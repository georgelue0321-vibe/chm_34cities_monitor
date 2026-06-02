# 🏛️ 全国核心34城楼市"底部信号"智能监测终端

> **China Core 34 Cities Property Bottom Signal Terminal**
>
> 本项目是一款专为高端投资人与专业投研机构定制的**全国核心34城楼市"底部信号"智能监测大屏终端**。系统深度融合了中国人民银行（PBOC）保障性住房再贷款额度追踪、微观地方国企收储招标事件、主流券商与顶投机构研判共识，以及高频更新的挂牌基本面数据，形成一套完整的"收储防线"研判与决策辅助工具。

---

## 📂 1. 项目文件组成

```
china_housing_monitor/              ← Python 包 (v2.0.2)
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

china_monitor_db.sqlite             ← SQLite 数据库 (gitignored)
chm.html                            ← 生成的 SPA 仪表盘 (gitignored)
scratch/verify_scoring_rigor.py     ← 验证测试套件 (31 项)
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

## 🛡️ 4. 爬虫与高可用容错

- **链家/贝壳爬虫**：定向 HTTP Header + 正则解析挂牌量与均价
- **SSL 绕过**：`ssl._create_unverified_context()` 绕过 macOS 证书错误
- **Smart Fallback**：爬取失败时沿用上月数据 + 宏观均值微调（挂牌量 +1.2%，均价 -0.4%）
- **凌晨归属**：爬虫凌晨跑完的 `collected_at` 归属前一天数据

---

## ⚙️ 5. 部署运行

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
python3 scratch/verify_scoring_rigor.py
# 31/31 测试全部通过
```

### 本地预览
```bash
python3 -m http.server 8080
# 浏览器打开 http://localhost:8080/chm.html
```

---

## 📝 6. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v2.0.2 | 2026-06-02 | 移动端 UI 优化、Footer 日期、34 城导航折行 |
| v2.0.1 | 2026-05-31 | 移动端布局重构、Tooltip 优化、文字修复 |
| v2.0.0 | 2026-05-31 | 模块化重构: 单文件 → 14 模块 + 6 JS + 4 HTML |
| v0.8 | 2026-06-01 | 34 城扩展、ECharts 地图、收储扫描器 Skill |

---

## ⚠️ 免责声明

本终端仅供研究参考，不构成任何投资建议。数据基于公开信息整理，可能存在滞后或偏差。投资决策请以官方披露为准，风险自担。
