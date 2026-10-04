# 快速开始

bitDance 是一个基于 **vn.py + FastAPI + Vue 3** 的量化交易研究与回测系统，包含 23 个策略族、免费 A 股行情、组合回测与因子选股等分析工具。

## 1. 一键启动（推荐）

在仓库根目录（Windows PowerShell）执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-all.ps1
```

脚本会自动安装前端依赖并启动三个服务：

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| 业务后端 | 8080 | 用户/会员/社区/社区等业务 API |
| 交易服务 | 8000 | 真实 vn.py 回测引擎 + 行情 + AI |
| 前端 | 5173 | Vue 3 界面（浏览器打开此地址） |

## 2. 手动启动

```bash
# 后端 8080
cd bitDance_Object/backend
pip install -r requirements.txt
uvicorn main:app --port 8080

# 交易服务 8000（仓库根目录）
python trader/main.py

# 前端 5173
cd bitDance_Object
npm install
npm run dev
```

## 3. 首次使用：先准备行情数据

回测数据保存在 vn.py 的本地数据库（`~/.vntrader/database.db`），**不在 Git 仓库里**，全新克隆后需要先导入行情：

1. 打开 `http://localhost:5173` → 进入「行情」页
2. 搜索并打开一只标的（如 `600519.SH`）
3. 点击 **「同步日线到本地库」**

> 也可以在「行情」页点击「导入 CSV 日线」，上传 tushare 格式的日线文件
> （列：`ts_code,trade_date,open,high,low,close,vol,amount`）。

## 4. 页面导览

| 页面 | 路径 | 作用 |
| --- | --- | --- |
| 市场看板 | `/dashboard` | A 股自选股实时概览、涨跌榜 |
| 行情 | `/market` | 搜索标的、同步日线到本地库 |
| 个股日线 / 分时 | `/market/stock` | 日线 K 线与分钟分时图 |
| 我的策略 | `/strategies` | 选策略 + 填参数 + 运行回测 |
| 策略对比 | `/analytics/compare` | 多个策略并行回测，收益曲线叠加 |
| 因子选股 | `/analytics/screen` | 全市场多因子打分选股 |
| 参数优化 | `/analytics/grid` | 单参数网格扫描，收益/回撤对比 |
| 组合回测 | `/analytics/portfolio` | 多标的加权组合净值与风险指标 |
| 实时行情 | `/analytics/realtime` | WebSocket 实时快照推送 |
| 社区 | `/community` | 帖子、点赞、评论 |
| 文档中心 | `/docs` | 全部功能文档 |

## 5. 下一步

- 了解**策略族**如何从聚宽模板改写而来 → 见「策略与回测」
- 了解**分析工具**的用法 → 见「分析工具」
- 了解**数据源**配置（免费 / TuShare）→ 见「数据源」