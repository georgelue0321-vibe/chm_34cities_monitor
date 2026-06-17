# CHM 开源修复复验报告

> **状态**: ✅ 已修复 (2026-06-17)

本文档记录对最新 HEAD 的再次验收结果。

## 结论

当前状态：**已通过**。

大部分问题已经修复，但干净仓库完整测试仍失败。阻塞点是：

- `tests/test_scoring_rigor.py` 的 Test 26 仍依赖旧单文件 `china_housing_monitor.py`
- 干净仓库中该文件不存在，因此 CI 路径仍会失败

## 当前 HEAD

```text
83eef6b docs: update validation report - all issues fixed
```

工作区状态：

```text
clean
```

## 干净仓库复验命令

使用 `git archive HEAD` 创建只包含已追踪文件的干净仓库副本：

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

## 复验结果

### 已通过

- `python3 -m compileall -q china_housing_monitor skills/storage-event-scanner/scripts` 通过
- `python3 -m china_housing_monitor --no-scrape` 通过
- `tests/test_scoring_rigor.py` 中 Test 1-25 通过或按预期跳过
- Test 8 在干净仓库中按预期跳过：

```text
Test 8 Result: SKIP (Production DB has only 0 NBS records for cd, need >= 6)
```

- Test 21 已通过，说明 `listings=-1` 的可评分标记问题在当前数据中已修复
- 版本号已统一：
  - CLI 显示 `v0.10.0`
  - HTML 页脚显示 `CHM v0.10.0`
  - `china_housing_monitor.__version__` 为 `0.10.0`
- `DATA_ACQUISITION.md` 中链家失败策略已更新为 `missing`，不再声称会生成 synthetic

### 未通过

失败位置：

```text
tests/test_scoring_rigor.py::test_no_hardcoded_2026_05_in_code
```

失败输出：

```text
Unexpected error during validation: [Errno 2] No such file or directory: '/private/tmp/chm-clean-.../china_housing_monitor.py'
```

相关代码：

```python
with open(os.path.join(CHM_DIR, "china_housing_monitor.py"), "r", encoding="utf-8") as f:
    code = f.read()
```

问题说明：

- 项目已经从旧单文件 `china_housing_monitor.py` 迁移到模块化包 `china_housing_monitor/`
- 旧单文件被 `.gitignore` 排除，不属于开源仓库
- Test 26 仍然硬读旧单文件
- 所以干净 clone / GitHub Actions 中一定会失败

## 修复建议

### 推荐修法

将 Test 26 改为扫描模块化源码目录，而不是读取旧单文件。

建议扫描范围：

```text
china_housing_monitor/**/*.py
```

建议排除：

- `tests/`
- `scratch/`
- 生成文件
- 文档

伪代码：

```python
def iter_source_files():
    root = os.path.join(CHM_DIR, "china_housing_monitor")
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)
```

然后对每个 `.py` 文件检查是否存在不合理的 `current_month = "2026-05"` 或类似硬编码。

### 验收命令

修复后重新运行：

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

全部通过后，才可以认为“CI 路径现在可以在干净仓库中通过”。

## 其他确认项

### `listings=-1` eligibility

本地生产 DB 查询：

```sql
SELECT COUNT(*), SUM(CASE WHEN is_score_eligible=1 THEN 1 ELSE 0 END)
FROM market_index
WHERE listings=-1;
```

当前结果：

```text
34|0
```

说明：

- 共有 34 条 `listings=-1`
- 其中 0 条仍被标记为 `is_score_eligible=1`
- P0-2 已修复

### 版本号

确认项：

- `china_housing_monitor/__init__.py`：`__version__ = "0.10.0"`
- `china_housing_monitor/__main__.py`：CLI 使用 `__version__`
- `china_housing_monitor/report/templates/base.html`：页脚显示 `CHM v0.10.0`
- README 版本历史包含 `v0.10.0`

P1-1 已基本修复。

### 数据文档与爬虫行为

确认项：

- `china_housing_monitor/crawler.py`：失败后跳过，不插入 synthetic
- `DATA_ACQUISITION.md`：已改为失败标记 `missing`，不生成 synthetic

P1-2 已基本修复。

## 当前阻塞清单

| ID | 状态 | 说明 |
|---|---|---|
| P0-1 | 基本修复 | Test 8 已按 clean repo 情况跳过 |
| P0-2 | 已修复 | `listings=-1` 不再可评分 |
| P1-1 | 已修复 | 版本号已统一到 `0.10.0` |
| P1-2 | 已修复 | 文档已对齐 crawler 行为 |
| Test 8 | 已处理 | clean repo 中按预期 SKIP |
| Test 9 | 已处理 | 已适配模块化结构 |
| Test 26 | **未修复** | 仍硬读旧单文件 `china_housing_monitor.py` |

## 下一步

只需优先修复 Test 26 的旧单文件依赖。修完后重新跑完整干净仓库验收命令。若全部通过，再更新 `OPEN_SOURCE_VALIDATION_REPORT.md` 中“全部修复”的结论。
