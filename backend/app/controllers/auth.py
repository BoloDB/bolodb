import bcrypt
from pydantic import EmailStr
from fastapi import HTTPException
from backend.app.models.user import UserSignup, UserInDB, Role
from backend.app.mongodatabase import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user,
    serialize_doc,
)
from bson import ObjectId
import jwt
from datetime import datetime, timedelta, UTC
from backend.app.secrets import get_jwt_secret


def get_me(user_id):
    data = serialize_doc(get_user_by_id(user_id))
    data.pop("hashed_pass", None)
    return data


def login(email: EmailStr, password: str):
    user_details = get_user_by_email(email)
    if user_details is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user_bytes = password.encode()
    if bcrypt.checkpw(user_bytes, user_details["hashed_pass"].encode("utf-8")):
        return create_jwt(str(user_details["_id"]), user_details["role"])
    raise HTTPException(status_code=401, detail="Invalid credentials")


def create_access_jwt(user_id, role):
    ALGORITHM = "HS256"
    data = {"user_id": user_id, "role": role}
    expiry = datetime.now(UTC) + timedelta(minutes=60)
    data.update({"exp": expiry})
    return jwt.encode(data, get_jwt_secret(), algorithm=ALGORITHM)


def create_jwt(user_id, role):
    ALGORITHM = "HS256"
    secret = get_jwt_secret()
    data = {"user_id": user_id, "role": role}
    refresh_data = {"user_id": user_id, "role": role}
    access_expiry = datetime.now(UTC) + timedelta(hours=1)
    refresh_expiry = datetime.now(UTC) + timedelta(days=7)
    data.update({"exp": access_expiry})
    refresh_data.update({"exp": refresh_expiry})
    access_encoded_jwt = jwt.encode(data, secret, algorithm=ALGORITHM)
    refresh_encoded_jwt = jwt.encode(refresh_data, secret, algorithm=ALGORITHM)
    return {"access_token": access_encoded_jwt, "refresh_token": refresh_encoded_jwt}


def signup(user: UserSignup):
    if get_user_by_email(user.email) is not None:
        raise HTTPException(status_code=400, detail="Email already Registered")
    encoded_pass = user.password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_pw = bcrypt.hashpw(encoded_pass, salt)
    hashed_pw = hashed_pw.decode("utf-8")
    user_in_db = UserInDB(email=user.email, hashed_pass=hashed_pw, role=Role.user)
    create_user(user_in_db)
    return True


def change_password(user_id, old_password, new_password):
    user_details = get_user_by_id(user_id)
    if user_details is None:
        raise HTTPException(status_code=404, detail="User not found")
    old_pass_enc = old_password.encode("utf-8")
    new_pass_enc = new_password.encode("utf-8")
    if bcrypt.checkpw(old_pass_enc, user_details["hashed_pass"].encode("utf-8")):
        salt = bcrypt.gensalt()
        new_hashed_pw = bcrypt.hashpw(new_pass_enc, salt)
        user_details["hashed_pass"] = new_hashed_pw.decode("utf-8")
        update_user(
            {"_id": ObjectId(user_id)},
            {"$set": {"hashed_pass": user_details["hashed_pass"]}},
        )
        return True
    raise HTTPException(status_code=401, detail="Incorrect Password, Please try again")
