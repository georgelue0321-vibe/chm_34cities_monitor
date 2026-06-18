# 贡献指南

感谢你对 China Housing Monitor (CHM) 项目的关注！无论是报告 Bug、建议新功能，还是提交代码，每一份贡献都很有价值。

## 报告 Bug

发现 Bug？请通过 [GitHub Issues](../../issues) 提交，包含以下信息：

1. **问题描述**：清晰简洁地说明遇到的问题
2. **复现步骤**：如何触发这个 Bug
3. **期望行为**：你认为正确的行为是什么
4. **实际行为**：实际发生了什么
5. **环境信息**：操作系统、Python 版本等
6. **相关截图**：如果有 UI 问题，请附上截图

## 建议新功能

有好的想法？同样通过 [GitHub Issues](../../issues) 提交，标记为 `enhancement`：

1. 说明这个功能解决什么问题
2. 描述你期望的实现方式
3. 如果有参考项目或设计，请一并提供

## 开发环境设置

### 前置要求

- Python 3.11+
- 无需安装任何第三方依赖

### 快速开始

```bash
# 克隆项目
git clone https://github.com/georgelue0321-vibe/chm_34cities_monitor.git
cd chm_34cities_monitor

# 运行完整管道（初始化 → 爬取 → 评分 → 生成 HTML）
python3 -m china_housing_monitor

# 运行测试
python3 tests/test_scoring_rigor.py
```

### 项目结构

```
china_housing_monitor/    ← Python 包（14 个模块）
├── config.py             ← 常量、路径、城市定义
├── crawler.py            ← 链家爬虫
├── db/                   ← 数据库初始化和种子数据
├── scoring/              ← 评分算法
├── data/                 ← 数据组装和图表辅助
└── report/               ← HTML 模板和静态资源

china_monitor_db.sqlite   ← SQLite 数据库（gitignored）
chm.html                  ← 生成的 HTML 仪表盘
tests/                    ← 测试套件
```

## 代码规范

### 基本原则

- **零依赖**：只使用 Python 3 标准库，不要引入第三方包
- **英文代码**：变量名、函数名、注释使用英文
- **中文 UI**：所有面向用户的文本使用中文（zh-CN）
- **城市 ID**：使用小写拼音缩写（如 `bj`、`sh`、`cd`）

### Python 代码风格

- 遵循 PEP 8 规范
- 函数和类添加 docstring
- 类型注解（Type Hints）用于关键函数
- 常量使用 UPPER_SNAKE_CASE

### 数据库相关

- 数据质量状态：`official` > `scraped` > `estimated` > `demo` > `missing`
- 文字字段必须引用原始来源（券商研报、政府公告）原文，禁止 AI 生成或总结
- 新增数据时记录 `data_quality_log`

### UI 相关

- 图表使用 ApexCharts（折线图）和 ECharts（地图）
- 移动端优先设计
- 浅色/暗色主题双适配

## 提交流程

### 1. Fork 项目

```bash
# Fork 后克隆你的副本
git clone https://github.com/YOUR_USERNAME/chm_34cities_monitor.git
cd chm_34cities_monitor

# 添加上游远程仓库
git remote add upstream https://github.com/georgelue0321-vibe/chm_34cities_monitor.git
```

### 2. 创建功能分支

```bash
# 同步上游最新代码
git fetch upstream
git checkout -b feature/your-feature-name upstream/main
```

### 3. 开发和测试

```bash
# 编写代码后运行测试
python3 tests/test_scoring_rigor.py

# 手动验证 HTML 输出
python3 -m china_housing_monitor --no-scrape
open chm.html
```

### 4. 提交代码

```bash
git add .
git commit -m "feat: add your feature description"
```

提交信息格式：
- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `style:` 代码格式调整（不影响功能）
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具链变更

### 5. 发起 Pull Request

```bash
git push origin feature/your-feature-name
```

然后在 GitHub 上发起 PR，包含：
1. 清晰的标题和描述
2. 关联的 Issue（如果有）
3. 变更内容的详细说明
4. 测试结果截图（如果有 UI 变更）

## 测试要求

- 所有新功能必须包含测试
- 测试文件位于 `tests/` 目录
- 运行 `python3 tests/test_scoring_rigor.py` 确保所有测试通过
- 测试会自动创建独立的测试数据库，不影响生产数据

## 代码审查

所有 PR 都需要通过代码审查。审查重点：

1. 是否符合项目架构和代码规范
2. 是否引入了不必要的依赖
3. 测试是否充分
4. 文档是否需要更新
5. UI 变更是否适配移动端和两种主题

## 联系方式

如果你有任何问题，可以通过以下方式联系：

- GitHub Issues：[链接待填写]
- Email：[待填写]
- 微信：[待填写]

---

再次感谢你的贡献！每一份帮助都让 CHM 变得更好。
