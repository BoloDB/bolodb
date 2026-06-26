from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict


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

    model_config = ConfigDict(populate_by_name=True)


class UserPublic(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    email: EmailStr
    role: Role

    model_config = ConfigDict(populate_by_name=True)
