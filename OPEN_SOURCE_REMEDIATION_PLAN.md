# CHM 开源修复执行计划

本文档是 `OPEN_SOURCE_ACTION_GUIDE.md` 的执行版。行动指南回答“还有哪些问题”，本文档回答“如果现在开始修，按什么顺序做、每一步如何验收”。

核心原则：

- 先让干净 clone 能跑，再追求开源文档体面。
- 先修 P0 可复现问题，再处理仓库治理和贡献体验。
- 每个阶段都要有明确验收命令，避免只做文档承诺。
- 不引入新的第三方 Python 依赖，延续项目零依赖定位。

## 阶段 1：P0 可复现修复

目标：让项目在没有现有 SQLite、没有本机隐藏文件的情况下，可以初始化数据库并生成 HTML。

### 任务

1. 修复 `pboc_global` schema 和插入逻辑
   - 统一字段为：`date`、`balance_billion`、`percentage`、`source`、`collected_at`
   - 避免裸 `INSERT INTO pboc_global VALUES (...)`
   - 改成显式列名插入

2. 补齐缺失的 `collected_at`
   - `market_index` 增加 `collected_at TEXT`
   - `professional_opinions` 增加 `collected_at TEXT`
   - 使用 `add_column_if_not_exists()` 保持已有 DB 可迁移

3. 追踪运行必需的地图 GeoJSON
   - 修改 `.gitignore`
   - 加入例外：`!china_housing_monitor/report/static/china.json`
   - 将 `china_housing_monitor/report/static/china.json` 纳入 git

4. 做 fresh DB 验证
   - 用临时空 DB 调用 `init_db()`
   - 再跑真实项目命令 `--init-only` 和 `--no-scrape`

### 验收命令

```bash
python3 -c "import tempfile, os; import china_housing_monitor.config as c; import china_housing_monitor.db.init as i; p=os.path.join(tempfile.mkdtemp(), 'fresh.sqlite'); c.DB_PATH=p; i.DB_PATH=p; i.init_db(); print(p)"
python3 -m china_housing_monitor --init-only
python3 -m china_housing_monitor --no-scrape
git check-ignore -v china_housing_monitor/report/static/china.json
git ls-files china_housing_monitor/report/static/china.json
```

### 完成标准

- 临时空 DB 初始化成功
- `--init-only` 成功
- `--no-scrape` 成功生成 `chm.html`
- `china.json` 不再被忽略，且已被 git 追踪

## 阶段 2：测试和 CI 基础

目标：让外部用户 clone 后可以按 README 运行测试，并让 CI 能覆盖核心行为。

### 任务

1. 迁移评分测试
   - 从 `scratch/verify_scoring_rigor.py` 迁到 `tests/test_scoring_rigor.py`
   - 保留测试 DB 复制隔离逻辑
   - 修正路径，不依赖 `scratch/`

2. 更新 README 测试命令
   - 去掉 `scratch/verify_scoring_rigor.py`
   - 改成 `tests/test_scoring_rigor.py`

3. 增加最小 CI
   - `python3 -m compileall`
   - `tests/test_scoring_rigor.py`
   - `skills/storage-event-scanner/tests/test_deduplication.py`
   - `skills/storage-event-scanner/tests/test_chm_contract.py`

4. 明确 CI 不跑爬虫
   - 网络数据更新做手动流程
   - 默认 CI 不访问链家、中指、browser-use

### 验收命令

```bash
python3 -m compileall -q china_housing_monitor skills/storage-event-scanner/scripts
python3 tests/test_scoring_rigor.py
python3 skills/storage-event-scanner/tests/test_deduplication.py
python3 skills/storage-event-scanner/tests/test_chm_contract.py
```

### 完成标准

- 所有测试在本地通过
- README 中测试命令可直接复制执行
- CI 文件存在并能跑完最小测试集

## 阶段 3：开源仓库边界清理

目标：源码仓只保留项目核心源码、必要静态资源、公开文档和测试。

### 任务

1. 清理本机路径和内部 workflow
   - 搜索 `/Users/george`
   - 搜索 `WorkBuddy`
   - 搜索 `.workbuddy`
   - 搜索 `opencode`
   - 搜索 `self-improving`
   - 将需要保留的说明改成相对路径或公开友好文案

2. 决定 `AGENTS.md` 的公开策略
   - 方案 A：保留，但清理为公开 Agent 说明
   - 方案 B：移到内部文档，不随开源仓库发布

3. 处理外部开发工具包
   - `skills/remotion-video-toolkit/` 看起来不是 CHM 核心
   - 建议移除，或在第三方声明中明确来源和许可证

4. 处理生成产物
   - `cd_price_trend.html` 当前被 git 追踪
   - 建议改为 release artifact，而不是源码仓文件
   - `chm.html` 继续保持 gitignored

5. 检查被忽略文件
   - 发布前逐项确认本地 DB、备份、scratch、`.opencode/` 等不会进入源码包或 release 包

### 验收命令

```bash
rg -n "(/Users/george|WorkBuddy|\\.workbuddy|self-improving|opencode)" .
git status --short --ignored
git ls-files | sort
```

### 完成标准

- 公开文件中无本机绝对路径
- 公开文件中无内部记忆/工作流依赖
- 外部工具包有明确保留理由或已移除
- 生成产物边界清楚

## 阶段 4：许可证、数据来源和术语统一

目标：让项目公开后，用户能理解代码许可、第三方依赖、数据来源和评分语义。

### 任务

1. 添加 `LICENSE`
   - 建议在 MIT、Apache-2.0、GPL-3.0 中明确选择
   - README 增加 License 小节

2. 添加 `THIRD_PARTY_NOTICES.md`
   - Tailwind CDN
   - ApexCharts
   - ECharts
   - Font Awesome
   - Google Fonts
   - `china.json` GeoJSON 来源
   - Remotion 工具和历史 BGM 资产

3. 统一版本号
   - `china_housing_monitor/__init__.py`
   - CLI 输出
   - HTML 页脚
   - README
   - 版本历史

4. 清理旧术语
   - `True Bottom`
   - `真底`
   - `18 cities`
   - 旧的 18 城/20 城残留

5. 对齐数据文档和实际 schema
   - `DATA_ACQUISITION.md`
   - `DATA_SOURCES.md`
   - SQLite schema
   - 特别是 `pboc_global` 字段说明

6. 整理 `professional_opinions`
   - 无来源的先降级、移除或标注不可评分
   - 后续补字段：`source_title`、`source_date`、`source_url`、`quote_type`、`methodology_note`

### 验收命令

```bash
rg -n "True Bottom|真底|18 cities|18城|20城|v2\\.0\\.0|v0\\.9" README.md DATA_ACQUISITION.md DATA_SOURCES.md china_housing_monitor
rg -n "pboc_global|report_date|facility_name|total_quota|used_pct|balance_billion|percentage" DATA_ACQUISITION.md DATA_SOURCES.md china_housing_monitor
ls -la LICENSE THIRD_PARTY_NOTICES.md
```

### 完成标准

- 旧术语无非历史上下文残留
- 版本号来源明确
- 数据文档字段与代码一致
- 第三方库、字体、地图数据、历史资产都有说明

## 阶段 5：公开前干净 clone 彩排

目标：模拟真实外部用户，确认开源仓库本身完整、命令可信、页面可打开。

### 任务

1. 在临时目录 fresh clone
2. 从零运行编译、初始化、生成、测试
3. 打开生成 HTML
4. 检查地图、导航、主要图表是否正常
5. 最后决定是否清理 git 历史中的视频/BGM 资产

### 验收命令

```bash
git clone <repo-url> chm-open-source-test
cd chm-open-source-test
python3 -m compileall -q china_housing_monitor
python3 -m china_housing_monitor --init-only
python3 -m china_housing_monitor --no-scrape
python3 tests/test_scoring_rigor.py
python3 skills/storage-event-scanner/tests/test_deduplication.py
python3 skills/storage-event-scanner/tests/test_chm_contract.py
python3 -m http.server 8080
```

### 完成标准

- fresh clone 不依赖本机隐藏文件
- fresh clone 不依赖已有 SQLite
- 所有 README 命令可执行
- 测试通过
- `chm.html` 可打开
- 地图和主图表可渲染

## 建议执行顺序

1. 修 `pboc_global` schema/插入列数不匹配
2. 修缺失的 `collected_at`
3. 追踪 `china.json`
4. 迁移评分测试到 `tests/`
5. 增加最小 CI
6. 清理个人路径和内部 workflow
7. 处理 Remotion 工具包和生成产物
8. 添加 `LICENSE` 和 `THIRD_PARTY_NOTICES.md`
9. 统一版本、术语、数据 schema 文档
10. 整理 `professional_opinions` 来源
11. 重写 README 的使用路径
12. 做干净 clone 彩排
13. 评估是否需要清理 git 历史中的 BGM/视频资产
14. 发布第一个开源 tag 或 GitHub Release

## 预期里程碑

### M1：可复现 alpha

包含阶段 1 和阶段 2。

判断标准：

- 干净环境能初始化和生成 HTML
- 测试入口可用
- CI 基础存在

### M2：公开仓库候选版

包含阶段 3 和阶段 4。

判断标准：

- 仓库边界干净
- 许可证和第三方声明完整
- 数据文档和代码一致
- 旧术语清理完成

### M3：开源发布版

包含阶段 5。

判断标准：

- fresh clone 彩排通过
- README 所有命令可信
- release artifact 策略明确
- 可以打 tag 并公开推广
