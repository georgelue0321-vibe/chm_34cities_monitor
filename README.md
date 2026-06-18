# 🏛️ 全国核心34城楼市"底部信号"智能监测终端

> **China Core 34 Cities Property Bottom Signal Terminal**
>
> 本项目是为**广大持币或待持币的普通人**打造的楼市底部信号监测工具，帮助他们在低价甚至底价买到心仪的房子。系统深度融合了中国人民银行（PBOC）保障性住房再贷款额度追踪、微观地方国企收储招标事件、主流券商与顶投机构研判共识，以及高频更新的挂牌基本面数据，形成一套完整的"收储防线"研判与决策辅助工具。

---

## 📂 1. 项目文件组成

```
china_housing_monitor/              ← Python 包 (v1.0.0)
├── __init__.py                     ← 包初始化
├── __main__.py                     ← CLI 入口 (argparse)
├── config.py                       ← 常量、路径、34城定义、评分参数
├── crawler.py                      ← 链家爬虫 + SSL 绕过 + Smart Fallback
├── db/
│   ├── init.py                     ← init_db(), 表迁移
│   └── seed.py                     ← 历史数据播种 (NBS/交易/收储/券商共识)
├── scoring/
│   ├── factors.py                  ← 评分因子: calc_s_price, storage_recency
│   └── bottom.py                   ← compute_bottom_score, generate_warnings
├── data/
│   ├── payload.py                  ← fetch_data_payload() 组装 JSON
│   └── charts.py                   ← 图表辅助: visibility, evidence grade
└── report/
    ├── generator.py                ← generate_html_report() 编译 HTML
    ├── static/                     ← JS (nav/gauge/charts/dashboard) + CSS
    └── templates/                  ← HTML 模板 (base/header/left/right)

skills/storage-event-scanner/       ← 收储事件智能扫描器
├── scripts/                        ← 扫描/去重/阶段分类/来源验证/入库
├── templates/                      ← 来源优先级配置
└── tests/                          ← 去重测试

tests/                              ← 测试套件
├── test_scoring_rigor.py           ← 评分验证测试 (31 项)
└── test_monitor_db.sqlite          ← 测试用临时 DB (gitignored)

china_monitor_db.sqlite             ← SQLite 数据库 (gitignored)
chm.html                            ← 生成的 SPA 仪表盘 (gitignored)
```

---

## 🌐 2. 核心特性

### 📊 BSS_LOW_DATA_V1 低数据评分模型
- **S_Price (60%)**：NBS 二手住宅价格环比 3 个月均值 + 连续性
- **S_Storage (30%)**：收储事件阶段 × 时间衰减
- **S_PBOC (10%)**：央行再贷款使用率映射 0-100
- **状态层级**：`下跌通道` → `政策底观察` → `价格止跌观察` → `政策价格共振` → `底数据强信号观察`
- **Evidence Grade**：A/B/C/D/E 五档，基于信号覆盖、数据质量、验证覆盖

### 🗺️ 34城覆盖
- **一线 (4)**：北京、上海、深圳、广州
- **新一线 (12)**：成都、重庆、杭州、武汉、西安、南京、天津、长沙、合肥、郑州、厦门、青岛
- **二线核心 (18)**：太原、呼和浩特、沈阳、长春、哈尔滨、福州、南昌、济南、南宁、海口、贵阳、昆明、兰州、银川、西宁、石家庄、乌鲁木齐、惠州

### ⚡ 单文件零延迟 SPA
- Python 编译引擎将 SQLite 全量数据注入 `window.MONITOR_DB`
- 城市切换完全在浏览器内存中运行，微秒级响应
- ECharts 地图 + ApexCharts 图表 + 动态径向仪表盘

### 🔍 收储事件智能扫描器
- 智能去重：识别同一事件的不同报道，保留最权威来源
- 来源验证：按政府官网 > 官方微信 > 国家媒体 > 地方媒体优先级
- 6 阶段分类：政策表态 → 房源征集 → 正式招标 → 成交公示 → 签约收购 → 改造完成

---

## 🗄️ 3. 数据库表结构

| 表名 | 用途 |
|------|------|
| `cities` | 34 城市基础信息 (ID/名称/能级/PBOC 额度) |
| `market_index` | 链家爬取数据: 挂牌量 + 均价 |
| `storage_execution_events` | 国企收储事件 (已验证来源) |
| `city_price_index_monthly` | NBS 70 城房价指数 (环比/同比/定基) |
| `city_transaction_monthly` | 月度成交量 |
| `bottom_score_monthly` | 预计算评分/状态/因子/解释 |
| `professional_opinions` | 券商研报共识 |
| `pboc_global` | 央行再贷款进度时序 |
| `data_quality_log` | 数据质量审计 |

---

## ⚙️ 4. 部署运行

### 完整管道
```bash
# 初始化 DB + 爬取 34 城 + 计算评分 + 编译 HTML
python3 -m china_housing_monitor

# 跳过爬取，仅重新生成 HTML
python3 -m china_housing_monitor --no-scrape

# 仅初始化数据库
python3 -m china_housing_monitor --init-only
```

### 验证测试
```bash
python3 tests/test_scoring_rigor.py
python3 skills/storage-event-scanner/tests/test_deduplication.py
python3 skills/storage-event-scanner/tests/test_chm_contract.py
```

### 本地预览
```bash
python3 -m http.server 8080
# 浏览器打开 http://localhost:8080/chm.html
```

---

## 🤖 5. AI 代理使用建议

> **⚠️ 重要提示：使用 AI 代理运行 CHM 时，请选择较强的模型**

CHM 的完整管道包含多个步骤：初始化数据库、获取 NBS 数据、爬取链家数据、计算评分、生成报告。较弱的模型（如 DeepSeek v4 Flash）可能在首次装载时**跳过 NBS 数据获取**，导致评分因子中 S_Price 缺失数据源，整体分值失真且偏低。

### 推荐模型

| 模型 | 推荐度 | 说明 |
|------|--------|------|
| **DeepSeek v4 Pro** | ⭐⭐⭐ | 推荐，能正确执行完整管道 |
| **Claude 3.5 Sonnet** | ⭐⭐⭐ | 推荐，理解多步骤流程 |
| **GPT-4o** | ⭐⭐⭐ | 推荐，执行力强 |
| DeepSeek v4 Flash | ⚠️ | 可能跳过 NBS 数据获取 |
| 其他轻量模型 | ⚠️ | 可能出现步骤遗漏 |

### 验证方法

运行完成后，检查是否成功获取 NBS 数据：
```bash
sqlite3 china_monitor_db.sqlite "SELECT COUNT(*) FROM city_price_index_monthly"
# 应返回 487+ 条记录
```

如果返回 0，请手动执行：
```bash
python3 -m china_housing_monitor --fetch-nbs
```

---

## 📦 6. 数据采集依赖（可选）

CHM 核心代码**零依赖**，仅需 Python 3.11+。实时数据采集需要额外工具：

| 工具 | 用途 | 必需？ |
|------|------|--------|
| [browser-use](https://github.com/browser-use/browser-use) | 浏览器自动化（收储扫描、央行数据、中指数据） | 数据更新时 |
| Chrome/Chromium | browser-use 的浏览器后端 | 数据更新时 |

<details>
<summary>安装 browser-use</summary>

```bash
pip install "browser-use[core]"
# 或
uv add "browser-use[core]"
```

验证安装：
```bash
browser-use doctor
```

**为什么需要"有头浏览器"？**

CHM 的数据采集目标（百度、央行官网、中指研究院）会检测并拦截无头浏览器。使用 `--headed` 模式可以：
- 正常渲染 JavaScript 动态内容
- 手动处理验证码（如需要）
- 避免被反爬机制拦截

</details>

<details>
<summary>不安装 browser-use 也能用吗？</summary>

**可以。** 以下功能不需要 browser-use：
- ✅ 初始化数据库：`python3 -m china_housing_monitor --init-only`
- ✅ 生成 HTML 报告：`python3 -m china_housing_monitor --no-scrape`
- ✅ 运行测试：`python3 tests/test_scoring_rigor.py`
- ✅ 查看预生成的 `chm.html`

以下功能需要 browser-use：
- ❌ 收储事件扫描（每周增量更新）
- ❌ 央行再贷款数据提取（每季度）
- ❌ 中指研究院数据提取（每月）

</details>

---

## 📊 7. 数据获取

详见 [DATA_ACQUISITION.md](DATA_ACQUISITION.md) — 各数据源的获取方式、格式、导入命令。

| 数据源 | 方式 | 频率 | 评分影响 |
|--------|------|------|----------|
| NBS 70城 | `--fetch-nbs` | 每月 | S_Price 60% |
| 链家挂牌 | 自动爬虫 | 每周 | 展示用 |
| 央行再贷款 | browser-use | 每季度 | S_PBOC 10% |
| 收储事件 | 搜索+去重 | 每周 | S_Storage 30% |
| 中指研究院 | browser-use | 每月 | 展示用 |

---

## 📝 8. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0.1 | 2026-06-18 | 评分计算顺序修复 + seed.py 收储事件同步 + AI 代理使用建议 |
| v1.0.0 | 2026-06-18 | 开源准备 & 数据采集依赖说明：修复 schema、添加 LICENSE、清理路径、统一术语 |
| v0.9 | 2026-06-15 | 中指数据导入、数据获取指南、34城评分更新 |
| v0.8 | 2026-06-02 | 34 城扩展、ECharts 地图、收储扫描器 Skill、模块化重构、移动端 UI 优化 |
| v0.7 | 2026-05-31 | 移动端布局重构、Tooltip 优化、文字修复、告一段落工作流 |
| v0.6 | 2026-05-31 | 单文件 → 14 模块 + 6 JS + 4 HTML 模板化拆分 |

---

## 🤝 9. 参与贡献

欢迎参与 CHM 项目！请先阅读：

- [贡献指南](CONTRIBUTING.md) — 如何报告 Bug、建议功能、提交代码
- [行为准则](CODE_OF_CONDUCT.md) — 社区行为规范

---

## ⚠️ 10. 免责声明

本终端仅供研究参考，不构成任何投资建议。数据基于公开信息整理，可能存在滞后或偏差。投资决策请以官方披露为准，风险自担。
