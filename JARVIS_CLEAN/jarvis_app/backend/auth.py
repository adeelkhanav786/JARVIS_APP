"""
auth.py — Register, Login, Change Password
"""
import hashlib, os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import get_conn, provision_user, get_user_info

router = APIRouter()


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode()).hexdigest()


class AuthRequest(BaseModel):
    username: str
    password: str


class ChangePwRequest(BaseModel):
    username:     str
    old_password: str
    new_password: str


@router.post("/register")
def register(req: AuthRequest):
    if not req.username or not req.password:
        raise HTTPException(400, "Username and password are required.")
    if len(req.username) < 2:
        raise HTTPException(400, "Username must be at least 2 characters.")
    if len(req.password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters.")
    conn = get_conn()
    if conn.execute("SELECT 1 FROM users WHERE username=?", (req.username,)).fetchone():
        conn.close()
        raise HTTPException(409, "Username already exists.")
    salt = os.urandom(16).hex()
    conn.execute(
        "INSERT INTO users (username, password_hash, salt, last_login) VALUES (?,?,?,datetime('now'))",
        (req.username, _hash(req.password, salt), salt)
    )
    conn.commit()
    conn.close()
    provision_user(req.username)
    return {"success": True, "message": "Registration successful!", "username": req.username}


@router.post("/login")
def login(req: AuthRequest):
    if not req.username or not req.password:
        raise HTTPException(400, "Username and password are required.")
    conn = get_conn()
    row = conn.execute(
        "SELECT password_hash, salt FROM users WHERE username=?", (req.username,)
    ).fetchone()
    conn.close()
    if not row or _hash(req.password, row["salt"]) != row["password_hash"]:
        raise HTTPException(401, "Invalid username or password.")
    provision_user(req.username)
    return {"success": True, "message": "Login successful!", "username": req.username,
            "user_info": get_user_info(req.username)}


@router.get("/me/{username}")
def get_me(username: str):
    info = get_user_info(username)
    if not info:
        raise HTTPException(404, "User not found.")
    return info


@router.post("/change-password")
def change_password(req: ChangePwRequest):
    if not all([req.username, req.old_password, req.new_password]):
        raise HTTPException(400, "All fields are required.")
    if len(req.new_password) < 4:
        raise HTTPException(400, "New password must be at least 4 characters.")
    conn = get_conn()
    row = conn.execute(
        "SELECT password_hash, salt FROM users WHERE username=?", (req.username,)
    ).fetchone()
    if not row:
        conn.close(); raise HTTPException(404, "User not found.")
    if _hash(req.old_password, row["salt"]) != row["password_hash"]:
        conn.close(); raise HTTPException(401, "Current password is incorrect.")
    new_salt = os.urandom(16).hex()
    conn.execute(
        "UPDATE users SET password_hash=?, salt=? WHERE username=?",
        (_hash(req.new_password, new_salt), new_salt, req.username)
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": "Password changed successfully!"}
