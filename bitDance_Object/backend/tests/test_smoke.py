"""后端 8080 接口冒烟测试（FastAPI TestClient）。

运行（需 backend/.venv）：.\\.venv\\Scripts\\python -m pytest tests -q
覆盖：注册/登录/me/会员/社区/聊天降级/上传端点存在。
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("BITDANCE_JWT_SECRET", "test-secret")
# 测试使用独立临时数据库（每会话唯一，避免残留数据），必须在 import main 之前设置
_tmpdb = Path(tempfile.mkdtemp(prefix="bitdance_ci_")) / "app.db"
os.environ["BITDANCE_DB_PATH"] = str(_tmpdb)
# main.py 在 backend/ 下（tests 的上一级）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app, init_db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["BITDANCE_DB_TEST"] = "1"
    c = TestClient(app)
    init_db()
    yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    r = client.post(
        "/api/auth/register",
        json={"username": "cismoke", "email": "ci@example.com", "password": "123456"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_login_me(auth_headers, client):
    r = client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["memberTier"] == "free"
    assert body["memberActive"] is False


def test_membership_upgrade(auth_headers, client):
    r = client.post("/api/membership/upgrade-demo", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["memberTier"] == "member"
    assert body["memberActive"] is True


def test_community_crud(auth_headers, client):
    r = client.post(
        "/api/community/posts",
        headers=auth_headers,
        json={"title": "CI 冒烟测试", "content": "正文内容"},
    )
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    r = client.get(f"/api/community/posts/{pid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["title"] == "CI 冒烟测试"

    r = client.get("/api/community/posts?page=1&size=10", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    r = client.post(f"/api/community/posts/{pid}/like", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["likeCount"] == 1

    r = client.post(
        f"/api/community/posts/{pid}/comments",
        headers=auth_headers,
        json={"body": "好策略"},
    )
    assert r.status_code == 200
    cid = r.json()["id"]

    r = client.post(f"/api/community/comments/{cid}/like", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["likeCount"] == 1


def test_chat_fallback(auth_headers, client):
    """trader 未启动/未配 key 时，chat 应返回 stub 降级而非 500。"""
    r = client.post("/api/chat/send", headers=auth_headers, json={"message": "你好"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "reply" in body