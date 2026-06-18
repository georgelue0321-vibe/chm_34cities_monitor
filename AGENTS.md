# AGENTS.md — China Housing Monitor (CHM)

## What this is

A modular Python data pipeline that:
1. Manages a local SQLite DB (`china_monitor_db.sqlite`) with 8 tables of Chinese housing market data for 34 cities (v0.8, expanded from 18)
2. Scrapes Lianjia for real-time listing counts and prices, with a mathematically-documented fallback when blocked
3. Computes a multi-factor "Bottom Signal Score" (0-100) per city per month
4. Compiles everything into a standalone single-file HTML SPA (`chm.html`) with all data injected as `window.MONITOR_DB`

No dependencies beyond Python 3 standard library. No package.json, no requirements.txt, no venv.

## Prerequisites

**Core pipeline** (init, score, compile HTML):
- Python 3.11+
- No external dependencies

**Data collection** (optional, for real-time updates):
- [browser-use](https://github.com/browser-use/browser-use) CLI: `pip install "browser-use[core]"`
- Chrome/Chromium with remote debugging enabled
- **Must use `--headed` mode** for all browser-use commands (百度、央行、中指研究院会拦截 headless)

```bash
# Verify browser-use installation
browser-use doctor

# Test headed mode
browser-use --headed open "https://www.baidu.com"
```

For detailed setup, see `skills/storage-event-scanner/SKILL.md`.

## Commands

```bash
# Run the full pipeline: init DB, scrape 34 cities, compute scores, compile HTML
python3 -m china_housing_monitor

# Skip scraping, just regenerate HTML from existing DB
python3 -m china_housing_monitor --no-scrape

# Only initialize/seed the database
python3 -m china_housing_monitor --init-only

# Run the verification test suite (31 tests, uses a copied test DB — safe for production)
python3 tests/test_scoring_rigor.py

# Start local HTTP server for preview
python3 -m http.server 8080
```

## Architecture

```
china_housing_monitor/                  ← Python package (v1.0.0)
├── __init__.py                         ← Package init, version
├── __main__.py                         ← CLI entry point (argparse)
├── compat.py                           ← Backward compatibility shim for tests
├── config.py                           ← Constants, paths, city definitions, scoring params
├── crawler.py                          ← Lianjia scraper with SSL bypass + fallback chain
├── db/
│   ├── __init__.py
│   ├── init.py                         ← init_db(), backup_db(), add_column_if_not_exists()
│   └── seed.py                         ← seed_historical_data() — NBS, transaction, storage, opinions
├── scoring/
│   ├── __init__.py
│   ├── factors.py                      ← Scoring helpers: calc_s_price, storage_recency, PBOC mapping
│   └── bottom.py                       ← compute_bottom_score, generate_warnings, decide_city_status_timeline
├── data/
│   ├── __init__.py
│   ├── payload.py                      ← fetch_data_payload() — assembles full JSON payload from SQLite
│   └── charts.py                       ← Chart helpers: visibility, evidence grade, signal interpretation
└── report/
    ├── __init__.py
    ├── generator.py                    ← generate_html_report() — reads templates, injects data
    ├── static/
    │   ├── style.css                   ← Custom CSS (scrollbars, transitions, nav)
    │   ├── nav.js                      ← Navigation: toggleNavMobile, onCityChange, updateNavButtons
    │   ├── gauge.js                    ← renderNationalGauge — PBOC radial bar charts
    │   ├── rankings.js                 ← renderRankings — city ranking list
    │   ├── charts.js                   ← NBS index, transaction, score history, scraped charts
    │   └── dashboard.js                ← renderCityDashboard — main city detail view
    └── templates/
        ├── base.html                   ← HTML skeleton, footer, script tags
        ├── header.html                 ← Header/navbar with city tier navigation
        ├── left_column.html            ← Storage events + rankings
        └── right_column.html           ← City details, scoring factors, signal interpretation

china_monitor_db.sqlite                 ← The database (gitignored)
chm.html                                ← Generated output, open directly in browser
scratch/verify_scoring_rigor.py         ← Test suite (31 tests)
```

## Module dependency graph

```
__main__.py
    ├── config
    ├── db.init
    ├── crawler
    └── report.generator
            ├── config
            ├── data.payload
            │       ├── config
            │       ├── scoring.factors
            │       ├── scoring.bottom
            │       └── data.charts
            └── (reads templates/ + static/ files)

compat.py (test shim)
    ├── config
    ├── db.init
    ├── db.seed
    ├── scoring.factors
    ├── scoring.bottom
    ├── crawler
    ├── data.payload
    ├── data.charts
    └── report.generator
```

## Critical gotchas

- **`init_db()` is destructive**: It runs `DROP TABLE IF EXISTS` on most tables, then re-seeds from hardcoded data. Only `storage_events` is preserved via migration logic.

- **`current_month` is resolved dynamically** via `resolve_current_month(conn)` in `scoring/factors.py`. Falls back to latest month in `city_price_index_monthly` (official/scraped) or current system month.

- **`last_updated` uses actual crawl timestamp**: Queried from `data_quality_log.MAX(collected_at)`, not the NBS month.

- **Crawler uses `ssl._create_unverified_context()`** in `crawler.py` to bypass macOS certificate errors. This is intentional.

- **HTML templates use `{{PLACEHOLDER}}` syntax**: The templates in `report/templates/` use Python string replacement. The JS/CSS files use normal `{` `}` (no escaping needed).

- **Test DB isolation**: The test suite copies the production DB to `scratch/test_monitor_db.sqlite` before mutating it. It patches `config.DB_PATH` at runtime.

- **Text content must be directly quoted**: `professional_opinions.consensus`、`storage_execution_events.details` 等文字字段，必须引用原始来源（券商研报、政府公告）原文，**禁止 AI 生成或总结**。数据字段（价格、环比、同比）可从 API 获取，但分析文字必须有可查证的原始出处。

## Monthly data workflow

### 月中指数据提取（每月一次）
**时机**: NBS 70城数据发布后（通常每月18日前后）

**步骤**:
1. 用 `browser-use --headed` 打开 https://www.cih-index.com/data/index/esfHouse.html
2. 提取34城二手住宅数据（均价、环比、同比）
3. **只更新已有链家数据的城市/月份**，不插入新行（避免 listings = -1）
4. 导入 `market_index` 表，`source_label='中指研究院'`
5. 可用 MoM% 反推上月价格：`prev_price = curr_price / (1 + mom/100)`

**数据格式**:
```python
# 每城市: (价格, 环比%)
data = {
    'bj': (62090, -0.38),  # 北京
    'sh': (55173, 0.13),   # 上海
    # ...
}
```

**导入逻辑**:
```python
# 只更新价格，不覆盖挂牌量
cur.execute("""
    UPDATE market_index 
    SET price_sqm = ?, source_label = '中指研究院', data_status = 'official'
    WHERE city_id = ? AND date = ?
""", (price, cid, current_month))
```

**注意**: 
- 中指数据不直接影响评分（评分用NBS），主要用于展示和交叉验证
- 不要用 INSERT OR REPLACE，会覆盖链家挂牌量数据

## Data model key tables

| Table | Purpose |
|---|---|
| `cities` | 34 cities with pinyin ID, Chinese name, tier level, PBOC quota (v0.8) |
| `pboc_global` | PBOC re-lending facility progress timeline |
| `market_index` | Scraped Lianjia data: listings count + avg price per city/month |
| `storage_execution_events` | Gov.cn-verified state-owned enterprise acquisition events |
| `professional_opinions` | Brokerage research consensus per city |
| `city_price_index_monthly` | NBS 70-city official price index (MoM/YoY) |
| `city_transaction_monthly` | Official municipal housing bureau transaction volumes |
| `data_quality_log` | Audit trail: `official/scraped/estimated/missing/demo` per metric |
| `bottom_score_monthly` | Pre-computed scores, statuses, drivers, explanations |
| `pboc_global` | PBOC re-lending facility progress timeline |

## Scoring system summary

- **Low-Data Mode (BSS_LOW_DATA_V1)**: 3 factors only
  - S_Price (60%): NBS resale home MoM 3-month average + continuity
  - S_Storage (30%): Storage event stage × recency decay
  - S_PBOC (10%): PBOC usage percentage mapped to 0-100 score
- **Validation gates** (not in score, only cap status): Transaction, Listing, Inventory
- **Status tiers**: `下跌通道` → `政策底观察` → `价格止跌观察` → `政策价格共振` → `底数据强信号观察`
- **Evidence grades**: A/B/C/D/E based on signal coverage, validation coverage, data quality
- **PBOC stale cap**: If PBOC data >6 months old, pboc_score capped at 30, evidence_grade capped at C

## Warnings system

Warnings are generated by `scoring/bottom.py::generate_warnings()` and displayed in the dashboard:

| Type | Style | Trigger |
|------|-------|---------|
| `info` | Gray | Storage at policy/recruitment stage |
| `caution` | Amber | PBOC low, inventory surge |
| `warning` | Red | Data missing, price-volume divergence |
| `positive` | Green | Storage at signing/execution stage |

## Conventions

- All UI text is Chinese (zh-CN). Keep comments, variable names, and output in English where they already are.
- City IDs are lowercase pinyin abbreviations (34 cities v0.8): `bj`, `sh`, `sz`, `gz`, `cd`, `cq`, `hz`, `wh`, `xa`, `nj`, `tj`, `cs`, `hf`, `zz`, `xm`, `qd`, `nb`, `fz`, `ty`, `hhht`, `sy`, `cc`, `hrb`, `hfc`, `nc`, `jn`, `zzz`, `nn`, `hk`, `gy`, `km`, `lz`, `yc`, `xn`
- Storage event stages in order of weight: `政策表态(10)` → `房源征集(25)` → `正式招标(45)` → `成交公示(70)` → `签约收购(90)` → `改造完成/配租配售(100)`
- Data quality statuses: `official` > `scraped` > `estimated` > `demo` > `missing`/`abnormal`
- Stock market color convention: up (positive) = red, down (negative) = green

## What NOT to do

- Don't add pip dependencies — the project is intentionally zero-dependency
- Don't run `init_db()` in isolation expecting data to persist — it drops and re-seeds
- Don't insert mock/test data into the production DB without marking it `demo` in `data_quality_log`
- Don't modify `storage_events` schema — it's the legacy table; use `storage_execution_events`
- Don't hardcode URLs that aren't verified gov.cn portals
- Don't import from `china_housing_monitor` package directly — use the specific submodule

## Agent Workflow

### 「告一段落」触发词
当用户说"告一段落"时，主动执行收尾流程，无需用户提醒：
1. **回顾总结**：简要列出本轮完成的所有变更
2. **坑典更新**：将踩过的坑写入项目 `PITFALLS.md`
3. **验证**：运行测试，确认模板和 chm.html 同步
4. **确认下一步**：询问 commit / 继续 / 结束

## Changelog

### v2.0.0 (2026-05-31) — Modular Refactor

**Structure:**
- Split monolithic `china_housing_monitor.py` (3464 lines) into 14 Python modules
- Extracted HTML template into 4 template files + 6 JS files + 1 CSS file
- Created CLI entry point with argparse (`--no-scrape`, `--init-only`, `--month`)

**Data:**
- Added `professional_opinions` table with 18 city-specific brokerage consensus
- `last_updated` now uses actual crawl timestamp from `data_quality_log`
- PBOC quarter increase shows "-" when data is stale (not misleading old data)
- Signed cities count changed from 5 to 11 (all cities with any storage event)

**UI/Layout:**
- Renamed "楼市假底信号实时预警" → "底部信号实时评估"
- Removed icon next to title
- Changed "20城" → "18城" throughout
- Compact nav: green dot for storage cities, active city always shown first
- Compact nav button: mobile only, PC shows "点击展开全部 18 城" hint
- City details: Layout A (name row + gauge+params row + consensus + drivers + collapsible disclaimer)
- Signal interpretation: replaced validation matrix + evidence coverage with actionable insights
- NBS chart: transformed to deviation from 100% with 0% reference line
- Transaction chart: 0/null values shown as gaps, not data points
- Storage warnings: based on actual stage, not score threshold
- Footer: data sources, disclaimer, system info, George Lue link
- Chart titles: added data source attribution (NBS, 住建局, 链家/贝壳)

**Color scheme:**
- Ranking change arrows: red = up, green = down (stock market convention)
- Signal interpretation: white text, colored icons only
- Positive storage warning: green style

### v0.8 (2026-06-01) — 34城扩展 + ECharts地图 + 收储扫描器

**数据扩展：**
- 16 新增城市: 太原/呼和浩特/沈阳/长春/哈尔滨/合肥/福州/南昌/济南/郑州/长沙/南宁/海口/贵阳/昆明/兰州/银川/西宁（实际 18 城，含之前的银川/西宁）
- NBS CSV 导入: 从 `nbs_70city_full_202401_202604.csv` 导入 16 城 × 28 月 = 448 条
- Lianjia 爬虫扩展: `LIANJIA_CITY_PREFIXES` 覆盖 34 城
- 专业意见种子数据: 34 城券商共识

**新功能：**
- ECharts 地图模块 (`map.js` + `china.json` GeoJSON 582KB)：34 城散点图，蓝色强信号点
- 收储事件扫描器 Skill：浏览器搜索 + 智能去重 + 6 阶段分类 + 来源优先级验证
- 34 城全景扫描：774 事件发现，688 新导入

**UI：**
- 标题/导航/页脚 "18城" → "34城"，版本 "v0.8"
- 布局：地图 8 列 + 温度板 4 列（2:1 比例）
- 省份标签隐藏，悬停效果禁用

**Bug 修复：**
- `init_db()` hash 冲突修复（福州重复事件）
- `storage_recency_multiplier()` 空日期守卫
- `month_diff()` 空字符串守卫

### v2.0.1 (2026-05-31) — UI/UX 优化

**移动端布局重构：**
- 单容器 `grid grid-cols-1 lg:grid-cols-12`，使用 `order-*` 同时控制移动端和桌面端视觉顺序
- 移动端模块排序：温度板→城市详情→评分因子→收储追踪→信号评估→图表→排行榜
- 城市详情 grid: `grid-cols-5` → `grid-cols-3 sm:grid-cols-5`，底部信号块 `row-span-2`

**Tooltip 优化：**
- NBS 图表：移除"价格持平"基准线标签，改为 hover 显示"价格上涨/下跌/持平"
- 底部信号径向图：hover 区域扩大至整个 div，添加深色背景 tooltip
- 四个参数框：添加动态解释 tooltip（观察状态/风险等级/信号强度/数据可信度），根据实际值显示具体含义

**文字修复：**
- "二线核心核心城" → "二线核心城"（判断 `level === "二线核心"` 时避免重复）
- 负面指标文案区分：收储执行→收储执行不力，价格止跌确认→价格止跌未确认，全国资金温度→全国资金温度不足
- `__init__.py` "20城" → "18城"

**Agent 规范：**
- 新增「告一段落」触发词工作流（AGENTS.md）
- 坑典 PITFALLS.md 新增 #15-18

### v2.0.2 (2026-06-02) — Mobile UI + Footer Date

**导航优化：**
- 二线核心城市 nav 从 `overflow-x-auto` 横滑改为 `flex-wrap` 折行，展示所有城市

**移动端修复：**
- Safari 左滑空白：添加 `html, body { overflow-x: hidden; max-width: 100vw; }`

**Footer 日期：**
- Header 移除「数据基准期」标签
- Footer 新增「下次更新: 2026-06-08」（每周一更新）
- 基准期 = 爬虫日期 - 1 天（凌晨跑的数据归属前一天）
- Payload 新增 `next_update` 字段，自动计算下一个周一

### v0.9 (2026-06-04) — NBS 数据扩展 + 房价走势图 + Remotion 视频

**NBS 数据扩展：**
- 通过东方财富 API 拉取 34 城 2023-05/06 起的完整数据（35~36 个月）
- 新增 264 条记录（2023-05~2023-12 + 2025-02 缺失月），DB 更新 949 条
- 11 城（bj/sh/nj/xm 等）NBS 从 2023-06 起有数据（名单扩容）

**新产出：**
- `cd_price_trend.html`：34 城二手房价格走势全景页面（ECharts）
  - 累计涨跌排名表（带可视化条形图）
  - 34 线走势图（底部 5 城红/顶部 5 城绿高亮，筛选标签）
  - 以 2023-06=100 为基准链式计算累计指数
- `bar-chart-race/`：Remotion 视频项目
  - 34 城柱形竞赛动画 MP4（1080×720, 30fps, 35s）
  - 带钢琴曲 BGM（Kevin MacLeod - Slow Burn）
  - 标题/副标题/X轴/百分比样式优化

**工具链：**
- 安装 SkillHub CLI（`~/.local/bin/skillhub`）
- 安装 `remotion-video-toolkit` skill（`.opencode/skills/`）
- Pitfalls 新增 #39~#42（ffmpeg 音量、@remotion/media、下载防盗链、SkillHub 路径）

### v0.9.1 (2026-06-06) — 浅色主题 + 字体放大 + NBS 去重

**UI：**
- 全局字体放大 +2px：`text-[8px]`→`[10px]`...`text-xs`→`text-sm`，移动端 14→15px
- 浅色主题：CSS 变量 + `[data-theme="light"]` 覆盖 Tailwind class，Header 添加 🌙/☀️ 切换按钮
- `localStorage('chm_theme')` 持久化，`<head>` 内同步初始化防闪烁
- 暗色模式零改动：保留原始 Tailwind class，浅色通过 CSS 高优先级覆盖实现
- ApexCharts/ECharts 动态主题：`getThemeColors()` 读取 `data-theme`，切换时 destroy+re-render

**Bug 修复：**
- `factors.py` 评分查询加 `GROUP BY month`：修复 EASTMONEY_API + NBS_70CITY 双 source 导致的 NBS 数据重复，`calc_s_price` 的 `series[-6:]` 索引错乱
- 坑典新增 #43（浅色主题不要改暗色）、#44（NBS 重复数据）

**数据变化：**
- EASTMONEY_API 导入了 2023-06~2023-12 + 2026-04 额外月份，所有城市 `price_score` 上浮
- 上海：63.8→86.0（2026-03→2026-05），因签约收购事件 + 价格因子上浮

### v0.9.2 (2026-06-07) — 浅色主题完整适配

**图表主题适配：**
- `charts.js` 新增 `getThemeColors()` helper，返回 15 个主题色变量
- 4 个 ApexCharts 图表（NBS/交易/评分历史/挂牌）全部适配：grid/axis/tooltip/annotation
- `map.js` 新增 `getMapThemeColors()` + 区域色块（7 大区域微色调）+ `rerenderMapForTheme()`
- ECharts 地图省份区域色块：华北蓝/东北紫/华东绿/华中黄/华南橙/西南青/西北暖灰

**JS 动态 class 适配：**
- `dashboard.js` 新增 `getDashboardTheme()`：状态 badge/径向图/警告卡片/时间轴 stage badge
- `rankings.js` 新增 `getRankingsTheme()`：排行榜行/排名 badge/状态 badge
- 所有状态色浅色模式使用 `bg-xxx-100 text-xxx-800` 确保 WCAG AA 对比度 ≥4.5:1

**CSS 补全：**
- body 背景/文字、焦点状态、模态框五维状态、toast、地图入口标签、导航边框
- 温度板 badge 专用 class：`.badge-inferred`（反推）、`.badge-frozen`（冻结）
- 坑典新增 #45-48（Tailwind `/` class、ECharts tooltip、主题切换、对比度）

**UI/UX Pro 指导：**
- 主动加载 ui-ux-pro-max skill 获取 WCAG 对比度指导
- 浅色模式文字用 `text-xxx-700/800` 替代 `text-xxx-500/600`

### v0.9.3 (2026-06-07) — 移动端图表区+footer排版优化

**图表区排版：**
- Header 布局：标题+图例从单行改为 `flex-col`（移动端）→ `sm:flex-row`（桌面端）
- 图例指示器：从裸线条改为 pill badge 样式（`.chart-legend-badge`），线条加宽到 `w-2.5`
- 横屏提示：从内联灰色文字改为琥珀色高亮 badge（`.chart-legend-hint` + 呼吸动画），仅移动端显示
- 图表标题：`items-start` 移动端顶部对齐，`flex-1 min-w-0` 包裹长标题
- 图表高度：`h-52` → `h-44 sm:h-52`，移动端更紧凑

**Footer 系统信息：**
- 每个信息项改为独立 pill tag（`.footer-sys-tag`），移动端自然换行
- `·` 分隔符仅桌面端显示（`hidden sm:inline`）
- "下次更新" 蓝色高亮（`bg-blue-900/30` + `text-blue-400`）

**竖排文字修复：**
- `writing-mode-vertical` 加 `white-space: nowrap` 防止微信浏览器换行
- 坑典新增 #57（竖排中文不要加 width: 1em）、#58（移动端多信息项用 pill tag）

## 收储事件扫描器 (storage-event-scanner)

### 功能
- 智能去重：识别同一事件的不同报道，只保留最权威来源
- 来源验证：验证URL可访问性，按优先级选择信息源
- 阶段分类：明确区分6个事件阶段
- 质量控制：记录来源可信度

### 使用方法

```bash
# 扫描单个城市
python3 skills/storage-event-scanner/scripts/scanner.py --city sy

# 扫描所有城市
python3 skills/storage-event-scanner/scripts/scanner.py --all

# 运行测试
python3 skills/storage-event-scanner/tests/test_deduplication.py
```

### 事件阶段权重

| 阶段 | 权重 | 说明 |
|------|------|------|
| 政策表态 | 10 | 政府文件、方案、通知 |
| 房源征集 | 25 | 征集公告、招标 |
| 正式招标 | 45 | 招标公告、采购 |
| 成交公示 | 70 | 中标、成交公示 |
| 签约收购 | 90 | 签约、签署协议 |
| 改造完成 | 100 | 竣工、交付、配租配售 |

### 信息源优先级

| 优先级 | 来源类型 |
|--------|----------|
| 100 | 政府官网 |
| 90 | 官方微信 |
| 80 | 国家媒体 |
| 70 | 地方媒体 |
| 60 | 行业媒体 |
| 50 | 其他 |
