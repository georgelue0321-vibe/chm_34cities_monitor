# CHM 开源修复复验报告

> **状态**: 已通过  
> **复验日期**: 2026-06-17  
> **复验 HEAD**: `3368342 docs: update revalidation report - all tests pass in clean repo`

本文档记录对最新 HEAD 的独立复验结果。复验使用 `git archive HEAD` 创建只包含已追踪文件的干净仓库副本，避免依赖本地 SQLite、scratch 文件、生成产物或未追踪资源。

## 结论

当前状态：**已通过**。

干净仓库完整验证链路已经通过：

- 编译检查通过
- `python3 -m china_housing_monitor --no-scrape` 成功生成 `chm.html`
- 31 个评分测试全部通过或按预期跳过
- storage scanner 去重测试通过
- storage scanner contract 测试通过

## 复验命令

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

### 入口和构建

```text
China Housing Monitor (CHM) v1.0.0
Master standalone dashboard compiled successfully
```

确认：

- CLI 版本显示 `v1.0.0`
- fresh repo 可以初始化 DB
- fresh repo 可以生成 `chm.html`
- `china_housing_monitor/report/static/china.json` 已被追踪，地图资源可用于生成 HTML

### 评分测试

结果摘要：

```text
ALL VERIFICATION TESTS COMPLETED SUCCESSFULLY! (31/31 PASS)
```

关键项：

- Test 1-7: PASS
- Test 8: SKIP，clean repo 无 NBS 历史数据，属于预期跳过
- Test 9-25: PASS
- Test 26: PASS，已改为扫描模块化源码目录，不再依赖旧单文件 `china_housing_monitor.py`
- Test 27-31: PASS

### Scanner 测试

去重测试：

```text
All tests passed!
```

Contract 测试：

```text
All CHM contract tests passed.
```

## 修复清单复核

| ID | 问题 | 当前状态 |
|---|---|---|
| P0-1 | 测试 fixture 数据不足 | 已处理，Test 8 在 clean repo 中按预期 SKIP |
| P0-2 | `listings=-1` 仍被标记为可评分 | 已修复 |
| P1-1 | 版本号未统一 | 已修复，CLI/README/页脚均为 `v1.0.0` |
| P1-2 | 数据文档与爬虫行为不一致 | 已修复，链家失败策略为 `missing` / 不生成 synthetic |
| Test 8 | 依赖生产 DB 完整数据 | 已处理 |
| Test 9 | 依赖旧单文件结构 | 已处理 |
| Test 26 | 依赖旧单文件结构 | 已处理 |

## 仍需人工确认的非阻塞项

以下不阻塞当前 CI/干净仓库验证，但开源发布前仍建议人工确认：

- `THIRD_PARTY_NOTICES.md` 中 GeoJSON、Remotion、历史 BGM 的来源和许可证描述是否足够严谨
- `professional_opinions` 中券商共识文字是否已经全部有可核验来源，或是否需要在开源版中降级/移除无来源内容
- 是否要从 git 历史中清理曾经出现过的音频或视频相关资产

## 最终判断

从工程可复现角度看，本轮开源修复可以视为通过：

- 干净仓库能生成报告
- 干净仓库测试链路通过
- CI 路径预期可通过

下一步可以进入开源发布前的人工合规确认和 release 准备。
