from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
# 支持测试隔离：BITDANCE_DB_PATH 覆盖数据库文件
DB_PATH = Path(os.environ.get("BITDANCE_DB_PATH", "")) if os.environ.get("BITDANCE_DB_PATH") else DATA_DIR / "app.db"

JWT_SECRET = os.getenv("BITDANCE_JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
JWT_EXPIRES_SECONDS = int(os.getenv("BITDANCE_JWT_EXPIRES", "604800"))  # 7 days

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)
logger = logging.getLogger("bitdance.backend")

_alert_task: asyncio.Task | None = None


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
        # 回测报告历史：原先只存浏览器 localStorage，换设备即丢且无法多端同步
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL,
                preview TEXT NOT NULL DEFAULT '',
                stats TEXT NOT NULL DEFAULT '{}',
                params TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL,
                UNIQUE(user_id, id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_backtest_reports_user ON backtest_reports(user_id, created_at DESC)"
        )
        # 纸面交易持仓：服务端保存才能在别的设备/刷新后继续
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                strategy_id TEXT NOT NULL,
                vt_symbol TEXT NOT NULL,
                side TEXT NOT NULL DEFAULT 'long',
                entry_price REAL NOT NULL,
                entry_date TEXT NOT NULL,
                capital REAL NOT NULL DEFAULT 0,
                note TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                exit_price REAL NULL,
                exit_date TEXT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_paper_positions_user ON paper_positions(user_id, status, created_at DESC)"
        )
        # 价格预警规则：原先纯前端 setInterval，关页面即失效
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'below',
                value REAL NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                fired INTEGER NOT NULL DEFAULT 0,
                last_fired_at INTEGER NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(user_id, code, kind, value)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_rules_user ON alert_rules(user_id, fired, created_at DESC)"
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
        "memberUntil": None if user.member_until is None else time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(int(user.member_until))),
        "memberActive": user_is_member(user),
    }


def iso_time(ts: int | float) -> str:
    """epoch -> ISO8601（与 Java LocalDateTime 序列化一致，如 2026-10-02T18:00:00）。"""
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(int(ts)))


# ---- 会员门禁（与 demo Java 版 MembershipService 行为一致） ----


def assert_can_use_strategy(user: AuthedUser, strategy_id: str) -> None:
    """非会员仅允许使用策略列表第一个策略；开通会员可解锁全部。"""
    if not strategy_id or not strategy_id.strip():
        raise HTTPException(status_code=400, detail="strategyId 不能为空")
    if user_is_member(user):
        return
    free_id = resolve_free_strategy_id()
    if not free_id:
        free_id = "01"
    if free_id == strategy_id.strip():
        return
    raise HTTPException(
        status_code=403,
        detail="非会员仅可使用列表中的首个策略，开通会员可解锁其余策略与 AI 问答",
    )


def assert_ai_access(user: AuthedUser) -> None:
    if not user_is_member(user):
        raise HTTPException(
            status_code=403,
            detail="AI 问答为会员功能，请在会员中心开通会员",
        )


def _forward_json(path: str, payload: dict, method: str = "POST") -> dict:
    """转发到 trader(8000)。"""
    import urllib.request

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://localhost:8000{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"回测服务暂不可用: {exc}") from exc


_free_id_cache: dict[str, Any] = {"id": None, "at": 0.0}


def resolve_free_strategy_id() -> str | None:
    """取策略列表第一个 id（缓存 60s，与 Java 版一致）。"""
    now = time.time()
    cached = _free_id_cache["id"]
    if cached and now - _free_id_cache["at"] < 60:
        return cached
    try:
        raw = _forward_json("/strategy/list", {}, method="GET")
    except Exception:
        return cached
    strategies = raw.get("strategies") or []
    if not strategies:
        return cached
    first = strategies[0]
    sid = str(first.get("strategy_id", "")).strip() or None
    if sid:
        _free_id_cache["id"] = sid
        _free_id_cache["at"] = now
    return sid


def annotate_strategies(raw: dict, user: AuthedUser | None) -> dict:
    """给策略列表打会员锁定标记（与 Java 版 annotateStrategies 一致）。"""
    if raw is None:
        return {}
    member = user is not None and user_is_member(user)
    strategies = raw.get("strategies") or []
    if strategies:
        free_id = None
        for row in strategies:
            sid = str(row.get("strategy_id", "")).strip()
            if free_id is None:
                free_id = sid or None
            row["locked"] = (not member) and (sid != free_id)
        raw["freeStrategyId"] = free_id
    raw["memberActive"] = member
    return raw


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
async def _on_startup() -> None:
    init_db()
    # 价格预警后台检查：每 30 秒拉一次 trader 实时快照，命中即标记 fired。
    # 放在后台任务里，用户关掉浏览器也能触发（前端通过 /api/alerts 拉取结果）。
    global _alert_task
    _alert_task = asyncio.create_task(_alert_loop())


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    global _alert_task
    if _alert_task is not None:
        _alert_task.cancel()
        _alert_task = None


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
def chat_send(body: ChatRequest, user: AuthedUser = Depends(get_current_user)):
    assert_ai_access(user)
    result = _forward_chat("/chat/completions", {"conversation_id": body.conversation_id or "", "message": body.message})
    return {"success": True, "reply": result.get("reply", ""), "conversationId": result.get("conversation_id", "")}


@app.post("/api/chat/send-with-id")
def chat_send_with_id(body: ChatRequest, user: AuthedUser = Depends(get_current_user)):
    assert_ai_access(user)
    result = _forward_chat("/chat/completions", {"conversation_id": body.conversation_id or "", "message": body.message})
    return {
        "conversationId": result.get("conversation_id", ""),
        "reply": result.get("reply", ""),
        "model": result.get("model"),
        "usage": result.get("usage"),
    }


@app.post("/api/chat/new")
def chat_new(body: ChatRequest, user: AuthedUser = Depends(get_current_user)):
    assert_ai_access(user)
    result = _forward_chat("/chat/completions", {"message": body.message})
    return {"success": True, "reply": result.get("reply", ""), "conversationId": result.get("conversation_id", "")}


@app.post("/api/chat/clear")
def chat_clear(body: ChatRequest, user: AuthedUser = Depends(get_current_user)):
    return {"success": True, "message": "会话已清空"}


@app.get("/api/chat/status")
def chat_status(user: AuthedUser = Depends(get_current_user)):
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


# ---- backtest：转发 trader(8000) 真实回测，非会员仅放行首个策略 ----


class BacktestRunBody(BaseModel):
    strategyId: Optional[str] = None
    strategy_id: Optional[str] = None
    vtSymbol: str = "600031.SSE"
    vt_symbol: Optional[str] = None
    start: str = "2024-01-01"
    end: Optional[str] = None
    rate: float = 0.0003
    slippage: float = 0.01
    size: float = 1.0
    pricetick: float = 0.01
    capital: int = 10000
    fastWindow: Optional[int] = None
    slowWindow: Optional[int] = None
    signalWindow: Optional[int] = None
    atrWindow: Optional[int] = None
    atrMult: Optional[float] = None
    fixedSize: Optional[int] = None
    stopLossPct: Optional[float] = None
    takeProfitPct: Optional[float] = None
    trailingStopPct: Optional[float] = None


def _build_strategy_query(payload: dict) -> str:
    """把 camelCase 请求体转成 8000 chooseStrategy 的 query 参数。"""
    q: dict[str, str] = {}
    sid = payload.get("strategyId") or payload.get("strategy_id")
    if sid:
        q["strategy_id"] = str(sid)
    symbol = payload.get("vtSymbol") or payload.get("vt_symbol")
    if symbol:
        q["vt_symbol"] = str(symbol)
    q["start"] = str(payload.get("start", "2024-01-01"))
    q["end"] = str(payload.get("end") or max(payload.get("start", "2024-01-01"), "2024-01-01"))
    for src, dst in [
        ("rate", "rate"), ("slippage", "slippage"), ("size", "size"),
        ("pricetick", "pricetick"), ("capital", "capital"),
    ]:
        if payload.get(src) is not None:
            q[dst] = str(payload[src])
    for src, dst in [
        ("fastWindow", "fast_window"), ("slowWindow", "slow_window"),
        ("signalWindow", "signal_window"), ("atrWindow", "atr_window"),
        ("atrMult", "atr_mult"), ("fixedSize", "fixed_size"),
        ("stopLossPct", "stop_loss_pct"), ("takeProfitPct", "take_profit_pct"),
        ("trailingStopPct", "trailing_stop_pct"),
    ]:
        if payload.get(src) is not None:
            q[dst] = str(payload[src])
    import urllib.parse

    return urllib.parse.urlencode(q)


@app.get("/api/backtest/strategies")
def backtest_strategies(user: Optional[AuthedUser] = Depends(get_current_user)):
    raw = _forward_json("/strategy/list", {}, method="GET")
    return annotate_strategies(raw, user)


@app.get("/api/backtest/run")
@app.get("/api/backtest/run-symbol")
@app.get("/api/backtest/run-range")
@app.get("/api/backtest/run-custom")
def backtest_run(strategy_id: str = "", user: AuthedUser = Depends(get_current_user)):
    assert_can_use_strategy(user, strategy_id)
    q = _build_strategy_query({"strategyId": strategy_id, "start": "2024-01-01", "end": ""})
    return _forward_json(f"/strategy/{strategy_id}?{q}", {}, method="GET")


@app.post("/api/backtest/run")
def backtest_run_post(payload: BacktestRunBody, user: AuthedUser = Depends(get_current_user)):
    body = payload.model_dump()
    sid = body.get("strategyId") or body.get("strategy_id")
    if not sid:
        raise HTTPException(status_code=400, detail="strategyId 不能为空")
    assert_can_use_strategy(user, str(sid))
    q = _build_strategy_query(body)
    return _forward_json(f"/strategy/{sid}?{q}", {}, method="GET")


# ---- community（帖子 / 点赞 / 评论） ----


class PostCreateBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


class CommentCreateBody(BaseModel):
    body: str = Field(..., min_length=1)


def _post_summary(row: Any, like_count: int, comment_count: int, liked_by_me: bool = False) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "title": str(row["title"]),
        "excerpt": str(row["content"])[:120],
        "authorUsername": str(row["username"]),
        "likeCount": like_count,
        "commentCount": comment_count,
        "createdAt": iso_time(int(row["created_at"])),
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
            "createdAt": iso_time(time.time()),
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
                "createdAt": iso_time(int(r["created_at"])),
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
            "createdAt": iso_time(time.time()),
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


# ---- tushare 行情 CSV 上传：转发到 trader(8000) ----


@app.post("/api/tusharestaticsupload/upload/csv")
async def tushare_upload_csv(file: UploadFile = File(...)):
    import urllib.request

    content = await file.read()
    boundary = "----bitdance" + str(int(time.time() * 1000))
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file.filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    try:
        req = urllib.request.Request(
            "http://localhost:8000/upload/csv",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"上传转发失败: {exc}") from exc


# ---- 回测报告历史（服务端持久化，替代 localStorage） ----

class ReportCreateBody(BaseModel):
    title: str = Field("", max_length=200)
    body: str = Field(..., min_length=1)
    preview: str = Field("", max_length=400)
    stats: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


def _report_dto(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "title": str(row["title"] or ""),
        "body": str(row["body"]),
        "preview": str(row["preview"] or ""),
        "stats": json.loads(row["stats"] or "{}"),
        "params": json.loads(row["params"] or "{}"),
        "createdAt": int(row["created_at"]),
    }


@app.get("/api/reports")
def list_reports(limit: int = 50, user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM backtest_reports WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user.id, max(1, min(limit, 200))),
        ).fetchall()
        return {"items": [_report_dto(r) for r in rows]}
    finally:
        conn.close()


@app.post("/api/reports")
def create_report(body: ReportCreateBody, user: AuthedUser = Depends(get_current_user)):
    preview = body.preview or body.body.strip()[:200]
    conn = get_db()
    try:
        cur = conn.execute(
            """
            INSERT INTO backtest_reports (user_id, title, body, preview, stats, params, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.id,
                body.title.strip(),
                body.body.strip(),
                preview,
                json.dumps(body.stats, ensure_ascii=False),
                json.dumps(body.params, ensure_ascii=False),
                int(time.time()),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM backtest_reports WHERE id = ?", (int(cur.lastrowid),)).fetchone()
        return _report_dto(row)
    finally:
        conn.close()


@app.delete("/api/reports/{report_id}")
def delete_report(report_id: int, user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        cur = conn.execute("DELETE FROM backtest_reports WHERE id = ? AND user_id = ?", (report_id, user.id))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="报告不存在")
        return {"deleted": True, "id": str(report_id)}
    finally:
        conn.close()


# ---- 纸面交易持仓（服务端账本） ----

class PaperPositionBody(BaseModel):
    strategyId: str = Field(..., max_length=8)
    vtSymbol: str = Field(..., max_length=32)
    side: str = Field("long", pattern="^(long|short)$")
    entryPrice: float = Field(..., gt=0)
    entryDate: str = Field(..., max_length=10)
    capital: float = Field(0, ge=0)
    note: str = Field("", max_length=500)


class PaperCloseBody(BaseModel):
    exitPrice: float = Field(..., gt=0)
    exitDate: Optional[str] = Field(None, max_length=10)


def _paper_dto(row: Any) -> dict[str, Any]:
    entry = float(row["entry_price"])
    exit_price = None if row["exit_price"] is None else float(row["exit_price"])
    ret = None
    if exit_price is not None and entry > 0:
        ret = (exit_price / entry - 1.0) * 100.0 if row["side"] == "long" else (entry / exit_price - 1.0) * 100.0
    return {
        "id": int(row["id"]),
        "strategyId": str(row["strategy_id"]),
        "vtSymbol": str(row["vt_symbol"]),
        "side": str(row["side"]),
        "entryPrice": entry,
        "entryDate": str(row["entry_date"]),
        "capital": float(row["capital"]),
        "note": str(row["note"]),
        "status": str(row["status"]),
        "exitPrice": exit_price,
        "exitDate": None if row["exit_date"] is None else str(row["exit_date"]),
        "returnPct": None if ret is None else round(ret, 4),
        "createdAt": int(row["created_at"]),
        "updatedAt": int(row["updated_at"]),
    }


@app.get("/api/paper/positions")
def paper_positions(status: str = "", user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM paper_positions WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                (user.id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM paper_positions WHERE user_id = ? ORDER BY created_at DESC",
                (user.id,),
            ).fetchall()
        return {"items": [_paper_dto(r) for r in rows]}
    finally:
        conn.close()


@app.post("/api/paper/positions")
def paper_create(body: PaperPositionBody, user: AuthedUser = Depends(get_current_user)):
    now = int(time.time())
    conn = get_db()
    try:
        cur = conn.execute(
            """
            INSERT INTO paper_positions
              (user_id, strategy_id, vt_symbol, side, entry_price, entry_date, capital, note, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
            """,
            (
                user.id,
                body.strategyId,
                body.vtSymbol,
                body.side,
                body.entryPrice,
                body.entryDate,
                body.capital,
                body.note,
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM paper_positions WHERE id = ?", (int(cur.lastrowid),)).fetchone()
        return _paper_dto(row)
    finally:
        conn.close()


@app.post("/api/paper/positions/{position_id}/close")
def paper_close(position_id: int, body: PaperCloseBody, user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM paper_positions WHERE id = ? AND user_id = ?", (position_id, user.id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="持仓不存在")
        if row["status"] != "open":
            raise HTTPException(status_code=409, detail="该持仓已平仓")
        conn.execute(
            "UPDATE paper_positions SET status='closed', exit_price=?, exit_date=?, updated_at=? WHERE id=?",
            (
                body.exitPrice,
                body.exitDate or time.strftime("%Y-%m-%d"),
                int(time.time()),
                position_id,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM paper_positions WHERE id = ?", (position_id,)).fetchone()
        return _paper_dto(row)
    finally:
        conn.close()


@app.delete("/api/paper/positions/{position_id}")
def paper_delete(position_id: int, user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        cur = conn.execute("DELETE FROM paper_positions WHERE id = ? AND user_id = ?", (position_id, user.id))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="持仓不存在")
        return {"deleted": True}
    finally:
        conn.close()


# ---- 价格预警（服务端规则 + 后台检查） ----

class AlertBody(BaseModel):
    code: str = Field(..., min_length=2, max_length=16, description="sh600519 或 600519.SSE")
    kind: str = Field("below", pattern="^(below|above)$")
    value: float = Field(..., gt=0)
    message: str = Field("", max_length=200)


def _normalize_tx_code(code: str) -> str:
    raw = code.strip().lower()
    if re.match(r"^(sh|sz|bj)\d{6}$", raw):
        return raw
    m = re.match(r"^(\d{6})\.(sse|szse|bse|sh|sz|bj)$", raw)
    if m:
        suffix = {"sse": "sh", "sh": "sh", "szse": "sz", "sz": "sz", "bse": "bj", "bj": "bj"}[m.group(2)]
        return f"{suffix}{m.group(1)}"
    raise HTTPException(status_code=400, detail="代码格式应为 sh600519 或 600519.SSE")


def _alert_dto(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "code": str(row["code"]),
        "kind": str(row["kind"]),
        "value": float(row["value"]),
        "message": str(row["message"]),
        "fired": bool(row["fired"]),
        "lastFiredAt": row["last_fired_at"],
        "createdAt": int(row["created_at"]),
    }


def _trader_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    """从 trader(8000) 的实时快照接口取价，返回 code -> quote。"""
    import urllib.parse
    import urllib.request

    if not codes:
        return {}
    qs = urllib.parse.urlencode({"symbols": ",".join(codes)})
    try:
        with urllib.request.urlopen(f"http://localhost:8000/analytics/realtime?{qs}", timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in data.get("items") or []:
        ts = str(item.get("ts_code", "")).upper()
        # 600519.SSE -> sh600519
        m = re.match(r"^(\d{6})\.(SSE|SZSE|BSE)$", ts)
        if not m:
            continue
        prefix = {"SSE": "sh", "SZSE": "sz", "BSE": "bj"}[m.group(2)]
        out[f"{prefix}{m.group(1)}"] = item
    return out


def _evaluate_alerts(user_id: int | None = None) -> list[dict[str, Any]]:
    """检查预警规则，命中则标记 fired 并返回事件。后台循环与手动检查共用。"""
    conn = get_db()
    try:
        if user_id is None:
            rows = conn.execute("SELECT * FROM alert_rules WHERE fired = 0").fetchall()
        else:
            rows = conn.execute("SELECT * FROM alert_rules WHERE user_id = ? AND fired = 0", (user_id,)).fetchall()
        if not rows:
            return []
        quotes = _trader_quotes(sorted({str(r["code"]) for r in rows}))
        now = int(time.time())
        events: list[dict[str, Any]] = []
        for r in rows:
            q = quotes.get(str(r["code"]))
            if not q:
                continue
            price = float(q.get("now") or 0)
            if price <= 0:
                continue
            hit = price <= float(r["value"]) if r["kind"] == "below" else price >= float(r["value"])
            if not hit:
                continue
            conn.execute(
                "UPDATE alert_rules SET fired = 1, last_fired_at = ? WHERE id = ?",
                (now, int(r["id"])),
            )
            events.append({
                **_alert_dto(r),
                "fired": True,
                "lastFiredAt": now,
                "price": price,
                "name": str(q.get("name", "")),
                "eventMessage": str(r["message"] or f"{r['code']} {'跌破' if r['kind'] == 'below' else '突破'} {r['value']}，现价 {price:.2f}"),
            })
        conn.commit()
        return events
    finally:
        conn.close()


@app.get("/api/alerts")
def list_alerts(user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM alert_rules WHERE user_id = ? ORDER BY created_at DESC", (user.id,)
        ).fetchall()
        return {"items": [_alert_dto(r) for r in rows]}
    finally:
        conn.close()


@app.post("/api/alerts")
def create_alert(body: AlertBody, user: AuthedUser = Depends(get_current_user)):
    code = _normalize_tx_code(body.code)
    conn = get_db()
    try:
        try:
            cur = conn.execute(
                "INSERT INTO alert_rules (user_id, code, kind, value, message, fired, created_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
                (user.id, code, body.kind, body.value, body.message, int(time.time())),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="相同预警规则已存在")
        row = conn.execute("SELECT * FROM alert_rules WHERE id = ?", (int(cur.lastrowid),)).fetchone()
        return _alert_dto(row)
    finally:
        conn.close()


@app.patch("/api/alerts/{alert_id}")
def reset_alert(alert_id: int, user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE alert_rules SET fired = 0, last_fired_at = NULL WHERE id = ? AND user_id = ?",
            (alert_id, user.id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="预警不存在")
        row = conn.execute("SELECT * FROM alert_rules WHERE id = ?", (alert_id,)).fetchone()
        return _alert_dto(row)
    finally:
        conn.close()


@app.delete("/api/alerts/{alert_id}")
def delete_alert(alert_id: int, user: AuthedUser = Depends(get_current_user)):
    conn = get_db()
    try:
        cur = conn.execute("DELETE FROM alert_rules WHERE id = ? AND user_id = ?", (alert_id, user.id))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="预警不存在")
        return {"deleted": True}
    finally:
        conn.close()


@app.post("/api/alerts/check")
def check_alerts(user: AuthedUser = Depends(get_current_user)):
    events = _evaluate_alerts(user.id)
    return {"events": events, "count": len(events)}

async def _alert_loop() -> None:
    """后台预警检查循环。异常不退出，下一轮继续。"""
    while True:
        try:
            events = await asyncio.to_thread(_evaluate_alerts, None)
            if events:
                logger.info("price alerts fired: %s", len(events))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("alert loop error: %r", exc)
        await asyncio.sleep(30)
