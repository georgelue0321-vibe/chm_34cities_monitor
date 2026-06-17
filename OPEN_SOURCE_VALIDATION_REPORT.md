# CHM 开源修复验收报告

本文档记录对提交 `67265f2 feat: open source remediation - phase 1-5 complete` 的复查结果。结论：开源修复已完成一部分关键 P0，但还没有完全通过验收，尤其是干净仓库 CI 路径仍会失败。

## 验收结论

当前状态：**未完全通过**。

已修复：

- `pboc_global` fresh init 列数不匹配问题已修复
- `market_index`、`professional_opinions` 已补 `collected_at` 迁移
- `china_housing_monitor/report/static/china.json` 已被 git 追踪，且不再被 `.gitignore` 忽略
- `LICENSE`、`THIRD_PARTY_NOTICES.md`、`.github/workflows/test.yml`、`tests/test_scoring_rigor.py` 已加入仓库
- `python3 -m china_housing_monitor --no-scrape` 能成功生成 `chm.html`

仍未通过：

- 干净仓库按 CI 顺序运行会失败
- 本地生产 DB 迁移后评分测试仍失败
- 版本号仍不统一
- 数据文档与爬虫实际行为仍不一致

## 复查环境

工作目录：

```bash
/Users/george/Documents/CHM
```

当前 HEAD：

```text
67265f2 feat: open source remediation - phase 1-5 complete
```

工作区状态：

```text
clean
```

## 已执行验收命令

### 1. 编译检查

```bash
python3 -m compileall -q china_housing_monitor skills/storage-event-scanner/scripts
```

结果：通过。

### 2. 临时空 DB 初始化

```bash
python3 -c "import tempfile, os; import china_housing_monitor.config as c; import china_housing_monitor.db.init as i; p=os.path.join(tempfile.mkdtemp(), 'fresh.sqlite'); c.DB_PATH=p; i.DB_PATH=p; i.init_db(); print('init_db OK:', p)"
```

结果：通过。

说明：

- 原先的 `pboc_global has 4 columns but 5 values were supplied` 已修复
- `market_index.collected_at`、`professional_opinions.collected_at` 迁移已执行

### 3. 地图 GeoJSON 追踪状态

```bash
git check-ignore -v china_housing_monitor/report/static/china.json || true
git ls-files china_housing_monitor/report/static/china.json
```

结果：通过。

说明：

- `git check-ignore` 无输出，说明不再被忽略
- `git ls-files` 能输出 `china_housing_monitor/report/static/china.json`

### 4. 真实入口生成 HTML

```bash
python3 -m china_housing_monitor --no-scrape
```

结果：通过。

输出显示 `Master standalone dashboard compiled successfully`。

### 5. Scanner 测试

```bash
python3 skills/storage-event-scanner/tests/test_deduplication.py
python3 skills/storage-event-scanner/tests/test_chm_contract.py
```

结果：均通过。

## 未通过问题

### P0-1：干净仓库 CI 路径失败

复现方式：

```bash
tmpdir=$(mktemp -d /tmp/chm-clean-XXXXXX)
git archive HEAD | tar -x -C "$tmpdir"
cd "$tmpdir"
python3 -m compileall -q china_housing_monitor skills/storage-event-scanner/scripts
python3 -c "import tempfile, os; import china_housing_monitor.config as c; import china_housing_monitor.db.init as i; p=os.path.join(tempfile.mkdtemp(), 'fresh.sqlite'); c.DB_PATH=p; i.DB_PATH=p; i.init_db(); print('init_db OK:', p)"
python3 -m china_housing_monitor --no-scrape
python3 tests/test_scoring_rigor.py
```

失败结果：

```text
AssertionError: Expected normal score, got 32.0
```

失败位置：

- `tests/test_scoring_rigor.py::test_missing_transaction_does_not_zero_score`
- 断言位置：`assert latest['score'] > 50`

原因判断：

- `tests/test_scoring_rigor.py` 复制根目录 `china_monitor_db.sqlite` 作为测试 DB
- 在干净仓库中，该 DB 是由 `--no-scrape` 刚初始化生成的
- fresh seed 没有完整历史 NBS 数据
- 测试只插入 1 个月价格数据，但评分逻辑 `calc_s_price` 需要足够历史序列
- 因此价格因子不足，最终分数只有 32.0

影响：

- 当前 `.github/workflows/test.yml` 在 GitHub Actions 上预计会失败
- README 中的测试命令在干净 clone 后也不可靠

建议修复：

- 方案 A：测试自带完整 fixture，不依赖根目录生产 DB
- 方案 B：在测试 setup 中为目标城市补足至少 6 个月 `city_price_index_monthly`
- 方案 C：CI 中在跑评分测试前显式准备测试 DB，而不是依赖 `--no-scrape` 的 seed

推荐方案：

- 优先选方案 B 或 A
- 不建议 CI 为测试拉线上 NBS 数据，因为这会引入网络不稳定性

### P0-2：旧生产 DB 中 `listings=-1` 仍被标记为可评分

本地复现：

```bash
python3 tests/test_scoring_rigor.py
```

失败结果：

```text
AssertionError: City bj listings=-1 but is_score_eligible=1, expected 0
```

查询结果：

```sql
SELECT COUNT(*), SUM(CASE WHEN is_score_eligible=1 THEN 1 ELSE 0 END)
FROM market_index
WHERE listings=-1;
```

当前结果：

```text
34|34
```

原因判断：

- 旧生产 DB 中 2026-05 中指数据记录 `listings=-1`
- `data_status='official'`、`source_label='中指研究院'`、`is_score_eligible=1`
- 这可能表示“价格是官方/中指可用”，但“挂牌量不可用”
- 当前数据模型用一个 `is_score_eligible` 同时承载价格和挂牌两个语义，导致测试和数据语义冲突

影响：

- 本地迁移后的测试失败
- 开源后用户如果带旧 DB 升级，也会遇到同类问题

建议修复：

- 短期：在迁移中规范化 `market_index`：

```sql
UPDATE market_index
SET is_score_eligible = 0
WHERE listings = -1;
```

- 更稳妥：拆分字段语义：
  - `price_is_score_eligible`
  - `listing_is_score_eligible`
  - 或将 `market_index` 的价格源和挂牌源拆表

注意：

- 如果 `source_label='中指研究院'` 的价格仍要用于展示，不应因为 `listings=-1` 抹掉价格可用性
- 修复时要明确“评分 eligibility”和“展示 eligibility”的区别

### P1-1：版本号仍未统一

发现：

- `china_housing_monitor/__init__.py`：`__version__ = "0.10.0"`
- `china_housing_monitor/__main__.py`：CLI 仍打印 `China Housing Monitor (CHM) v2.0.0`
- `china_housing_monitor/report/templates/base.html`：页脚仍显示 `CHM v0.9`
- `DATA_SOURCES.md`：仍写 `基于 v0.9.3 代码分析`

影响：

- README、CLI、HTML、数据文档对外展示的版本不一致
- 开源首版识别混乱

建议修复：

- CLI 从 `china_housing_monitor.__version__` 读取版本
- HTML footer 用模板占位符或常量注入版本
- 文档统一为当前开源版本，例如 `v0.10.0`

### P1-2：数据文档与链家爬虫实际行为不一致

发现：

- `DATA_ACQUISITION.md` 写链家失败会“沿用上月价格 × 随机系数（0.990-0.997）”，并标记 `synthetic`
- `china_housing_monitor/crawler.py` 实际逻辑是失败后 `listings=-1`，若无价格则跳过，不插入 synthetic 数据

影响：

- 外部贡献者会误解数据生成方式
- 公开项目的数据可信度说明不准确

建议修复：

- 更新 `DATA_ACQUISITION.md`
- 明确当前策略：失败即 `missing`，不生成 synthetic 数据
- 如果历史库中仍有 synthetic/extrapolated，应说明它们是历史遗留数据

## 已通过项目

### P0 已通过

- `pboc_global` schema/插入列数不匹配已修复
- `market_index.collected_at` 已补迁移
- `professional_opinions.collected_at` 已补迁移
- `china.json` 已被 git 追踪
- `LICENSE` 已存在
- `THIRD_PARTY_NOTICES.md` 已存在

### 测试已通过

```bash
python3 -m compileall -q china_housing_monitor skills/storage-event-scanner/scripts
python3 skills/storage-event-scanner/tests/test_deduplication.py
python3 skills/storage-event-scanner/tests/test_chm_contract.py
```

### 入口已通过

```bash
python3 -m china_housing_monitor --no-scrape
```

## 下一步建议

优先级顺序：

1. 修复 `tests/test_scoring_rigor.py` 的 fresh DB fixture 问题，确保 CI 能过
2. 修复或明确 `market_index.is_score_eligible` 对 `listings=-1` 的语义
3. 统一版本号到 `0.10.0`
4. 更新 `DATA_ACQUISITION.md` 中链家失败策略
5. 再次运行干净仓库验收命令

最终验收命令建议：

```bash
tmpdir=$(mktemp -d /tmp/chm-clean-XXXXXX)
git archive HEAD | tar -x -C "$tmpdir"
cd "$tmpdir"
python3 -m compileall -q china_housing_monitor skills/storage-event-scanner/scripts
python3 -m china_housing_monitor --no-scrape
python3 tests/test_scoring_rigor.py
python3 skills/storage-event-scanner/tests/test_deduplication.py
python3 skills/storage-event-scanner/tests/test_chm_contract.py
```

该命令全部通过后，才建议认为“开源修复阶段完成”。
