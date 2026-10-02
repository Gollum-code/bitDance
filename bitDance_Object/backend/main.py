from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "app.db"

JWT_SECRET = os.getenv("BITDANCE_JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
JWT_EXPIRES_SECONDS = int(os.getenv("BITDANCE_JWT_EXPIRES", "604800"))  # 7 days

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                member_tier TEXT NOT NULL DEFAULT 'free',
                member_until INTEGER NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS post_likes (
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (post_id, user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                body TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS comment_likes (
                comment_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (comment_id, user_id)
            )
            """
        )
        # 老库兼容：users 缺 member 列时补上
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "member_tier" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN member_tier TEXT NOT NULL DEFAULT 'free'")
        if "member_until" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN member_until INTEGER NULL")
        conn.commit()
    finally:
        conn.close()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def issue_token(user_id: int) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "iat": now, "exp": now + JWT_EXPIRES_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def parse_bearer_token(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    if not creds:
        return None
    if creds.scheme.lower() != "bearer":
        return None
    return creds.credentials


@dataclass
class AuthedUser:
    id: int
    username: str
    email: str
    member_tier: str
    member_until: Optional[int]


def get_current_user(token: Optional[str] = Depends(parse_bearer_token)) -> AuthedUser:
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        sub = payload.get("sub")
        if not sub or not str(sub).isdigit():
            raise HTTPException(status_code=401, detail="登录已失效")
        user_id = int(sub)
    except JWTError:
        raise HTTPException(status_code=401, detail="登录已失效")

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, username, email, member_tier, member_until FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="登录已失效")
        return AuthedUser(
            id=int(row["id"]),
            username=str(row["username"]),
            email=str(row["email"]),
            member_tier=str(row["member_tier"]),
            member_until=row["member_until"],
        )
    finally:
        conn.close()


def user_is_member(user: AuthedUser) -> bool:
    if user.member_tier == "member":
        if user.member_until is None:
            return True
        return int(user.member_until) > int(time.time())
    return False


def user_dto(user: AuthedUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "memberTier": user.member_tier,
        "memberUntil": None if user.member_until is None else time.strftime("%Y-%m-%d", time.gmtime(int(user.member_until))),
        "memberActive": user_is_member(user),
    }


def normalize_account(account: str) -> str:
    return account.strip()


_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,24}$")


class RegisterBody(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


class LoginBody(BaseModel):
    account: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=72)


class UserDTO(BaseModel):
    id: int
    username: str
    email: EmailStr
    memberTier: str = "free"
    memberUntil: Optional[str] = None
    memberActive: bool = False


class AuthResponse(BaseModel):
    token: str
    user: UserDTO


app = FastAPI(title="bitDance backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup() -> None:
    init_db()


@app.exception_handler(HTTPException)
async def http_exception_handler(_req: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.post("/api/auth/register", response_model=AuthResponse)
def register(body: RegisterBody):
    username = body.username.strip()
    if not _USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="用户名需为 3-24 位字母/数字/下划线")

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE username = ? OR email = ?",
            (username, str(body.email).lower()),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="用户名或邮箱已被注册")

        now = int(time.time())
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, created_at, member_tier) VALUES (?, ?, ?, ?, 'free')",
            (username, str(body.email).lower(), hash_password(body.password), now),
        )
        conn.commit()
        user_id = int(cur.lastrowid)
        token = issue_token(user_id)
        user = AuthedUser(id=user_id, username=username, email=body.email, member_tier="free", member_until=None)
        return {"token": token, "user": user_dto(user)}
    finally:
        conn.close()


@app.post("/api/auth/login", response_model=AuthResponse)
def login(body: LoginBody):
    account = normalize_account(body.account)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, username, email, password_hash, member_tier, member_until FROM users WHERE username = ? OR email = ?",
            (account, account.lower()),
        ).fetchone()
        if not row or not verify_password(body.password, str(row["password_hash"])):
            raise HTTPException(status_code=401, detail="账号或密码错误")

        user_id = int(row["id"])
        token = issue_token(user_id)
        user = AuthedUser(
            id=user_id,
            username=str(row["username"]),
            email=str(row["email"]),
            member_tier=str(row["member_tier"]),
            member_until=row["member_until"],
        )
        return {"token": token, "user": user_dto(user)}
    finally:
        conn.close()


@app.get("/api/auth/me", response_model=UserDTO)
def me(user: AuthedUser = Depends(get_current_user)):
    return user_dto(user)


# ---- chat：转发到 trader(8000) 的真实 Kimi 对话（未配置 key 时降级为 stub） ----


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1)


def _forward_chat(path: str, payload: dict) -> dict:
    import urllib.request

    try:
        req = urllib.request.Request(
            f"http://localhost:8000{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        # trader 未启动 / 未配置 key 时的降级响应
        return {
            "conversation_id": payload.get("conversation_id", ""),
            "reply": f"(stub) 收到: {payload.get('message', '')}",
        }


@app.post("/api/chat/send")
def chat_send(body: ChatRequest):
    result = _forward_chat("/chat/completions", {"message": body.message})
    return {"success": True, "reply": result.get("reply", ""), "conversationId": result.get("conversation_id", "")}


@app.post("/api/chat/new")
def chat_new(body: ChatRequest):
    result = _forward_chat("/chat/completions", {"message": body.message})
    return {"success": True, "reply": result.get("reply", ""), "conversationId": result.get("conversation_id", "")}


@app.post("/api/chat/clear")
def chat_clear(body: ChatRequest):
    return {"success": True}


@app.get("/api/chat/status")
def chat_status():
    return {"hasActiveConversation": False, "conversationId": ""}


# ---- membership（演示版会员，本地免支付直接开通） ----


@app.post("/api/membership/upgrade-demo")
def membership_upgrade(user: AuthedUser = Depends(get_current_user)):
    until = int(time.time()) + 365 * 24 * 3600
    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET member_tier = 'member', member_until = ? WHERE id = ?",
            (until, user.id),
        )
        conn.commit()
    finally:
        conn.close()
    upgraded = AuthedUser(id=user.id, username=user.username, email=user.email, member_tier="member", member_until=until)
    return user_dto(upgraded)


# ---- community（帖子 / 点赞 / 评论） ----


class PostCreateBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


class CommentCreateBody(BaseModel):
    body: str = Field(..., min_length=1)


def _post_summary(row: Any, like_count: int, comment_count: int, liked_by_me: bool = False) -> dict[str, Any]:
    import time as _t

    return {
        "id": int(row["id"]),
        "title": str(row["title"]),
        "excerpt": str(row["content"])[:120],
        "authorUsername": str(row["username"]),
        "likeCount": like_count,
        "commentCount": comment_count,
        "createdAt": _t.strftime("%Y-%m-%d %H:%M", _t.localtime(int(row["created_at"]))),
        "likedByMe": liked_by_me,
    }


@app.get("/api/community/trending")
def community_trending(limit: int = 10):
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT p.*, u.username,
                   (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.id) AS like_count,
                   (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count
            FROM posts p JOIN users u ON u.id = p.author_id
            ORDER BY like_count DESC, p.created_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_post_summary(r, int(r["like_count"]), int(r["comment_count"])) for r in rows]
    finally:
        conn.close()


@app.get("/api/community/posts")
def community_posts(q: str = "", page: int = 1, size: int = 10):
    conn = get_db()
    try:
        page = max(page, 1)
        size = min(max(size, 1), 50)
        offset = (page - 1) * size
        like_q = " AND (p.title LIKE ? OR p.content LIKE ?)" if q else ""
        params: list[Any] = []
        if q:
            params.extend([f"%{q}%", f"%{q}%"])
        params.extend([size, offset])
        rows = conn.execute(
            f"""
            SELECT p.*, u.username,
                   (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.id) AS like_count,
                   (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count
            FROM posts p JOIN users u ON u.id = p.author_id
            WHERE 1=1 {like_q}
            ORDER BY p.created_at DESC LIMIT ? OFFSET ?
            """,
            tuple(params),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM posts p WHERE 1=1 " + like_q,
            tuple(params[:2]) if q else (),
        ).fetchone()["n"]
        return {
            "items": [_post_summary(r, int(r["like_count"]), int(r["comment_count"])) for r in rows],
            "total": int(total),
            "page": page,
            "size": size,
        }
    finally:
        conn.close()


@app.get("/api/community/posts/{post_id}")
def community_post_detail(post_id: int, user: Optional[AuthedUser] = Depends(get_current_user)):
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT p.*, u.username,
                   (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.id) AS like_count,
                   (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count
            FROM posts p JOIN users u ON u.id = p.author_id
            WHERE p.id = ?
            """,
            (post_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="帖子不存在")
        liked = False
        if user:
            liked = conn.execute(
                "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?", (post_id, user.id)
            ).fetchone() is not None
        return {
            **_post_summary(row, int(row["like_count"]), int(row["comment_count"]), liked),
            "content": str(row["content"]),
        }
    finally:
        conn.close()


@app.post("/api/community/posts")
def community_create_post(body: PostCreateBody, user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO posts (author_id, title, content, created_at) VALUES (?, ?, ?, ?)",
            (user.id, body.title.strip(), body.content.strip(), int(time.time())),
        )
        conn.commit()
        return {
            "id": int(cur.lastrowid),
            "title": body.title.strip(),
            "excerpt": body.content.strip()[:120],
            "content": body.content.strip(),
            "authorUsername": user.username,
            "likeCount": 0,
            "commentCount": 0,
            "likedByMe": False,
            "createdAt": time.strftime("%Y-%m-%d %H:%M", time.localtime()),
        }
    finally:
        conn.close()


@app.post("/api/community/posts/{post_id}/like")
def community_toggle_post_like(post_id: int, user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        exists = conn.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="帖子不存在")
        liked = conn.execute(
            "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?", (post_id, user.id)
        ).fetchone()
        if liked:
            conn.execute("DELETE FROM post_likes WHERE post_id = ? AND user_id = ?", (post_id, user.id))
        else:
            conn.execute("INSERT INTO post_likes (post_id, user_id) VALUES (?, ?)", (post_id, user.id))
        conn.commit()
        count = conn.execute("SELECT COUNT(*) AS n FROM post_likes WHERE post_id = ?", (post_id,)).fetchone()["n"]
        return {"liked": liked is None, "likeCount": int(count)}
    finally:
        conn.close()


@app.get("/api/community/posts/{post_id}/comments")
def community_comments(post_id: int, sort: str = "new", user: Optional[AuthedUser] = Depends(get_current_user)):
    conn = get_db()
    try:
        order = "c.created_at DESC" if sort == "new" else "(SELECT COUNT(*) FROM comment_likes cl WHERE cl.comment_id = c.id) DESC"
        rows = conn.execute(
            f"""
            SELECT c.*, u.username,
                   (SELECT COUNT(*) FROM comment_likes cl WHERE cl.comment_id = c.id) AS like_count
            FROM comments c JOIN users u ON u.id = c.author_id
            WHERE c.post_id = ? ORDER BY {order}
            """,
            (post_id,),
        ).fetchall()
        result = []
        for r in rows:
            liked = False
            if user:
                liked = conn.execute(
                    "SELECT 1 FROM comment_likes WHERE comment_id = ? AND user_id = ?", (r["id"], user.id)
                ).fetchone() is not None
            result.append({
                "id": int(r["id"]),
                "body": str(r["body"]),
                "authorUsername": str(r["username"]),
                "likeCount": int(r["like_count"]),
                "likedByMe": liked,
                "createdAt": time.strftime("%Y-%m-%d %H:%M", time.localtime(int(r["created_at"]))),
            })
        return result
    finally:
        conn.close()


@app.post("/api/community/posts/{post_id}/comments")
def community_create_comment(post_id: int, body: CommentCreateBody, user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        exists = conn.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="帖子不存在")
        cur = conn.execute(
            "INSERT INTO comments (post_id, author_id, body, created_at) VALUES (?, ?, ?, ?)",
            (post_id, user.id, body.body.strip(), int(time.time())),
        )
        conn.commit()
        return {
            "id": int(cur.lastrowid),
            "body": body.body.strip(),
            "authorUsername": user.username,
            "likeCount": 0,
            "likedByMe": False,
            "createdAt": time.strftime("%Y-%m-%d %H:%M", time.localtime()),
        }
    finally:
        conn.close()


@app.post("/api/community/comments/{comment_id}/like")
def community_toggle_comment_like(comment_id: int, user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        exists = conn.execute("SELECT 1 FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="评论不存在")
        liked = conn.execute(
            "SELECT 1 FROM comment_likes WHERE comment_id = ? AND user_id = ?", (comment_id, user.id)
        ).fetchone()
        if liked:
            conn.execute("DELETE FROM comment_likes WHERE comment_id = ? AND user_id = ?", (comment_id, user.id))
        else:
            conn.execute("INSERT INTO comment_likes (comment_id, user_id) VALUES (?, ?)", (comment_id, user.id))
        conn.commit()
        count = conn.execute("SELECT COUNT(*) AS n FROM comment_likes WHERE comment_id = ?", (comment_id,)).fetchone()["n"]
        return {"liked": liked is None, "likeCount": int(count)}
    finally:
        conn.close()

