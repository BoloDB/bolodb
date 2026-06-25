from fastapi import APIRouter, Request
import backend.app.controllers.auth as auth_controller
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
async def login(request: Request):
    body = await request.json()
    token = auth_controller.login(body["email"], body["password"])
    response = JSONResponse({"message": "Login Success"})
    response.set_cookie(
        key="access_token",
        value = token,
        httponly=True,
    )
    return response