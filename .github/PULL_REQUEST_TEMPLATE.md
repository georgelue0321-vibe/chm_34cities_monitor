## 变更类型

- [ ] Bug 修复
- [ ] 新功能
- [ ] 数据更新（NBS/收储/成交等）
- [ ] 评分算法调整
- [ ] UI/样式优化
- [ ] 破坏性变更
- [ ] 文档更新
- [ ] 测试补充

## 变更描述

<!-- 简要说明做了什么、为什么这么做 -->

## 相关 Issue

<!-- 关联的 Issue 编号，如无则留空 -->
Closes #

## 测试情况

- [ ] `python3 -m china_housing_monitor --no-scrape` 通过
- [ ] `python3 tests/test_scoring_rigor.py` 全部通过
- [ ] 浏览器打开 `chm.html` 手动验证
- [ ] 移动端视口检查（如涉及 UI 变更）

## 检查清单

- [ ] 无新增 pip 依赖（项目零依赖原则）
- [ ] 未直接修改 `china_monitor_db.sqlite`
- [ ] 文字字段引用原始来源，非 AI 生成
- [ ] `init_db()` 兼容（不破坏现有数据迁移逻辑）
- [ ] 浅色/暗色主题均正常（如涉及 UI）
- [ ] AGENTS.md / PITFALLS.md 已更新（如涉及架构变更）
