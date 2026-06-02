---
name: storage-event-scanner
version: 2.0.0
description: 收储事件智能扫描器 - 搜索、过滤、验证、入库。Use when scanning for government housing acquisition events for a specific city or all cities.
---

# Storage Event Scanner v2.0

收储事件智能扫描器 — 搜索政府收储公告，经 agent 验证后入库。

## 核心原则

**宁缺毋滥**。每条入库事件必须满足：
1. 来自 gov.cn 或 mp.weixin.qq.com 等权威来源
2. 城市标签与文章内容一致
3. 与已有事件不重复
4. Agent 人工确认有效

## 工作流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  1. 搜索     │ ──→ │  2. 过滤     │ ──→ │  3. 解析     │
│  Baidu/Sogou │     │  黑名单+白名单│     │  URL重定向   │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
┌─────────────┐     ┌─────────────┐           ▼
│  6. 入库     │ ←── │  5. Agent   │ ←── ┌─────────────┐
│  写入SQLite  │     │  逐条确认    │     │  4. 输出候选  │
└─────────────┘     └─────────────┘     │  JSON待审    │
                                        └─────────────┘
```

### Step 1: 搜索 (scanner.py)

```bash
python3 skills/storage-event-scanner/scripts/scanner.py --city <city_id>
```

**双引擎搜索**：
- **百度**：通用网页搜索，支持 `site:gov.cn`
- **搜狗微信搜索**：专门搜索微信公众号文章，能找到政府公众号公告（百度搜不到的）

搜索关键词：`{城市名} 收购存量商品房 保障房`
排除关键词：`以旧换新`, `土地收储`, `城中村`, `租赁`, `房价`
每城市最多 ~20 条结果（百度 10 + 搜狗 10）

### Step 2: 过滤 (scanner.py)

**来源白名单**（仅接受以下来源）：
- `*.gov.cn` — 政府官网
- `mp.weixin.qq.com` — 微信公众号（需验证为官方号）
- `xinhuanet.com`, `people.com.cn` — 国家媒体

**标题黑名单**（自动排除）：
- 包含：`以旧换新`, `土地收储`, `城中村改造`, `房价`, `涨跌`, `预测`, `分析`
- 包含：`自媒体`, `观点`, `评论`, `解读`, `盘点`, `汇总`
- 包含其他城市名（如搜索上海时出现"广州"）

### Step 3: 解析 URL (scanner.py)

- `baidu.com/link` → `curl` 测试实际跳转目的地
- `weixin.sogou.com/link` → `curl` 测试实际跳转目的地
- 如果目的地不是白名单来源，丢弃
- 存储最终 URL（非重定向 URL）

### Step 4: 输出候选 (scanner.py)

输出 JSON 文件到 `results/{city_id}_candidates.json`，格式：
```json
[
  {
    "title": "标题",
    "url": "最终URL",
    "abstract": "摘要",
    "source_type": "gov_official",
    "suggested_stage": "签约收购",
    "suggested_date": "2026-04-01",
    "city_match": true,
    "needs_verification": true
  }
]
```

### Step 5: Agent 验证

**Agent 必须逐条确认**：
1. 用 `webfetch` 或 `browser-use` 打开 URL，确认内容可访问
2. 确认文章确实关于「收购存量商品房用作保障房」
3. 确认城市标签正确（文章中的城市 = 搜索城市）
4. 确认与已有事件不重复（查询 DB 比较标题+日期）
5. 确认阶段分类正确（政策表态/房源征集/签约收购等）
6. 确认日期可提取

**Agent 判定标准**：
- ✅ **入库**：gov.cn 来源 + 内容相关 + 城市正确 + 不重复
- ❌ **丢弃**：内容无关 / 城市错误 / 重复 / 来源不可靠
- ⚠️ **待定**：内容相关但来源不够权威（如地方媒体）

### Step 6: 入库

Agent 确认后，手动执行 SQL 插入：
```sql
INSERT INTO storage_execution_events 
(city_id, event_date, event_stage, title, source_url, source_reliability, 
 data_status, confidence_score, is_score_eligible, collected_at, event_hash)
VALUES (?, ?, ?, ?, ?, ?, 'official', ?, 1, datetime('now'), ?);
```

## 使用方法

```bash
# 扫描单个城市（输出候选 JSON，不自动入库）
python3 skills/storage-event-scanner/scripts/scanner.py --city bj

# 扫描所有城市
python3 skills/storage-event-scanner/scripts/scanner.py --all

# 查看候选结果
cat skills/storage-event-scanner/results/bj_candidates.json
```

**扫描完成后**：告诉 agent "验证 [城市] 的候选事件"，agent 会逐条检查并入库。

## 事件阶段

| 阶段 | 权重 | 触发关键词 |
|------|------|-----------|
| 政策表态 | 10 | 方案、通知、意见、政策、推进 |
| 房源征集 | 25 | 征集、公告、招标公告 |
| 正式招标 | 45 | 招标、比选、采购 |
| 成交公示 | 70 | 中标、成交、公示 |
| 签约收购 | 90 | 签约、签署、协议、落地 |
| 改造完成 | 100 | 竣工、交付、配租、配售 |

## 信息源优先级

| 优先级 | 来源 | URL 特征 |
|--------|------|----------|
| 100 | 政府官网 | *.gov.cn |
| 95 | 政府微信 | mp.weixin.qq.com (官方号) |
| 80 | 国家媒体 | xinhuanet.com, people.com.cn |
| 60 | 地方媒体 | 仅在无更优来源时接受 |

## 依赖

- Python 3.8+
- browser-use CLI（已连接 Chrome）
- sqlite3

## 注意事项

- 需要连接 Chrome 浏览器（`browser-use connect`）
- 每城市扫描约 2-5 分钟
- **不会自动入库** — 输出候选 JSON，等 agent 验证后手动入库
- **搜狗验证码**（两层处理）：
  1. **搜索页验证码**：搜狗搜索页弹验证码时，脚本暂停，在 Chrome 中手动完成验证后自动继续
  2. **链接重定向验证码**：搜狗 `weixin.sogou.com/link` 重定向到 antispider 时，脚本会在 Chrome 中打开该链接，等你解验证码后获取真实 URL
