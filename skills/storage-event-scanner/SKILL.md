---
name: storage-event-scanner
version: 3.0.0
description: CHM 项目专用收储事件扫描器。Use when running weekly incremental scans, reviewing, deduplicating, or importing government housing acquisition events into China Housing Monitor storage_execution_events.
---

# Storage Event Scanner v3.0

CHM 项目专用收储事件入口，用于寻找并审核"收购已建成/存量商品房用作保障性住房"的公开事件。目标不是多抓，而是保护 `storage_execution_events` 的数据质量。

## Prerequisites

**必须在执行任何扫描命令前检查以下前置条件。**

### 1. browser-use CLI

```bash
# 检查是否已安装
browser-use doctor

# 如果未安装
pip install "browser-use[core]"
# 或
uv add "browser-use[core]"
```

- 官方仓库：https://github.com/browser-use/browser-use
- 文档：https://docs.browser-use.com

### 2. Chrome/Chromium with Remote Debugging

browser-use 需要连接到运行中的 Chrome 实例：

```bash
# 方式 1：启动 Chrome 并开启远程调试
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# 方式 2：在 Chrome 中访问
chrome://inspect/#remote-debugging
```

### 3. Headed 模式要求

**本项目必须使用 `--headed` 模式**，原因：
- 百度搜索需要渲染 JavaScript 动态内容
- 部分政府网站需要处理验证码
- Headless 模式会被反爬机制拦截

```bash
# 正确
browser-use --headed open "https://www.baidu.com"

# 错误（会被拦截）
browser-use open "https://www.baidu.com"
```

### Codex 沙箱注意事项

在 Codex 默认 shell 沙箱内，`browser-use doctor` 可能在 macOS AppKit
屏幕检测处直接 abort（退出码 134），栈顶通常是
`browser_use/browser/profile.py::get_display_size()` 调用
`NSScreen.mainScreen().frame()`。这不是 Chrome、百度或 CDP 问题。

如果出现该现象，必须把 `browser-use` 命令用授权方式跑到沙箱外：

```bash
browser-use doctor
browser-use --headed open "https://www.baidu.com"
```

若提示 `Session 'default' is already running with different config`，先执行：

```bash
browser-use close
```

### 前置条件检查命令

执行扫描前运行：

```bash
browser-use doctor && browser-use --headed open "https://www.baidu.com" && browser-use close
```

如果上述命令失败，参考 Troubleshooting 章节。

## Project Contract

- 项目根目录：当前仓库根目录
- 目标库：`china_monitor_db.sqlite`
- 目标表：`storage_execution_events`
- 质量日志：`data_quality_log`
- 城市 ID 唯一来源：`china_housing_monitor.config.CORE_CITIES`
- 事件哈希唯一算法：`china_housing_monitor.config.compute_event_hash(city_id, event_date, event_stage, title)`
- 不使用 pip 依赖；保持 Python 标准库

## Weekly Mode (v3.0 推荐流程)

当用户说"跑本周收储扫描"时执行每周增量扫描。

### 固定更新口径

- **频率**：每周一次，建议周一执行。
- **扫描窗口**：只抓取上一个完整自然周的信息，即 `run-date` 所在周的前一周周一至周日。
  - 例：`--run-date 2026-07-13` 对应扫描 `2026-07-06` 至 `2026-07-12`。
- **输出目录**：仍写入 `skills/storage-event-scanner/results/weekly/YYYY-MM-DD/`，其中
  `YYYY-MM-DD` 使用本次执行日期，不使用窗口开始日期。
- **导入边界**：扫描结果先作为证据；没有人工/代理逐条审核通过前，不写入
  `storage_execution_events`。
- **复用优先级**：在 Codex 内优先用内置/应用内浏览器做来源核验；只有用户明确要求
  `browser-use` 或需要 DOM 批量抽取时，才走 headed `browser-use` 辅助脚本。

### 核心原则

**先确定窗口，再逐城找证据。** v2.x 的自动化 scanner.py 效果不佳（容易搜到全国综述文章而非城市具体事件），v3.0 以“上周窗口 + 逐城搜索 + 打开原文核验”为准。

### 流程概览

```
1. 准备阶段
   ├── 确定 run-date 和上周扫描窗口
   ├── 创建 results/weekly/YYYY-MM-DD/ 目录
   └── 加载已有 source_url 去重

2. 逐城搜索（34城）
   ├── 搜索百度、官方站点和搜狗微信/官方微信结果
   ├── 搜索关键词包含：城市名 + 收购存量商品房 + 保障房 + 上周日期窗口
   ├── 检查搜索结果标题和摘要
   ├── 打开候选文章验证来源和内容
   └── 记录有效事件到 reviewed.json

3. 审核导入
   ├── 运行 dry-run 测试
   ├── 确认无误后 --commit 导入
   └── 重新生成 HTML 页面
```

### 详细步骤

#### 1. 准备阶段

```bash
# 创建本周输出目录
mkdir -p skills/storage-event-scanner/results/weekly/YYYY-MM-DD

# 查看已有事件（避免重复）
sqlite3 china_monitor_db.sqlite "SELECT city_id, source_url FROM storage_execution_events;"
```

每周执行时先明确窗口：

```text
run-date = 本次执行日期，通常是周一
scan_window = run-date 前一个完整自然周的周一至周日
```

窗口只用于搜索和审核；输出目录仍按 `run-date` 命名。

#### 2. 逐城搜索

**搜索命令模板：**

```bash
# 打开百度搜索
browser-use open "https://www.baidu.com/s?wd={城市名} 收购存量商品房 保障房 以旧换新 {年份}" 2>&1

# 等待页面加载（5秒）
sleep 5

# 提取搜索结果
browser-use eval "JSON.stringify(Array.from(document.querySelectorAll('#content_left .c-container')).slice(0,6).map(el => {const t = el.querySelector('h3 a'); const a = el.querySelector('.c-abstract'); return {title: t ? t.innerText.trim().substring(0,100) : '', url: t ? t.href : '', abstract: a ? a.innerText.trim().substring(0,200) : ''}}).filter(x => x.title))" 2>&1
```

**验证文章命令模板：**

```bash
# 打开候选文章
browser-use open "{文章URL}" 2>&1

# 等待页面加载（3秒）
sleep 3

# 获取页面标题和URL
browser-use eval "document.title + ' | ' + window.location.href" 2>&1

# 获取页面内容（前800字）
browser-use eval "document.body.innerText.substring(0, 800)" 2>&1
```

**搜索关键词优化：**

| 场景 | 推荐关键词 |
|---------|-----------|
| 基础逐城 | `{城市名} 收购存量商品房 保障房 {年份} 上周 {开始日期} 至 {结束日期}` |
| 政府源优先 | `{城市名} 收购存量商品房 保障性住房 征集 通告 site:gov.cn` |
| 国企/安居线索 | `{城市名} 安居 集团 收购 存量商品房 保障房 {年份}` |
| 官方微信 | `{城市名} 收购存量商品房 保障房 官方微信 征集` |
| 缺口城市复查 | `{城市名} 保障性住房 房源征集 收购 存量商品房 {年份}` |

**搜索结果筛选标准：**

- ✅ **有效标题**：包含具体城市名 + 收购/征集/以旧换新 + 保障房/保租房
- ❌ **无效标题**：全国综述、市场评论、房价预测、土地收储、城中村统租

**来源验证优先级：**

| 优先级 | 来源类型 | URL特征 | 可靠性 |
|--------|---------|---------|--------|
| 100 | 政府官网 | `*.gov.cn` | 最高 |
| 90 | 政府/国企官方微信 | `mp.weixin.qq.com` | 高 |
| 80 | 央媒 | `people.com.cn`, `xinhuanet.com`, `cctv.com` | 高 |
| 70 | 地方官媒 | 各省市级媒体 | 中 |
| ❌ | 普通自媒体 | `baijiahao.baidu.com`, `thepaper.cn` | 不可用 |

**文章内容验证要点：**

1. **页面可访问**：URL稳定，非跳转链接
2. **来源可信**：发布机构为政府、国企、央媒
3. **内容明确**：正文明确指向"收购存量商品房用作保障性住房"
4. **城市匹配**：正文城市与搜索城市一致
5. **日期可信**：有明确发布日期或事件日期

#### 3. 审核导入

**reviewed.json 格式：**

```json
[
  {
    "city_id": "sh",
    "city_name": "上海",
    "title": "上海房管局确认中心城区收购小户型二手房用作保租房",
    "event_date": "2026-05-07",
    "event_stage": "政策表态",
    "source_url": "https://fgj.sh.gov.cn/tpxw/20260507/adba080043d84d74b90ee27bedf23ad1.html",
    "source_type": "gov_official",
    "source_reliability": 95,
    "details": "上海市房管局局长高世昀在《2026上海民生访谈》中确认，今年上海在保租房筹措方面有了创新举措——在中心城区收购小户型二手房用作保租房。",
    "buyer_entity": "上海市各区国企",
    "approved": true,
    "review": {
      "status": "approved",
      "review_note": "上海市房屋管理局官网（fgj.sh.gov.cn）2026-05-07发布。"
    },
    "needs_verification": false,
    "verification_notes": "已通过官方来源验证。"
  }
]
```

**导入命令：**

```bash
# Dry-run 测试
python3 skills/storage-event-scanner/scripts/db_importer.py skills/storage-event-scanner/results/weekly/YYYY-MM-DD/reviewed.json

# 确认无误后正式导入
python3 skills/storage-event-scanner/scripts/db_importer.py skills/storage-event-scanner/results/weekly/YYYY-MM-DD/reviewed.json --commit

# 重新生成 HTML 页面
python3 -m china_housing_monitor --no-scrape
```

### 34城搜索清单

**一线城市（4城）：**
- bj (北京), sh (上海), sz (深圳), gz (广州)

**新一线城市（11城）：**
- cd (成都), cq (重庆), hz (杭州), wh (武汉), xa (西安)
- nj (南京), tj (天津), cs (长沙), hf (合肥), zz (郑州), xm (厦门)

**二线城市（11城）：**
- qd (青岛), nb (宁波), fz (福州), sy (沈阳), jn (济南)
- sjz (石家庄), ty (太原), hhht (呼和浩特), cc (长春), heb (哈尔滨), nc (南昌)

**三线城市（8城）：**
- nn (南宁), hk (海口), gy (贵阳), km (昆明)
- lz (兰州), xn (西宁), yc (银川), wlmq (乌鲁木齐)

### 常见问题

**Q: 搜索结果都是全国综述文章怎么办？**
A: 添加 `site:gov.cn` 限定政府网站，或使用更具体的关键词如 `"{城市名} 安居 集团 收购"`。

**Q: 找到文章但来源是百度百家号怎么办？**
A: 百度百家号（baijiahao.baidu.com）不可用，需要寻找其他来源或跳过该事件。

**Q: 文章没有明确日期怎么办？**
A: 只能通过多个可信来源交叉比对后取最早可信发布日期，并写入 `methodology_note`。

**Q: 同一事件有多个来源怎么办？**
A: 只保留一条 DB 记录：`source_url` 使用最权威来源，其他来源写入 `methodology_note`。

## Stage And Scoring

有效阶段：

- `政策表态`：入库但 `is_score_eligible=0`，不参与 CHM 评分。
- `房源征集`：入库并可评分。
- `正式招标`：入库并可评分。
- `成交公示`：入库并可评分。
- `签约收购`：入库并可评分。
- `改造完成/配租配售`：入库并可评分。

至少到 `房源征集` 才算有效收储动作。`政策表态` 常用于提振楼市预期，只作为过程信息记录。

## Source Priority

| Priority | Source | Rule |
|---:|---|---|
| 100 | 政府官网 | `*.gov.cn`，最高优先级 |
| 90 | 政府/国企官方微信 | `mp.weixin.qq.com`，需确认账号官方属性；与地方政府官网同级置信 |
| 80 | 央媒 | 可评分，但先继续找政府源；找不到政府源时使用 |
| 70 | 地方官媒 | 可评分但置信度低于政府源；找不到政府源时使用 |
| 拒绝 | 普通自媒体/中介/市场号 | 不入库，不评分 |

同一事件同一阶段有多个来源时，只保留一条 DB 记录：`source_url` 使用最权威来源，其他来源写入 `methodology_note`。如果阶段不同，分开入库。

## Candidate Review

逐条打开 `final_url`，不要只看搜索摘要。审核时必须确认：

- 页面可访问，且最终 URL 稳定。
- 发布机构是否为政府官网、政府/国企官方微信、央媒或地方官媒。
- 正文是否明确是"收购存量商品房用作保障性住房"，不是土地收储、以旧换新、城中村统租、市场评论。
- 正文城市是否等于 `city_id`。
- 事件日期来自正文、页面发布日期或可信来源交叉比对，不来自搜索摘要猜测。
- 阶段是否正确。
- 同城、同日期、同阶段、同标题或同 URL 是否已在 `storage_execution_events`。

通过项设置：

```json
{
  "approved": true,
  "review": {
    "status": "approved",
    "review_note": "正文确认，政府官网稳定 URL，未发现重复"
  }
}
```

不通过项保留但标记：

```json
{
  "approved": false,
  "review": {
    "status": "rejected",
    "reject_reason": "土地收储，不是收购商品房用作保障房"
  }
}
```

## Import Flow

默认只做 dry-run，不写 DB：

```bash
python3 skills/storage-event-scanner/scripts/db_importer.py skills/storage-event-scanner/results/weekly/YYYY-MM-DD/reviewed.json
```

确认 dry-run 无误后再写入：

```bash
python3 skills/storage-event-scanner/scripts/db_importer.py skills/storage-event-scanner/results/weekly/YYYY-MM-DD/reviewed.json --commit
```

commit 前 importer 会备份数据库。导入时会同时写：

- `storage_execution_events`
- `data_quality_log`

导入成功后再生成页面：

```bash
python3 -m china_housing_monitor --no-scrape
```

## Rejection Rules

直接拒绝：

- 土地收储、征迁、拆迁、旧改、城中村统租。
- 以旧换新、个人/中介收房、二手房交易服务。
- 全国/多地综述，无法落到具体城市事件。
- 房价预测、市场评论、投资分析、政策解读合集。
- 仅标题命中，正文没有收购存量商品房事实。
- URL 为搜索跳转、验证码页、404、撤稿页。
- 城市错配。

## Legacy Automated Scanner (v2.x)

v2.x 的自动化 scanner.py 仍然可用，但效果不如手动搜索。适用于：

- 快速预筛选大量城市
- 自动化测试场景
- 批量生成候选列表

```bash
python3 skills/storage-event-scanner/scripts/scanner.py --all --run-date YYYY-MM-DD
```

注意：自动化扫描结果仍需人工审核，不能直接导入。

## Browser-use Headed Helper

当需要按 v3.0 流程用 headed browser-use 扫描百度 + 搜狗微信，但又希望减少
截图/token 消耗时，可运行辅助脚本。该脚本只写本周证据 JSON，不导入 DB：

```bash
python3 skills/storage-event-scanner/scripts/browser_use_weekly_scan.py --run-date YYYY-MM-DD
```

默认扫描 `--run-date` 前一个完整自然周。也可以显式指定窗口：

```bash
python3 skills/storage-event-scanner/scripts/browser_use_weekly_scan.py \
  --run-date 2026-07-13 \
  --from-date 2026-07-06 \
  --to-date 2026-07-12
```

输出文件：

- `browser_use_scan.json`：扫描窗口、34 城百度与搜狗微信搜索结果、打开状态、候选验证结果
- `browser_use_verified_candidates.json`：脚本层面确认最终 URL 稳定且正文命中的候选
- `browser_use_review_notes.json`：人工审核结论和拒绝/待核原因（由执行者补充）

`browser_use_verified_candidates.json` 不是 `reviewed.json`，不得直接导入。导入前仍需
逐条确认阶段、事件日期、城市匹配、来源权威性和 DB 去重。

## Tests

```bash
python3 skills/storage-event-scanner/tests/test_deduplication.py
python3 skills/storage-event-scanner/tests/test_chm_contract.py
python3 skills/storage-event-scanner/scripts/scanner.py --help
python3 skills/storage-event-scanner/scripts/db_importer.py --help
```

不要把真实全城扫描当测试，因为它依赖浏览器状态、搜索引擎反爬和验证码。
