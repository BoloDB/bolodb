import os
from fastapi import Request
from bson import ObjectId
import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from pydantic import BaseModel
from dotenv import load_dotenv
from pymongo import MongoClient
from pydantic import BaseModel
from pymongo.database import Database
from backend.app.models.user import UserInDB

load_dotenv()
mongouri = os.getenv("MONGO_URI")
client = MongoClient(mongouri)
db = client["sports_council_db"]

def get_user_by_email(email):
    users = db["users"]
    user_data = users.find_one({"email": email})
    return user_data

def create_user(user_data: UserInDB):
    users = db["users"]
    return users.insert_one(user_data.model_dump(mode="json"))

def get_user_by_id(user_id):
    users = db["users"]
    user_data = users.find_one({"_id": ObjectId(user_id)})
    return user_data


def update_user(user_filter, update_op):
    users = db["users"]
    users.update_one(user_filter, update_op)
    return True

def serialize_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc