from fastapi import HTTPException, Cookie
from dotenv import load_dotenv
import os
import jwt

load_dotenv()

JWT_SECRET = os.environ["JWT_SECRET"]


async def get_current_user(access_token: str = Cookie(None)):
    # read cookie , verify jwt , return user
    if access_token is None:
        raise HTTPException(status_code=401, detail="Access Denied")
    try:
        token_data = jwt.decode(access_token, JWT_SECRET, algorithms=["HS256"])
        return token_data
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail="Session Expired, please login again"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid Token")
