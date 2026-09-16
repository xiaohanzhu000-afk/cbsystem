"""登录相关接口。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import get_conn
from oplog import ACTION_LOGIN, log_action
from security import create_access_token, get_current_user, verify_password

router = APIRouter()


class LoginPayload(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(payload: LoginPayload):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (payload.username.strip(),)
        ).fetchone()
    finally:
        conn.close()

    if row is None or not verify_password(payload.password, row["password"]):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    token = create_access_token(row["username"])
    log_action(ACTION_LOGIN, row["username"])
    return {"token": token, "username": row["username"]}


@router.get("/me")
def me(username: str = Depends(get_current_user)):
    return {"username": username}
