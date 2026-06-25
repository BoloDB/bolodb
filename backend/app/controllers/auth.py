from pydantic import EmailStr
from backend.app.mongodatabase import get_user_by_email
import bcrypt
from fastapi import HTTPException
from datetime import datetime, timedelta
import jwt
import os
from dotenv import load_dotenv

load_dotenv()

jwt_secret = os.getenv("JWT_SECRET")


def login(email: EmailStr, password: str) -> str:
    user_details = get_user_by_email(email)
    if user_details is None:
        raise HTTPException(status_code=400, detail="Email id invalid, please signup")
    user_bytes = password.encode()
    if bcrypt.checkpw(user_bytes, user_details["hashed_pass"].encode("utf-8")) == True:
        return create_jwt(str(user_details["_id"]), user_details["role"])
    raise HTTPException(status_code=401, detail="Incorrect Password")


def create_jwt(user_id, role):
    ALGORITHM = "HS256"
    data = {"user_id": user_id, "role": role}
    expiry = datetime.utcnow() + timedelta(minutes=60)
    data.update({"exp": expiry})
    encoded_jwt = jwt.encode(data, jwt_secret, algorithm=ALGORITHM)
    return encoded_jwt