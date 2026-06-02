# AGENTS.md — China Housing Monitor (CHM)

## What this is

A modular Python data pipeline that:
1. Manages a local SQLite DB (`china_monitor_db.sqlite`) with 8 tables of Chinese housing market data for 34 cities (v0.8, expanded from 18)
2. Scrapes Lianjia for real-time listing counts and prices, with a mathematically-documented fallback when blocked
3. Computes a multi-factor "Bottom Signal Score" (0-100) per city per month
4. Compiles everything into a standalone single-file HTML SPA (`chm.html`) with all data injected as `window.MONITOR_DB`

No dependencies beyond Python 3 standard library. No package.json, no requirements.txt, no venv.

## Commands

```bash
# Run the full pipeline: init DB, scrape 34 cities, compute scores, compile HTML
python3 -m china_housing_monitor

# Skip scraping, just regenerate HTML from existing DB
python3 -m china_housing_monitor --no-scrape

# Only initialize/seed the database
python3 -m china_housing_monitor --init-only

# Run the verification test suite (31 tests, uses a copied test DB — safe for production)
python3 scratch/verify_scoring_rigor.py

# Start local HTTP server for preview
python3 -m http.server 8080 --directory /Users/george/WorkBuddy/CHM
```

There is no lint, typecheck, formatter, or CI configured. Run tests manually after changes.

## Architecture

```
china_housing_monitor/                  ← Python package (v2.0.0)
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
2. **自我反思**：记录 corrections.md + reflections.md + memory.md（self-improving skill）
3. **坑典更新**：将踩过的坑写入项目 `PITFALLS.md`
4. **文档同步**：更新 `ARCHITECTURE.md` / `.workbuddy/memory/MEMORY.md` 等项目文档
5. **验证**：运行 lint/test，确认模板和 chm.html 同步
6. **确认下一步**：询问 commit / 继续 / 结束

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
- 新增「告一段落」触发词工作流（全局 self-improving memory + AGENTS.md）
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
