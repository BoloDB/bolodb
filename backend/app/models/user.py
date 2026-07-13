from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
from backend.app.i18n.translator import _


class Role(Enum):
    user = "user"
    admin = "admin"


def validate_password_strength(password: str) -> str:
    """Validate password meets minimum complexity requirements.

    Requires: >= 8 chars, at least 1 uppercase, 1 lowercase, 1 digit.
    Returns the password if valid, raises ValueError otherwise.
    """
    if len(password) < 8:
        raise ValueError(_("Password must be at least 8 characters long"))
    if not any(c.isupper() for c in password):
        raise ValueError(_("Password must contain at least one uppercase letter"))
    if not any(c.islower() for c in password):
        raise ValueError(_("Password must contain at least one lowercase letter"))
    if not any(c.isdigit() for c in password):
        raise ValueError(_("Password must contain at least one digit"))
    return password


class UserSignup(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def check_password(cls, v):
        return validate_password_strength(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserInDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    email: EmailStr
    hashed_pass: str = ""
    role: Role
    google_id: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class UserPublic(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    email: EmailStr
    role: Role

    model_config = ConfigDict(populate_by_name=True)


class GoogleLogin(BaseModel):
    id_token: str
    client_id: str
