# CHM 开源前行动指南

本文档记录 2026-06-17 对 China Housing Monitor 仓库的开源就绪走查结果。目标不是一次性追求完美，而是先把公开仓库最容易踩雷的点清掉：可复现、可验证、许可证清楚、数据出处能自证、仓库边界干净。

## 总体判断

当前项目已经具备开源雏形：

- 核心代码已模块化为 `china_housing_monitor/`
- 零 Python 第三方依赖，部署门槛低
- 有数据源说明、数据获取说明和验证脚本
- `.gitignore` 已排除 SQLite、生成 HTML、scratch、本地配置等多数本地产物
- `skills/storage-event-scanner` 的两个测试可直接通过

但还不建议直接公开。当前最大风险集中在：

- 新用户从零运行可能失败
- 运行必需的地图 GeoJSON 未被 git 追踪
- README 指向的测试脚本未被 git 追踪
- 缺少许可证和第三方声明
- 数据文字，尤其是券商共识，缺少逐条可核验来源
- 仓库里混有本机路径、Agent 内部说明、外部 skill 和历史生成资产

建议先完成 P0，再考虑对外发布。

## P0：开源前必须处理

### 1. 修复全新运行 schema 问题

发现：

- `china_housing_monitor/db/init.py` 创建 `pboc_global` 时只有 4 个字段
- 同一个文件中 `pboc_history` 每条记录有 5 个值，并执行 `INSERT OR IGNORE INTO pboc_global VALUES (?, ?, ?, ?, ?)`
- `china_housing_monitor/db/init.py` 创建 `market_index` 时没有 `collected_at` 字段
- `china_housing_monitor/crawler.py` 写入 `market_index` 时使用了 `collected_at`
- `china_housing_monitor/db/init.py` 创建 `professional_opinions` 时没有 `collected_at` 字段
- `china_housing_monitor/db/seed.py` 写入 `professional_opinions` 时使用了 `collected_at`
- `DATA_SOURCES.md` 写明所有数据表均有 `collected_at`，但当前 `pboc_global`、`market_index`、`professional_opinions` 等 schema/文档并不一致

风险：

- 新用户删除本地 DB 后，执行 `python3 -m china_housing_monitor --init-only` 会先报 `table pboc_global has 4 columns but 5 values were supplied`
- 修复上述问题后，还可能继续遇到 `no column named collected_at`
- 开源后第一印象会变成“clone 后跑不起来”

建议：

- 统一 `pboc_global` 的真实字段。建议使用当前代码消费的字段：`date`、`balance_billion`、`percentage`、`source`、`collected_at`
- 避免裸 `INSERT INTO table VALUES (...)`，改成显式列名插入
- 在 `init.py` 中给 `market_index` 和 `professional_opinions` 增加 `collected_at TEXT`
- 或使用 `add_column_if_not_exists()` 做向后兼容迁移
- 同步更新 `DATA_ACQUISITION.md` 中 `pboc_global` 的导入 SQL，避免出现 `report_date/facility_name/total_quota/balance/used_pct` 与代码字段不一致

验收：

```bash
python3 -c "import tempfile, os; import china_housing_monitor.config as c; import china_housing_monitor.db.init as i; p=os.path.join(tempfile.mkdtemp(), 'fresh.sqlite'); c.DB_PATH=p; i.DB_PATH=p; i.init_db(); print(p)"
```

上述命令应在临时空 DB 上成功完成。之后再做真实干净目录验证：

```bash
python3 -m china_housing_monitor --init-only
python3 -m china_housing_monitor --no-scrape
```

两条命令都应成功完成，并生成 `chm.html`。

### 2. 追踪运行必需的地图 GeoJSON

发现：

- `china_housing_monitor/report/generator.py` 会读取 `china_housing_monitor/report/static/china.json`
- 该文件当前存在于本地，大小约 582 KB
- `.gitignore` 的 `*.json` 规则会忽略它
- `git ls-files` 中没有 `china_housing_monitor/report/static/china.json`

风险：

- 干净 clone 后执行 `generate_html_report()` 会因缺少 `china.json` 失败
- 地图模块无法渲染

建议：

- 在 `.gitignore` 中增加例外：

```gitignore
!china_housing_monitor/report/static/china.json
```

- 将该文件纳入 git
- 在 `THIRD_PARTY_NOTICES.md` 说明 GeoJSON 的来源、许可和修改情况

验收：

```bash
git check-ignore -v china_housing_monitor/report/static/china.json
git ls-files china_housing_monitor/report/static/china.json
python3 -m china_housing_monitor --no-scrape
```

第一个命令不应再显示忽略规则，第二个命令应输出该文件路径，第三个命令应能成功编译 HTML。

### 3. 把验证测试纳入仓库

发现：

- README 写明运行 `python3 scratch/verify_scoring_rigor.py`
- `.gitignore` 忽略了整个 `scratch/`
- 当前公开仓库中不会包含这个测试入口

风险：

- 外部贡献者无法按 README 运行测试
- CI 也无法引用该脚本

建议：

- 新建 `tests/test_scoring_rigor.py`
- 从 `scratch/verify_scoring_rigor.py` 迁移核心测试
- 测试数据库仍使用复制隔离，不污染生产 DB
- README 中测试命令改为：

```bash
python3 tests/test_scoring_rigor.py
python3 skills/storage-event-scanner/tests/test_deduplication.py
python3 skills/storage-event-scanner/tests/test_chm_contract.py
```

验收：

```bash
python3 -m compileall -q china_housing_monitor skills/storage-event-scanner/scripts
python3 tests/test_scoring_rigor.py
python3 skills/storage-event-scanner/tests/test_deduplication.py
python3 skills/storage-event-scanner/tests/test_chm_contract.py
```

### 4. 补齐 LICENSE 和第三方声明

发现：

- 仓库根目录没有 `LICENSE`
- 当前前端模板通过 CDN 引入 Tailwind、ApexCharts、ECharts、Font Awesome、Google Fonts
- git 历史中曾出现 `bar-chart-race/public/bgm.mp3`
- 仓库当前追踪 `skills/remotion-video-toolkit/`

风险：

- 用户不知道代码可如何使用
- 第三方库、字体、音乐和工具 skill 的许可证边界不清

建议：

- 添加 `LICENSE`，建议在 MIT、Apache-2.0、GPL-3.0 中明确选择一种
- 添加 `THIRD_PARTY_NOTICES.md`
- 对 CDN 资源列出名称、用途、许可证和链接
- 对 Remotion 工具、历史 BGM、视频产物作单独说明

验收：

- GitHub 页面显示许可证
- README 中有 License 小节
- `THIRD_PARTY_NOTICES.md` 能解释所有非自有代码、字体、音乐、工具包

### 5. 清理仓库边界和本机路径

发现：

- `AGENTS.md` 中存在 `/Users/george/WorkBuddy/CHM`
- `skills/storage-event-scanner/SKILL.md` 中存在 `/Users/george/Documents/CHM`
- `skills/remotion-video-toolkit/` 看起来是外部开发工具，不是 CHM 核心项目
- `cd_price_trend.html` 是生成产物，但当前被 git 追踪
- 本地仍有多个被忽略的大文件和开发残留，例如 `china_monitor_db.sqlite`、`china_monitor_db.sqlite.storage_import_backup_*`、`chm.html`、`.opencode/`、`self-improving-*`、`scratch/`

风险：

- 开源仓库混入个人环境路径
- 外部工具包可能带来不必要的许可和维护责任
- 生成产物和源码边界不清

建议：

- 将本机绝对路径改为项目相对路径
- 面向外部用户的文档放到 `docs/`
- Agent 私有工作流可保留本地，但不建议公开为项目核心文档
- 移除或单独说明 `skills/remotion-video-toolkit/`
- 决定是否继续追踪 `cd_price_trend.html`；更推荐在 release artifact 中发布生成页面
- 发布前用 `git status --short --ignored` 逐项确认被忽略文件不会进入仓库或发布包

验收：

```bash
rg -n "(/Users/george|WorkBuddy|\\.workbuddy|self-improving|opencode)" .
git ls-files | sort
git status --short --ignored
```

搜索结果中不应再出现个人路径或内部工作流依赖。

### 6. 整理数据文字的可核验来源

发现：

- `storage_execution_events` 大多有 `source_url`
- `professional_opinions` 中的券商共识缺少逐条研报标题、发布日期、URL 或不可公开来源说明
- `AGENTS.md` 已明确要求文字字段必须直接引用原始来源，禁止 AI 生成或总结

风险：

- 公开后用户无法验证券商共识的来源
- 若文字是整理或改写内容，可能影响可信度和合规边界

建议：

- 为 `professional_opinions` 增加字段：
  - `source_title`
  - `source_date`
  - `source_url`
  - `quote_type`
  - `methodology_note`
- 无法提供来源的内容先移除、降级为 `demo`，或改成“待补来源”
- README 中明确：评分基于公开数据，专业观点仅展示可核验原文或来源摘要

验收：

```sql
SELECT city_id, institution, date, source_url
FROM professional_opinions
WHERE source_url IS NULL OR source_url = '';
```

开源版中该查询应为空，或这些记录应明确标记为不可评分、不可引用。

## P1：让外部用户顺利使用

### 1. 重写 README 的运行路径

建议 README 分成三种使用方式：

- 快速预览：下载 release 中的 `chm.html`
- 从零生成：初始化 DB、拉取 NBS、可选爬虫、编译 HTML
- 离线开发：使用 fixture/sample DB，不触发外部站点

需要特别说明：

- `python3 -m china_housing_monitor --init-only` 会 seed 数据并重算分数
- `python3 -m china_housing_monitor --no-scrape` 当前也会先执行初始化逻辑
- `--fetch-nbs` 会访问东方财富 API
- 爬虫可能被目标站点限制，失败时应显示 missing，而不是伪造数据

### 2. 明确数据再分发策略

当前 `.gitignore` 已排除：

- `*.sqlite`
- `chm.html`
- `*.csv`
- `*.json`
- `scratch/`

这是合理方向。开源前需要进一步明确：

- 代码仓库是否只放源码和少量 seed 数据
- 完整 SQLite DB 是否作为 GitHub Release 附件发布
- 生成后的 `chm.html` 是否作为 Release artifact 发布
- 原始采集数据是否允许再分发

建议：

- 源码仓不提交完整 DB
- Release 可附带某个日期快照，并声明数据来源和免责声明
- 大型原始数据放到单独 release 或外部存储

### 3. 增加 CI

最低限度的 GitHub Actions：

```bash
python3 -m compileall -q china_housing_monitor skills/storage-event-scanner/scripts
python3 skills/storage-event-scanner/tests/test_deduplication.py
python3 skills/storage-event-scanner/tests/test_chm_contract.py
python3 tests/test_scoring_rigor.py
```

注意：

- CI 默认不跑爬虫
- CI 默认不访问需要浏览器或人工验证的网站
- 网络类数据更新可做成手动 workflow

### 4. 补数据源和爬虫合规说明

建议在 `DATA_SOURCES.md` 中明确：

- 数据源名称
- 获取方式
- 是否用于评分
- 更新频率
- 失败策略
- 人工核验要求
- 是否允许再分发

重点覆盖：

- 国家统计局 70 城指数
- 东方财富 API
- 链家/贝壳挂牌数据
- 中指研究院数据
- 央行结构性货币政策工具数据
- 地方政府和国企收储公告
- 券商研报或专业观点

### 5. 统一版本号

发现：

- README 中有 v2.0.2、v0.9 等混合版本
- CLI 打印 `China Housing Monitor (CHM) v2.0.0`
- 页脚显示 `CHM v0.9`
- `china_housing_monitor/__init__.py` 文案仍包含“18 cities”“True Bottom Score”“真底信号”等旧术语
- `DATA_ACQUISITION.md` 的 `pboc_global` 字段说明与当前代码读取的 `date/balance_billion/percentage/source` 不一致

建议：

- 以 `china_housing_monitor/__init__.py` 的 `__version__` 为唯一来源
- CLI、页脚、README 都引用同一版本
- 开源首版命名为 `v1.0.0`
- 全仓搜索并消除旧术语，尤其是“True Bottom”“真底确认”“18 城/18 cities”等容易误导用户的表达
- 将 `DATA_ACQUISITION.md`、`DATA_SOURCES.md`、实际 SQLite schema 三者对齐

## P2：提升开源协作体验

### 1. 添加贡献指南

建议新增 `CONTRIBUTING.md`，包含：

- 如何新增城市
- 如何新增收储事件
- 如何标记数据质量
- 如何运行测试
- 如何提交数据来源证据
- 什么内容不接受，例如无来源观点、营销稿、不可验证截图

### 2. 添加安全和数据错误反馈入口

建议新增 `SECURITY.md` 或 `DATA_ISSUE_TEMPLATE.md`：

- 不接受私人数据
- 不接受未授权爬取的数据包
- 数据错误如何提交 issue
- 收储事件更正需要附原始 URL

### 3. 拆分公开文档和 Agent 文档

当前 `AGENTS.md` 很适合内部协作，但对普通开源用户偏重。建议：

- `README.md`：给用户和贡献者
- `docs/architecture.md`：公开架构说明
- `docs/data-methodology.md`：评分和数据方法
- `AGENTS.md`：保留给 AI/Agent，但去除私人路径和内部记忆流程

### 4. 支持自定义 DB 路径

建议增加：

- `--db-path`
- `--report-path`
- 或环境变量 `CHM_DB_PATH`、`CHM_REPORT_PATH`

好处：

- 测试不用 patch 全局变量
- 用户可以把 DB 放到自己的数据目录
- CI 更容易隔离

### 5. 发布前做干净目录自测

发布前建议用全新目录模拟用户：

```bash
git clone <repo-url> chm-open-source-test
cd chm-open-source-test
python3 -m compileall -q china_housing_monitor
python3 -m china_housing_monitor --init-only
python3 -m china_housing_monitor --no-scrape
python3 -m http.server 8080
```

确认：

- 不依赖本机隐藏文件
- 不依赖未追踪的 scratch 文件
- 不需要已有 SQLite
- 能打开生成页面
- README 中每条命令都能执行

## 已验证项目

本次走查中已执行：

```bash
python3 -m compileall -q china_housing_monitor skills/storage-event-scanner/scripts
python3 skills/storage-event-scanner/tests/test_deduplication.py
python3 skills/storage-event-scanner/tests/test_chm_contract.py
```

结果：

- Python 编译检查通过
- storage scanner 去重测试通过
- CHM contract 测试通过

未执行：

- `scratch/verify_scoring_rigor.py`，因为它位于被忽略目录，开源前应迁移
- 全量爬虫，避免对外部站点发起批量请求
- 真实项目路径下删除 DB 后运行，因为当前 schema 问题已足够明确，应先修再验证

本次复核补充执行：

```bash
python3 -c "import tempfile, os; import china_housing_monitor.config as c; import china_housing_monitor.db.init as i; p=os.path.join(tempfile.mkdtemp(), 'fresh.sqlite'); c.DB_PATH=p; i.DB_PATH=p; i.init_db(); print(p)"
git check-ignore -v china_housing_monitor/report/static/china.json
git status --short --ignored
```

结果：

- 临时 fresh init 失败，错误为 `table pboc_global has 4 columns but 5 values were supplied`
- `china_housing_monitor/report/static/china.json` 被 `.gitignore:19:*.json` 忽略，但它是 HTML 生成必需文件
- 本地仍有大量被忽略产物，发布前需要确认不会进入源码包或 release 包

## 建议执行顺序

1. 修 `pboc_global` schema/插入列数不匹配
2. 修 schema 中缺失的 `collected_at`
3. 将 `china_housing_monitor/report/static/china.json` 纳入 git，并补来源/许可说明
4. 迁移评分测试到 `tests/`
5. 添加 `LICENSE` 和 `THIRD_PARTY_NOTICES.md`
6. 清理个人路径、内部 workflow、外部 skill 和生成产物
7. 整理 `professional_opinions` 来源字段
8. 统一版本、旧术语和数据文档 schema
9. 重写 README 的使用路径
10. 增加 CI
11. 做干净目录 clone 自测
12. 决定是否清理 git 历史中的视频/BGM 资产
13. 发布第一个开源 tag 或 GitHub Release

## 开源就绪度评估

当前粗略评估：

- 代码结构：70%
- 可复现性：55%
- 数据可信度：50%
- 许可证和仓库治理：35%
- 外部贡献体验：45%

综合开源就绪度约 55%。完成 P0 后，可提升到约 75%；完成 P1 后，基本可以作为公开 alpha 版本发布。
