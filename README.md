# bitDance

> **基于 vn.py 的量化交易研究与回测平台** —— 从策略研究、回测验证到组合分析的一站式实践项目。

## 项目简介

`bitDance` 以 **Python + vn.py** 量化引擎为核心，搭配 **FastAPI** 双服务与 **Vue 3 + TypeScript** 前端，构建了一个覆盖「**行情 → 策略 → 回测 → 分析 → 社区**」完整链路的量化交易实践系统。

### 核心能力

- **策略研究**：将聚宽社区 99 份策略模板去重改写为 **23 个 vn.py `CtaTemplate` 策略族**（均线 / MACD / RSRS / 布林 / 海龟 / 机器学习等），配套族参数映射与公共指标库
- **真实回测**：基于 vn.py `BacktestingEngine` 的日线回测，输出收益曲线、回撤、夏普、胜率、交易明细等完整指标
- **风险与风控**：独立风险模块（纯函数）补齐下行风险与尾部风险——索提诺 / Calmar / 溃疡指数 / 历史模拟法 VaR / CVaR / 偏度峰度 / 月度收益分布，配套**确定性风控闸门**（仓位 / 回撤 / VaR / 波动硬阈值逐条判定 + 一票否决）；参数寻优默认按夏普排序
- **多维分析**：多策略对比、因子选股、参数网格优化（单参数 + 双因子热力图）、组合回测、纸面交易、市场热力图
- **免费行情**：腾讯公开接口（免 token）提供全市场列表、日线、分钟线与实时快照，支持 TuShare 切换
- **智能辅助**：Kimi 驱动的回测报告生成、报告对比、AI 问答
- **社区生态**：帖子 / 点赞 / 评论，策略回测结果可一键分享
- **工程化**：GitHub Actions CI（后端 / 回测 / 前端三 job）、pytest 测试（62 用例，含 26 个风险模块单测）、一键启动脚本

### 技术栈

| 层 | 技术 |
| --- | --- |
| 量化引擎 | Python、vn.py、vnpy_ctastrategy |
| 后端服务 | FastAPI、Uvicorn、SQLite（双服务 8000 / 8080） |
| 前端 | Vue 3、TypeScript、Vite、Tailwind CSS、ECharts |
| 数据源 | 腾讯公开行情（免费）/ TuShare（可选） |
| 测试 / CI | pytest、GitHub Actions |

> 仓库规模：约 **149 个 Python 文件**、**27 个 Vue 组件**、**22 个前端路由**，含策略改写清单与完整文档。

## 仓库结构（按当前项目整理）

```text
bitDance/
├─ README.md
├─ start-all.ps1                          # 一键启动脚本（前端 + 8080 + 8000）
├─ .github/workflows/ci.yml               # CI：后端/回测/前端 三 job
├─ trader/                                # 交易与策略服务（FastAPI 8000）
│  ├─ main.py                             # 服务入口，注册 /strategy /chat /api/market /analytics
│  ├─ routers/
│  │  ├─ free_market.py                   # 免费行情源（腾讯公开接口，免 token）
│  │  ├─ market_data.py                   # 行情 API（日线/分钟线/批量同步），DATA_SOURCE 切换
│  │  ├─ tushare_bars.py / tushareStaticsUploud.py  # 写入 vn.py 数据库 / CSV 导入
│  │  ├─ chooseStrategy.py                # /strategy/list、/strategy/{id}（回测）
│  │  ├─ analytics.py                     # 多策略对比/因子选股/网格优化/组合回测/纸面交易/热力图/WS 推送
│  │  └─ chat.py                          # Kimi 智能助手（Moonshot API）
│  ├─ examples/cta_backtesting/           # ★ 策略改写与回测模块
│  │  ├─ rewritten_strategies/            # 23 个族策略 + manifest.csv + 工具函数
│  │  ├─ risk_metrics.py                  # ★ 风险/绩效指标库 + 确定性风控闸门（纯函数）
│  │  ├─ trade_analytics.py               # 逐笔成交/FIFO回合/信号质量/日度敞口
│  │  └─ run_rewritten_strategy_backtest.py
│  └─ tests/                              # 回测引擎 + 风险指标 + 分析功能 pytest
└─ bitDance_Object/
   ├─ package.json                        # 前端依赖与脚本
   ├─ vite.config.ts                      # 代理：/strategy /chat /api/market→8000，/api→8080
   ├─ src/                                # Vue 3 页面与组件（22 个路由）
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
  - `/analytics/*`：多策略对比、因子选股、参数网格优化、组合回测、纸面交易、市场热力图、实时行情（含 WebSocket 推送）
  - `/chat/*`：Kimi 智能对话（需 `MOONSHOT_API_KEY`）
  - `/api/market/*`：行情（股票列表/日线/分钟线/同步 vn.py/批量同步）
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
  - `risk_metrics.py`：风险与绩效指标库（见下节）
  - `trade_analytics.py`：逐笔成交、FIFO 回合、信号质量、日度敞口
  - `run_rewritten_strategy_backtest.py`：按 manifest 加载族策略并回测的引擎入口
- 策略来源：聚宽社区 99 份策略模板（`.txt`），改写清单见 `rewritten_strategies/manifest.csv`

### 4) 风险与绩效指标（`risk_metrics.py`）

vn.py 的 `calculate_statistics()` 只给出夏普和最大回撤，本模块补齐风险视角：

| 类别 | 指标 | 口径 |
|------|------|------|
| 收益 | 累计 / 年化收益 | 几何年化，年化 252 |
| 波动 | 年化波动率、年化下行波动率 | 日收益标准差 × √252 |
| 风险调整 | 夏普、索提诺、Calmar | 索提诺分母仅用下行波动 |
| 回撤 | 最大回撤、回撤持续天数、溃疡指数 | 溃疡指数 = √mean(回撤²) |
| 尾部 | VaR(95%)、CVaR(95%) | 历史模拟法，不假设正态分布 |
| 分布 | 偏度、超额峰度、日胜率、盈亏因子 | 识别"高夏普但负偏度"陷阱 |
| 仓位 | 最大 / 平均仓位占比、持仓天数占比 | 逐日 `end_pos × close × size / balance` |

配套**确定性风控闸门** `evaluate_risk_gate()`：仓位 / 回撤 / VaR / 年化波动 / 样本量逐条布尔判定，
任一不过即 `REJECT`（一票否决），拒绝原因逐条返回便于审计。

> **退化序列保护**：若样本期内几乎没有成交（如 400 天仅 1 笔），权益曲线几乎全平，
> 日收益只剩浮点噪声（~1e-10），直接计算会得到夏普 -1291 万这类无意义数值。
> 模块通过「日波动下限 + 有效交易天数占比」双重判定标记 `degenerate`、将比率归零，
> 并拒绝其通过风控闸门——避免"没交易"被误判成"零风险、安全"。

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
| `python-trader` | 编译检查 + 回测引擎 + 风险指标测试（62 用例，含 26 个风险模块单测 + 11 个组合合成单测） |
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

## 复现组合业绩

`scripts/collect_portfolio_metrics.py` 可独立运行：库中缺少标的或数据覆盖不足时，会自动从腾讯公开源分段拉取真实前复权日线并写入本地库（幂等，已满足则跳过）。

```bash
# 1) 体检本地行情，可选：修复坏数据 / 全量重拉
python scripts/repair_market_data.py --dry-run
python scripts/repair_market_data.py --all

# 2) 8 标的等权组合回测 + 每日再平衡基准（缺数据会自动同步）
python scripts/collect_portfolio_metrics.py

# 3) 离线模式：只用本地已有数据，不访问网络
python scripts/collect_portfolio_metrics.py --no-sync
```

脚本会为每个标的打印 `SYNCED`（本次拉取）或 `CACHED`（本地已满足），并输出每个标的的目标名义金额、换算股数与期初价，便于核对权重是否真等权。


## 免责声明

本项目仅用于技术研究与学习交流，不构成任何投资建议。量化交易存在风险，实盘请谨慎。
