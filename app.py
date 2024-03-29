# TODO: Validate add/update against schema
"""
Loads the app.
"""

import os
import json
import datetime

from dotenv import load_dotenv
from pymongo import MongoClient
from flask import Flask, request
from bson import json_util, ObjectId

app = Flask(__name__)

load_dotenv()
MONGODB_URI = os.environ["MONGODB_URI"]
client = MongoClient(MONGODB_URI)

@app.route("/", methods=["GET"])
def default_route():
    """
    Returns a string
    """
    return "Landing page for to-do-list project"

@app.route("/get-all", methods=["GET"])
def get_all_dates():
    """
    Gets all date entries.

    Returns
    -------
    dict
        Details of all date entries.
    """
    db = client["dates-in-sg"]
    dates_collection = db.dates
    cursor = dates_collection.find()
    result = []
    for document in cursor:
        document_cleaned = json.loads(json_util.dumps(document))
        result.append(document_cleaned)
    return result

@app.route("/get-one", methods=["GET"])
def get_one_date():
    """
    Gets a date entry.

    Query Parameter
    ----------
    oid: str
        date entry _id

    Returns
    -------
    dict
        Details of date entry.
    """
    oid = request.args.get("oid")
    db = client["dates-in-sg"]
    dates_collection = db.dates
    document_to_find = {"_id": ObjectId(oid)}
    result = dates_collection.find_one(document_to_find)
    return json.loads(json_util.dumps(result))

@app.route("/add-date", methods=["POST"])
def add_date():
    """
    Adds a date entry.

    Request Body
    ----------
    application/json
        JSON object with date entry fields:
            "title": str
            "completed": bool

    Returns
    -------
    str
        Number of documents inserted.
    """
    db = client["dates-in-sg"]
    dates_collection = db.dates
    new_date_entry = request.get_json()
    new_date_entry = dict(new_date_entry)

    if "location" in new_date_entry and "activity" in new_date_entry:
        result = dates_collection.insert_one(new_date_entry)
        return f"_id of inserted document: {result.inserted_id}"
    return "review does not conform to schema"

@app.route("/update-date", methods=["PUT"])
def update_date():
    """
    Updates a date entry.

    Query Parameters
    ----------
    oid: str
        id_ of date entry to update.

    Request Body
    ----------
    application/json
        JSON object with fields (keys) to update and corresponding update values.

    Returns
    -------
    str
        Number of documents updated.
    """
    db = client["dates-in-sg"]
    dates_collection = db.dates
    oid = request.args.get("oid")

    reminder_to_update = {"_id": ObjectId(oid)}
    updates = request.get_json()

    result = dates_collection.update_one(reminder_to_update, {"$set": updates})

    return f"Documents updated: {str(result.modified_count)}"

@app.route("/delete-date", methods=["DELETE"])
def remove_date():
    """
    Deletes a date entry.

    Query Parameters
    ----------
    oid: str
        id_ of date entry to delete.

    Returns
    -------
    str
        Number of documents deleted.
    """
    db = client["dates-in-sg"]
    dates_collection = db.dates
    oid = request.args.get("oid")
    document_to_delete = {"_id": ObjectId(oid)}

    result = dates_collection.delete_one(document_to_delete)
    return f"Documents deleted: {str(result.deleted_count)}"

@app.route("/add-review", methods=["PUT"])
def add_review():
    """
    Adds a review to a specified date entry.

    Query Parameters
    ----------
    oid: str
        id_ of date entry to update.

    Request Body
    ----------
    application/json
        JSON object formatted according to the schema

    Returns
    -------
    str
        Number of documents updated.
    """
    db = client["dates-in-sg"]
    dates_collection = db.dates

    oid = request.args.get("oid")
    date_review = request.get_json()
    date_review = dict(date_review)
    find_duplicate = dates_collection.find_one({"_id": ObjectId(oid), "reviews.user_id": date_review['user_id']})
    if find_duplicate:
        return "Already Reviewed by User", 400
    date_review["date_added"] = datetime.datetime.now()
    date_to_review = {"_id": ObjectId(oid),}
    result = dates_collection.update_one(date_to_review,
                                         {"$push": {"reviews": date_review}})
    update_date_rating(oid)
    return f"Reviews added: {str(result.modified_count)}"

@app.route("/update-review", methods=["PUT"])
def update_review():
    """
    Adds a review to a specified date entry.

    Query Parameters
    ----------
    oid: str
        id_ of date entry to update.

    Request Body
    ----------
    application/json
        JSON object formatted according to the schema

    Returns
    -------
    str
        Number of documents updated.
    """
    db = client["dates-in-sg"]
    dates_collection = db.dates

    oid = request.args.get("oid")
    user_id = request.args.get("uid")
    date_review = request.get_json()
    date_review = dict(date_review)
    date_review["date_added"] = datetime.datetime.now()
    date_to_review = {"_id": ObjectId(oid), "reviews.user_id": user_id}
    result = dates_collection.update_one(date_to_review,
                                         {"$set": {"reviews.$": date_review}})
    update_date_rating(oid)

    return f"Reviews modified: {str(result.modified_count)}"

@app.route("/delete-review", methods=["DELETE"])
def delete_review():
    """
    Deletes a review to a specified date entry.

    Query Parameters
    ----------
    oid: str
        id_ of date entry to update.
    uid: str
        id_ of the user whose review is to be deleted.

    Returns
    -------
    str
        Number of documents updated.
    """
    db = client["dates-in-sg"]
    dates_collection = db.dates
    oid = request.args.get("oid")
    user_id = request.args.get("uid")
    review_to_delete = {"$pull": {"reviews": {"user_id": user_id}}}

    result = dates_collection.update_one({"_id": ObjectId(oid)}, review_to_delete)
    update_date_rating(oid)

    return f"Reviews deleted: {str(result.modified_count)}"

def update_date_rating(oid: str):
    """
    Given an oid returns the averages of the ratings in all reviews.
    """
    db = client["dates-in-sg"]
    dates_collection = db.dates
    select_by_oid = {"$match": {"_id": ObjectId(oid)}}
    get_average = {"$project": {"avg_rating": {"$avg": "$reviews.rating"}, "_id": 0}}
    pipeline = [select_by_oid, get_average]
    cursor = dates_collection.aggregate(pipeline)

    try:
        res = next(cursor)["avg_rating"]
        if type(res) == float:
            dates_collection.update_one({"_id": ObjectId(oid)}, {"$set": {"review_rating": round(res, 1)}})

    except:
        dates_collection.update_one({"_id": ObjectId(oid)}, {"$set": {"review_rating": float(0)}})

if __name__ == "__main__":
    app.run(port=5000, debug=True)
