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