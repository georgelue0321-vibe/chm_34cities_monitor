# CHM 数据获取指南

> 本文档说明 China Housing Monitor 所需数据的获取方式，供 Agent 或开发者执行数据更新。

---

## 1. 快速开始

```bash
# 完整管道：初始化 → 爬取链家 → 计算评分 → 生成 HTML
python3 -m china_housing_monitor

# 仅更新 NBS 房价指数（东方财富 API）
python3 -m china_housing_monitor --fetch-nbs

# 跳过爬取，仅重新生成 HTML
python3 -m china_housing_monitor --no-scrape
```

---

## 2. 数据源详解

### 2.1 NBS 70城房价指数（自动）

**为什么需要**：评分因子 S_Price (60%) 的核心数据源，直接决定底部信号分数。

**获取方式**：

```bash
python3 -m china_housing_monitor --fetch-nbs
```

**工作原理**：
- API 来源：东方财富 `https://datacenter-web.eastmoney.com/api/data/v1/get`
- 数据表：`RPT_ECONOMY_HOUSE_PRICE`
- 覆盖：34城 × 36个月（2023-06 至今）
- 字段：新房环比、新房同比、二手房环比、二手房同比

**数据格式**（`city_price_index_monthly` 表）：

| 字段 | 说明 |
|------|------|
| city_id | 城市 ID（如 bj, sh） |
| month | 月份 YYYY-MM |
| new_home_mom | 新房环比 % |
| new_home_yoy | 新房同比 % |
| resale_home_mom | 二手房环比 % |
| resale_home_yoy | 二手房同比 % |
| source | EASTMONEY_API |
| data_status | official |

**验证方法**：

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('china_monitor_db.sqlite')
cur = conn.cursor()
cur.execute('SELECT city_id, month, resale_home_mom FROM city_price_index_monthly WHERE month=\"2026-04\" LIMIT 5')
for r in cur.fetchall():
    print(f'{r[0]:5s} {r[1]} MoM={r[2]}')
"
```

**数据发布节奏**：每月 15-18 日发布上月数据。

---

### 2.2 链家挂牌数据（自动爬虫）

**为什么需要**：提供挂牌量和均价快照，用于市场热度监测。注意：链家反爬严格，经常被屏蔽。

**获取方式**：

```python
from china_housing_monitor.crawler import update_all_cities_market_data
update_all_cities_market_data()
```

**工作原理**：
- 目标：`{city}.lianjia.com/ershoufang/`
- 提取：挂牌总量、featured 房源 unitPrice 均值
- 失败策略：若爬取失败（被屏蔽、超时等），该城市当月数据不插入
- 状态标记：`scraped`（成功）/ `missing`（失败或无数据）

**数据格式**（`market_index` 表）：

| 字段 | 说明 |
|------|------|
| city_id | 城市 ID |
| date | 月份 YYYY-MM |
| listings | 挂牌量（-1 表示被屏蔽或无数据） |
| price_sqm | 均价 元/㎡ |
| data_status | scraped / missing |
| source_label | 链家 |

**已知问题**：
- 链家/贝壳对自动化访问有反爬机制
- 大部分城市会被屏蔽，返回 missing 数据
- 不生成 synthetic 或 extrapolated 数据

**注意**：
- 历史数据库中可能存在早期生成的 synthetic 数据（2024年之前）
- 这些数据已标记为 `data_status='estimated'`，不参与评分

---

### 2.3 央行再贷款数据（browser-use 提取）

**为什么需要**：评分因子 S_PBOC (10%) 的数据源，反映全国保障房再贷款资金温度。

**获取方式**：

```bash
# 启动 headed 浏览器（需要处理验证码时用 headed 模式）
browser-use --headed open "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125437/4634692/4634700/index.html"

# 等待页面加载后提取数据
browser-use eval "
const text = document.body.innerText;
const balanceMatch = text.match(/余额[：:]\s*([\d.]+)\s*万亿/);
const usedMatch = text.match(/已用[：:]\s*([\d.]+)\s*万亿/);
JSON.stringify({
    balance: balanceMatch ? parseFloat(balanceMatch[1]) : null,
    used: usedMatch ? parseFloat(usedMatch[1]) : null
})
"
```

**数据格式**（`pboc_global` 表）：

| 字段 | 说明 |
|------|------|
| date | 报告日期 YYYY-MM-DD |
| balance_billion | 余额（亿元） |
| percentage | 使用率 % |
| source | 数据来源说明 |
| collected_at | 落库时间 |

**导入 SQL**：

```sql
INSERT OR REPLACE INTO pboc_global 
(date, balance_billion, percentage, source, collected_at)
VALUES ('2025-03-31', 5900.0, 93.7, '央行一季度货币政策执行报告', datetime('now'));
```

**数据发布节奏**：每季度末发布，通常滞后 1-2 个月。

**已知问题**：
- 2024年Q4 起 PBOC 改变披露格式，不再公布各工具余额
- 当前最新详细数据：2024-09-30（余额 16.2 亿，使用率 5.4%）
- 超过 6 个月未更新时，pboc_score 封顶 30

---

### 2.4 收储事件数据（搜索 + 去重 + 导入）

**为什么需要**：评分因子 S_Storage (30%) 的数据源，反映地方国企收购存量房进展。

**获取方式**：

```bash
# 扫描单个城市
python3 skills/storage-event-scanner/scripts/scanner.py --city sy

# 扫描所有城市
python3 skills/storage-event-scanner/scripts/scanner.py --all
```

**手动搜索流程（Agent 执行）**：

1. **百度搜索**：
```bash
browser-use --headed open "https://www.baidu.com/s?wd={城市名}+收购存量商品房+保障房+征集通告+2026"
```

2. **搜狗微信搜索**：
```bash
browser-use open "https://weixin.sogou.com/weixin?type=2&query={城市名}+收购存量商品房+保障房+征集"
```

3. **提取 URL**：
```bash
browser-use eval "
JSON.stringify(Array.from(document.querySelectorAll('.result h3 a, .news-list h3 a'))
    .slice(0, 10)
    .map(el => ({title: el.innerText.trim().substring(0, 100), url: el.href})))
"
```

4. **去重检查**：对比 `skills/storage-event-scanner/results/weekly/existing_urls.txt`

5. **阶段分类**：6个阶段及其权重

| 阶段 | 权重 | 关键词 |
|------|------|--------|
| 政策表态 | 10 | 方案、通知、意见 |
| 房源征集 | 25 | 征集公告、征集通告 |
| 正式招标 | 45 | 招标公告、采购 |
| 成交公示 | 70 | 中标、成交公示 |
| 签约收购 | 90 | 签约、签署协议 |
| 改造完成 | 100 | 竣工、交付、配租 |

6. **导入数据库**：
```bash
python3 skills/storage-event-scanner/scripts/db_importer.py --input reviewed.json
```

**数据格式**（`storage_execution_events` 表）：

| 字段 | 说明 |
|------|------|
| city_id | 城市 ID |
| district | 区域 |
| event_date | 事件日期 YYYY-MM-DD |
| event_stage | 阶段名称 |
| event_title | 事件标题 |
| event_description | 事件描述 |
| acquiring_entity | 收购主体 |
| source_url | 来源 URL |
| event_hash | 去重哈希 |

**验证方法**：

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('china_monitor_db.sqlite')
cur = conn.cursor()
cur.execute('SELECT city_id, COUNT(*) FROM storage_execution_events GROUP BY city_id ORDER BY COUNT(*) DESC')
for r in cur.fetchall():
    print(f'{r[0]:5s} {r[1]:3d} events')
"
```

---

### 2.5 中指研究院数据（browser-use 提取）

**为什么需要**：提供二手住宅绝对价格，用于展示和交叉验证。不直接影响评分。

**获取方式**：

```bash
# 启动 headed 浏览器
browser-use --headed open "https://www.cih-index.com/data/index/esfHouse.html"

# 等待页面加载（5秒）
sleep 5

# 提取 34 城数据
browser-use eval "
const text = document.body.innerText;
const cities = {
    '北京':'bj','上海':'sh','深圳':'sz','广州':'gz','成都':'cd','重庆':'cq',
    '杭州':'hz','武汉':'wh','西安':'xa','南京':'nj','天津':'tj','长沙':'cs',
    '合肥':'hf','郑州':'zz','厦门':'xm','青岛':'qd','宁波':'nb','福州':'fz',
    '石家庄':'sjz','太原':'ty','呼和浩特':'hhht','沈阳':'sy','长春':'cc',
    '哈尔滨':'heb','南昌':'nc','济南':'jn','南宁':'nn','海口':'hk','贵阳':'gy',
    '昆明':'km','兰州':'lz','西宁':'xn','银川':'yc','乌鲁木齐':'wlmq'
};
const results = [];
const lines = text.split('\\n');
for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (cities[line]) {
        let mom = null, price = null;
        for (let j = i+1; j < Math.min(i+10, lines.length); j++) {
            const l = lines[j].trim();
            if (/^-?\\d+\\.\\d+$/.test(l) && mom === null) mom = parseFloat(l);
            if (/^\\d{4,6}$/.test(l) && price === null) price = parseInt(l);
            if (mom !== null && price !== null) break;
        }
        if (price) results.push({city: cities[line], price, mom});
    }
}
JSON.stringify(results);
"
```

**导入数据库**：

```python
import sqlite3
from datetime import datetime

data = [
    ('bj', 62090, -0.38), ('sh', 55173, 0.13), # ... 完整 34 城数据
]

conn = sqlite3.connect('china_monitor_db.sqlite')
cur = conn.cursor()
current_month = datetime.now().strftime('%Y-%m')
updated = 0
skipped = 0

for cid, price, mom in data:
    # 只更新已有链家数据的城市/月份，不插入新行（避免 listings = -1）
    cur.execute("""
        UPDATE market_index 
        SET price_sqm = ?, source_label = '中指研究院', data_status = 'official', collected_at = datetime('now')
        WHERE city_id = ? AND date = ?
    """, (price, cid, current_month))
    if cur.rowcount > 0:
        updated += 1
    else:
        skipped += 1

conn.commit()
print(f"中指数据导入: {updated} 城更新价格, {skipped} 城跳过（无链家数据）")
```

**数据格式**（`market_index` 表）：

| 字段 | 说明 |
|------|------|
| city_id | 城市 ID |
| date | 月份 YYYY-MM |
| price_sqm | 二手住宅均价 元/㎡ |
| data_status | official |
| source_label | 中指研究院 |

**数据发布节奏**：每月 1-10 日发布上月数据。

**已知问题**：
- 历史数据需要付费 API
- 首页仅有当月数据
- 可用 MoM% 反推上月价格：`prev_price = curr_price / (1 + mom/100)`

---

## 3. 完整工作流示例

### 月度更新流程（Agent 执行）

```bash
# 1. 更新 NBS 数据（每月 18 日后）
python3 -m china_housing_monitor --fetch-nbs

# 2. 更新链家挂牌数据
python3 -c "from china_housing_monitor.crawler import update_all_cities_market_data; update_all_cities_market_data()"

# 3. 更新中指数据（browser-use）
browser-use --headed open "https://www.cih-index.com/data/index/esfHouse.html"
sleep 5
browser-use eval "提取脚本..."  # 见 2.5 节

# 4. 检查收储事件（每周一次）
python3 skills/storage-event-scanner/scripts/scanner.py --all

# 5. 重新计算评分
python3 -c "
from china_housing_monitor.scoring.factors import compute_and_store_all_scores
from china_housing_monitor.report.generator import generate_html_report
import sqlite3
from china_housing_monitor.config import DB_PATH
conn = sqlite3.connect(DB_PATH)
compute_and_store_all_scores(conn)
generate_html_report()
conn.close()
"

# 6. 验证结果
python3 scratch/verify_scoring_rigor.py
```

---

## 4. 常见问题

### Q: 链家爬虫被屏蔽怎么办？
A: 正常现象。被屏蔽的城市会标记为 `missing`，不生成 synthetic 数据。评分使用历史数据或被标记为数据不足。

### Q: NBS 数据延迟怎么办？
A: NBS 通常每月 15-18 日发布上月数据。延迟期间评分使用最新可用数据。

### Q: PBOC 数据长期不更新怎么办？
A: 2024年Q4 起 PBOC 改变披露格式，详细数据可能长期缺失。系统会自动封顶 pboc_score 为 30。

### Q: 收储事件如何判断真伪？
A: 优先级：政府官网 > 官方微信 > 国家媒体 > 地方媒体。必须有可验证的 URL。

### Q: 如何添加新城市？
A: 修改 `config.py` 中的 `CORE_CITIES` 字典，添加城市 ID、名称、能级、坐标。然后更新 `nbs_api.py` 中的 `CITY_NAME_MAP`。

---

## 5. 数据源总结

| 数据源 | 自动化 | 频率 | 评分影响 | 难度 |
|--------|--------|------|----------|------|
| NBS 70城 | ✅ API | 每月 | S_Price 60% | 低 |
| 链家挂牌 | ✅ 爬虫 | 每周 | 无（展示用） | 中 |
| 央行再贷款 | ❌ 浏览器 | 每季度 | S_PBOC 10% | 低 |
| 收储事件 | ⚠️ 搜索 | 每周 | S_Storage 30% | 高 |
| 中指研究院 | ❌ 浏览器 | 每月 | 无（展示用） | 低 |
