from enum import Enum
from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class Role(Enum):
    user = "user"
    admin = "admin"


class UserSignup(BaseModel):
    email: EmailStr
    password: str


class UserInDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    email: EmailStr
    hashed_pass: str
    role: Role

    class Config:
        populate_by_name = True


class UserPublic(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    email: EmailStr
    role: Role

    class Config:
        populate_by_name = True