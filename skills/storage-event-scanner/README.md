# Storage Event Scanner

收储事件智能扫描器 - CHM v0.8 数据采集工具

## 功能特性

- **智能去重** - 自动识别同一事件的不同报道
- **来源验证** - 验证URL可访问性，按优先级选择信息源
- **阶段分类** - 明确区分6个事件阶段
- **质量控制** - 记录来源可信度

## 安装

无需额外依赖，使用Python标准库。

## 使用方法

### 命令行

```bash
# 扫描单个城市
python3 scripts/scanner.py --city sy

# 扫描所有城市
python3 scripts/scanner.py --all

# 仅导入现有结果
python3 scripts/scanner.py --import-only
```

### 作为模块使用

```python
from scripts.scanner import scan_city, deduplicate_events
from scripts.source_validator import SourceValidator
from scripts.stage_classifier import StageClassifier

# 扫描城市
events = scan_city("sy", "沈阳")

# 去重
deduplicated = deduplicate_events(events)

# 分类
classifier = StageClassifier()
for event in deduplicated:
    stage, weight = classifier.classify(event["title"])
    event["stage"] = stage
```

## 事件阶段

| 阶段 | 权重 | 说明 |
|------|------|------|
| 政策表态 | 10 | 政府文件、方案、通知 |
| 房源征集 | 25 | 征集公告、招标 |
| 正式招标 | 45 | 招标公告、采购 |
| 成交公示 | 70 | 中标、成交公示 |
| 签约收购 | 90 | 签约、签署协议 |
| 改造完成 | 100 | 竣工、交付、配租配售 |

## 信息源优先级

| 优先级 | 来源类型 | 说明 |
|--------|----------|------|
| 100 | gov_official | 政府官网 |
| 90 | gov_wechat | 官方微信 |
| 80 | state_media | 国家媒体 |
| 70 | local_media | 地方媒体 |
| 60 | industry_media | 行业媒体 |
| 50 | other | 其他 |

## 测试

```bash
python3 tests/test_deduplication.py
```

## 文件结构

```
storage-event-scanner/
├── SKILL.md                    # Skill说明
├── README.md                   # 本文件
├── scripts/
│   ├── scanner.py              # 主扫描逻辑
│   ├── deduplicator.py         # 去重器
│   ├── source_validator.py     # 来源验证器
│   ├── stage_classifier.py     # 阶段分类器
│   └── db_importer.py          # 数据库导入器
├── templates/
│   └── source_priority.json    # 来源优先级配置
├── tests/
│   └── test_deduplication.py   # 去重测试
└── results/                    # 扫描结果目录
```
