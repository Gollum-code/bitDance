# 数据源与行情

系统支持两种行情数据源，通过环境变量 `DATA_SOURCE` 切换，**默认使用免费源**（无需任何配置）。

## 1. 免费源（默认）

- 实现：`trader/routers/free_market.py`（腾讯公开接口 `qt.gtimg.cn` / `web.ifzq.gtimg.cn`）
- 能力：
  - 全市场 A 股列表（约 5500+ 只，缓存 1 小时）
  - 日线 K 线（前复权 / 不复权）
  - 分钟 K 线（m1 / m5 / m15 / m30 / m60）
  - 实时快照（REST + WebSocket）
- 无需 token / 注册，适合 demo 与 GitHub 展示

```bash
python trader/main.py   # 默认即免费源
```

## 2. TuShare（可选）

数据更全（财务、指数、板块等），需要 TuShare Pro 账号与 token。

```bash
set DATA_SOURCE=tushare
set TUSHARE_TOKEN=你的token
python trader/main.py
```

可选 `TUSHARE_HTTP_URL` 自定义网关。

## 3. 行情 API 一览（trader 8000）

| 端点 | 说明 |
| --- | --- |
| `GET /api/market/stocks?q=&limit=` | 搜索股票列表 |
| `GET /api/market/daily?ts_code=&start_date=&end_date=` | 日线 K 线 |
| `GET /api/market/minute?ts_code=&period=&count=` | 分钟 K 线 |
| `POST /api/market/sync-vnpy` | 单只日线写入本地库 |
| `POST /api/market/sync-batch` | 批量日线写入本地库（选股联动用） |
| `GET /analytics/realtime?symbols=` | 实时快照 REST |
| `WS /analytics/ws` | 实时快照 WebSocket 推送 |

代码格式：前端用 TuShare 风格 `600519.SH`；回测引擎用 vn.py 风格 `600519.SSE`，两端会自动转换。

## 4. 本地数据库

- 回测与选股都读 vn.py 本地库：`~/.vntrader/database.db`
- 全新环境需先「同步日线到本地库」（见「快速开始」）
- 也可通过 `/api/tusharestaticsupload/upload/csv` 或前端「导入 CSV 日线」上传本地文件

## 5. 限流与降级

腾讯免费接口对**高频请求**有限流（可能返回 501 / 424）。代码已内置：

- 因子选股：串行抓取 + 失败重试 + 本地库兜底
- 批量同步：每只之间加间隔
- 实时行情：换用不同的腾讯端点，与日线互不影响