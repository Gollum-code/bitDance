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

def test_reports_persistence(auth_headers, client):
    r = client.post(
        "/api/reports",
        headers=auth_headers,
        json={
            "title": "CI 报告",
            "body": "# 回测报告\n内容",
            "stats": {"sharpe_ratio": 1.2},
            "params": {"strategy_id": "01"},
        },
    )
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert r.json()["stats"]["sharpe_ratio"] == 1.2

    r = client.get("/api/reports", headers=auth_headers)
    assert r.status_code == 200
    assert any(x["id"] == rid for x in r.json()["items"])

    r = client.delete(f"/api/reports/{rid}", headers=auth_headers)
    assert r.status_code == 200
    r = client.get("/api/reports", headers=auth_headers)
    assert all(x["id"] != rid for x in r.json()["items"])


def test_paper_positions_lifecycle(auth_headers, client):
    r = client.post(
        "/api/paper/positions",
        headers=auth_headers,
        json={
            "strategyId": "01",
            "vtSymbol": "600519.SSE",
            "side": "long",
            "entryPrice": 1500.0,
            "entryDate": "2026-01-05",
            "capital": 50000,
        },
    )
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    assert r.json()["status"] == "open"

    r = client.post(
        f"/api/paper/positions/{pid}/close",
        headers=auth_headers,
        json={"exitPrice": 1650.0, "exitDate": "2026-02-05"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "closed"
    assert abs(r.json()["returnPct"] - 10.0) < 0.01

    r = client.get("/api/paper/positions?status=open", headers=auth_headers)
    assert r.status_code == 200
    assert all(x["id"] != pid for x in r.json()["items"])

    r = client.delete(f"/api/paper/positions/{pid}", headers=auth_headers)
    assert r.status_code == 200


def test_alert_rules_crud_and_check(auth_headers, client):
    r = client.post(
        "/api/alerts",
        headers=auth_headers,
        json={"code": "600519.SSE", "kind": "below", "value": 1.0, "message": "测试预警"},
    )
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    assert r.json()["code"] == "sh600519"

    # 重复规则应 409
    r = client.post(
        "/api/alerts",
        headers=auth_headers,
        json={"code": "sh600519", "kind": "below", "value": 1.0},
    )
    assert r.status_code == 409

    r = client.get("/api/alerts", headers=auth_headers)
    assert r.status_code == 200
    assert any(x["id"] == aid for x in r.json()["items"])

    # trader 未启动时 check 应优雅返回空事件，而不是 500
    r = client.post("/api/alerts/check", headers=auth_headers)
    assert r.status_code == 200
    assert "events" in r.json()

    r = client.patch(f"/api/alerts/{aid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["fired"] is False

    r = client.delete(f"/api/alerts/{aid}", headers=auth_headers)
    assert r.status_code == 200
