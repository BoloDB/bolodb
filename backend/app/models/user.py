from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class Role(Enum):
    user = "user"
    admin = "admin"


def validate_password_strength(password: str) -> str:
    """Validate password meets minimum complexity requirements.

    Requires: >= 8 chars, at least 1 uppercase, 1 lowercase, 1 digit.
    Returns the password if valid, raises ValueError otherwise.
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit")
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
    id: str = ""
    email: EmailStr
    hashed_pass: str = ""
    role: Role
    google_id: Optional[str] = None
    supabase_id: Optional[str] = None
    email_verified: bool = False
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserPublic(BaseModel):
    id: str = ""
    email: EmailStr
    role: Role
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None


class SupabaseLogin(BaseModel):
    access_token: str


class VerifyEmailOTP(BaseModel):
    code: str


class UpdateProfile(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
