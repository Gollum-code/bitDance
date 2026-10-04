# bitDance

> 基于 vn.py 开发的量化交易系统（量化研究、回测与交易服务实践项目）

## 项目简介

`bitDance` 是一个以 **Python + vn.py** 为核心、并结合 **FastAPI** 与 **Vue 3 + Vite** 的量化交易实践项目。  
项目包含策略研究与回测示例、后端 API 服务、前端可视化页面等模块，适合用于：

- 量化策略学习与验证
- 交易系统原型开发
- 前后端联调与功能扩展

## 技术栈

- **量化/后端**：Python、vn.py、FastAPI、Uvicorn、SQLite
- **前端**：Vue 3、TypeScript、Vite、Tailwind CSS、ECharts
- **测试/持续集成**：pytest（后端接口 + 回测引擎）、GitHub Actions

> 仓库以 Python 为主（约 150 个 `.py`），前端 Vue/TS 约 40 个文件，另含策略改写清单 CSV 与少量 Notebook 示例。

## 仓库结构（按当前项目整理）

```text
bitDance/
├─ README.md
├─ start-all.ps1                          # 一键启动脚本（前端 + 8080 + 8000）
├─ .github/workflows/ci.yml               # CI：后端/回测/前端 三 job
├─ trader/                                # 交易与策略服务（FastAPI 8000）
│  ├─ main.py                             # 服务入口，注册 /strategy /chat /api/market
│  ├─ routers/
│  │  ├─ free_market.py                   # 免费行情源（腾讯公开接口，免 token）
│  │  ├─ market_data.py                   # 行情 API，DATA_SOURCE 切换 free/tushare
│  │  ├─ tushare_bars.py / tushareStaticsUploud.py  # 写入 vn.py 数据库 / CSV 导入
│  │  ├─ chooseStrategy.py                # /strategy/list、/strategy/{id}（回测）
│  │  └─ chat.py                          # Kimi 智能助手（Moonshot API）
│  ├─ examples/cta_backtesting/           # ★ 策略改写与回测模块
│  │  ├─ rewritten_strategies/            # 23 个族策略 + manifest.csv + 工具函数
│  │  └─ run_rewritten_strategy_backtest.py
│  └─ tests/                              # 回测引擎 pytest（7 个用例）
└─ bitDance_Object/
   ├─ package.json                        # 前端依赖与脚本
   ├─ vite.config.ts                      # 代理：/strategy /chat /api/market→8000，/api→8080
   ├─ src/                                # Vue 3 页面与组件
   └─ backend/
      ├─ main.py                          # 业务后端服务入口（8080，约 25 个 API）
      ├─ requirements.txt                 # 后端 Python 依赖
      ├─ tests/                           # 接口冒烟测试 pytest（4 个用例）
      └─ README.md                        # 后端模块说明
```

## 主要模块说明

### 1) trader 服务（`trader/main.py`）

- 使用 FastAPI 启动 API 服务（默认 `0.0.0.0:8000`）
- 已注册路由：
  - `/strategy/list`、`/strategy/{id}`：策略清单与真实 vn.py 回测
  - `/chat/*`：Kimi 智能对话（需 `MOONSHOT_API_KEY`）
  - `/api/market/*`：行情（股票列表/日线/分钟线/同步 vn.py）
  - `/upload/csv`：tushare 格式日线 CSV 导入 vn.py 数据库
- 行情数据源通过 `DATA_SOURCE` 切换：`free`（默认，腾讯公开接口免 token）或 `tushare`（付费，需 token）

### 2) 对象化前后端模块（`bitDance_Object`）

#### 前端

- `npm run dev` 启动 Vite 开发服务（默认 `http://localhost:5173`）
- `vite.config.ts` 中已配置开发代理：`/strategy`、`/chat`、`/api/market` → `http://localhost:8000`（trader），`/api` → `http://localhost:8080`（业务后端）

#### 后端

- 基于 FastAPI + SQLite（数据库默认文件 `bitDance_Object/backend/data/app.db`）
- 提供完整业务 API：
  - 认证：`POST /api/auth/register`、`POST /api/auth/login`、`GET /api/auth/me`
  - 会员：`POST /api/membership/upgrade-demo`（演示开通，非会员仅放行首个策略与限制 AI 问答）
  - 社区：帖子/点赞/评论（`/api/community/*`）
  - 回测：`/api/backtest/*`（转发 trader 8000 真实 vn.py 回测引擎，带会员门禁）
  - 聊天：`/api/chat/*`（转发 trader 8000 Kimi 对话，会员专用）
  - 行情 CSV 上传：`/api/tusharestaticsupload/upload/csv`

### 3) 回测示例与策略改写

- `trader/ai/tests/cta_backtesting/README.md` 提供了 CTA 日线回测最小可运行示例与参数说明
- `trader/examples/cta_backtesting/` 是**策略改写与回测**模块：
  - `rewritten_strategies/family_*.py`（23 个）：把聚宽平台 99 份模板**去重改写**为 vn.py `CtaTemplate` 策略族
  - `rewritten_strategies/_family_helpers.py`：族策略公共指标库（zscore/RSRS/KDJ/GFTD/ATR 等）
  - `rewritten_strategies/manifest.csv`：99 份模板 → 族策略类 + 默认参数的映射
  - `rewritten_strategies/_archived_v1/`：早期一次性生成的 100 份近似重复策略（已归档）
  - `run_rewritten_strategy_backtest.py`：按 manifesto 加载族策略并回测的引擎入口
- 策略来源模板：`D:\量化交易\量化投资策略源码模型多因子短线量化交易策略方法分析电子版模板\量化投资策略源码模型多因子短线量化交易策略方法分析电子版模板\量化策略代码(99份)\`（聚宽社区 99 份 `.txt`）

> **注意**：原始 33 份"向导式"模板是同一套聚宽向导框架的参数化副本，改写时已归并为
> `FamilyWizard` 一个族；其余 66 份按所选策略逻辑（均线/MACD/RSRS/布林/海龟/机器学习等）
> 归类为各自独立的族策略，避免"复制粘贴同一段模板"。

## 快速开始

> 建议使用 Python 3.10+ 与 Node.js 18+。

### 一键启动（推荐）

Windows 下在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-all.ps1
```

脚本会自动：
1. 检查并安装前端依赖（`npm install`）
2. 启动后端服务（`bitDance_Object/backend`，端口 8080）
3. 启动 trader 服务（`trader/main.py`，端口 8000）
4. 启动前端 Vite（端口 5173）
5. 健康检查并打印各服务地址

启动完成后打开 `http://localhost:5173` 即可。

### 手动分步启动

### A. 启动 `bitDance_Object` 后端（8080）

在 `bitDance_Object/backend` 目录执行：

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### B. 启动前端（Vite）

在 `bitDance_Object` 目录执行：

```bash
npm install
npm run dev
```

前端开发环境会将 `/api` 请求代理到 `http://localhost:8080`。

### C. 启动 trader 服务（8000）

在仓库根目录（或 `trader` 目录）按你的环境执行：

```bash
python trader/main.py
```

启动后默认监听：`http://0.0.0.0:8000`

### D. 数据源（免费 vs TuShare）

`trader/routers/market_data.py` 支持两种行情数据源，通过环境变量 `DATA_SOURCE` 切换：

| 数据源 | 环境变量 | 说明 |
|--------|---------|------|
| `free`（默认） | 无需配置 | 腾讯公开行情接口（免 token/注册），股票列表 + 日线前复权，适合 demo 与 GitHub 展示 |
| `tushare` | `TUSHARE_TOKEN`（必填），可选 `TUSHARE_HTTP_URL` | TuShare Pro（付费/积分），数据更全 |

```bash
# 默认免费源（无需任何配置）
python trader/main.py

# 切换到 TuShare（需先在环境里设置 token）
set DATA_SOURCE=tushare
set TUSHARE_TOKEN=你的token
python trader/main.py
```

免费源实现：`trader/routers/free_market.py`（腾讯 `qt.gtimg.cn` / `web.ifzq.gtimg.cn`，带缓存与限速）。

## 首次运行：先准备行情数据

> **重要**：回测数据保存在 vn.py 的本地数据库中（`~/.vntrader/database.db`），**不在 Git 仓库里**。
> 因此全新克隆后必须先把日线导入本地库，否则回测会因为缺少 K 线而无法成交。

两种方式导入行情（任选其一）：

1. **页面操作（推荐）**：启动全部服务后打开 `http://localhost:5173`
   - 进入「行情」页搜索并打开一只标的（如 `600519.SH`）
   - 点击 **「同步日线到本地库」**，即可写入 vn.py 数据库
   - 也可点击 **「导入 CSV 日线」** 上传本地 tushare 格式日线文件
2. **命令行**：`POST /api/market/sync-vnpy`，或直接用 `tushare_bars.py` 的工具函数写入

配置完成后，到「我的策略」页选择策略与标的即可运行回测。

## 回测与研究

- 策略研究建议优先通过 Notebook 与脚本进行迭代
- 回测示例参考：`trader/ai/tests/cta_backtesting/README.md`
- 策略改写与回测：`trader/examples/cta_backtesting/run_rewritten_strategy_backtest.py`
- 实盘前请完成：
  - 手续费/滑点建模
  - 参数稳健性检验
  - 风控规则验证（仓位、止损、风控阈值）

## 常见开发命令

```bash
# 前端
npm run dev
npm run build

# 后端（bitDance_Object/backend）
uvicorn main:app --reload --port 8080

# trader 服务（含真实回测引擎 /strategy/*）
python trader/main.py
```

## 测试与持续集成

项目配置了 **pytest** 测试与 **GitHub Actions** CI，每次 push 自动运行三个 job：

| Job | 内容 |
|-----|------|
| `python-backend` | 编译检查 + 后端 8080 接口冒烟测试（4 用例） |
| `python-trader` | 编译检查 + 回测引擎测试（7 用例） |
| `frontend` | `vue-tsc --noEmit` 类型检查 + `npm run build` |

本地运行测试：

```bash
# 后端接口冒烟测试（使用独立临时数据库，不污染开发数据）
cd bitDance_Object/backend
pip install -r requirements.txt
python -m pytest tests -q

# 回测引擎测试（需 vnpy + pandas）
python -m pytest trader/tests -q
```

> 后端测试通过 `BITDANCE_DB_PATH` 环境变量使用临时数据库；生产/开发默认使用 `bitDance_Object/backend/data/app.db`。


## 免责声明

本项目仅用于技术研究与学习交流，不构成任何投资建议。量化交易存在风险，实盘请谨慎。
