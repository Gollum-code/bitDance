# bitDance backend (FastAPI + SQLite)

## 启动

在 `bitDance_Object/backend` 目录下：

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

前端在 `vite.config.ts` 已把 `/api` 代理到 `http://localhost:8080`，所以前端 `npm run dev` 后即可直接联调。

## 接口

- `POST /api/auth/register` `{ username, email, password }`
- `POST /api/auth/login` `{ account, password }`（account 可为用户名或邮箱）
- `GET /api/auth/me`（Header: `Authorization: Bearer <token>`）

数据库文件：`backend/data/app.db`（自动创建）

