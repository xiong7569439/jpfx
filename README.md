# 竞品策略监控系统

> 独立站虚拟充值竞品策略监控分析员 - 每日自动生成结构化竞品日报

## 项目简介

自动监控竞品在游戏充值/点卡业务上的策略变化，输出结构化、可执行的《竞品策略变动日报》。

**监控站点**：
- **LootBar** - 竞品站点
- **LDShop** - 竞品站点
- **Trustpilot** - 第三方评价平台（评价数据基准）

**重点游戏**：原神、PUBG、崩坏星穹铁道、绝区零、鸣潮、无尽对决、王者荣耀、三角洲行动、暗区突围

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         每日任务调度                             │
│                     (APScheduler - 每日17:00)                   │
└─────────────────────────────┬─────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│    数据采集     │  │    数据解析     │  │    差异对比     │
│   (Collector)   │  │    (Parser)     │  │   (DiffEngine)  │
│                 │  │                 │  │                 │
│ - Browser       │  │ - DataExtractor │  │ - 快照对比      │
│ - Crawler       │  │ - PageNavigator │  │ - 变化检测      │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                        数据分析模块 (Analyzer)                    │
├─────────────┬──────────────┬───────────────┬──────────────────┤
│ 价格对比     │ 价格趋势      │ 促销分析      │ 支付监控         │
│ 差异分析     │ 7日走势      │ 9种促销类型    │ 渠道覆盖         │
├─────────────┼──────────────┼───────────────┼──────────────────┤
│ 库存监控     │ 评价分析      │ 结算链路      │ 新增游戏         │
│ 可购买状态    │ Trustpilot   │ 摩擦分析      │ 产品线扩展       │
└─────────────┴──────────────┴───────────────┴──────────────────┘
                              │
                              ▼
         ┌────────────────────┬────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   报告生成      │  │   邮件发送      │  │  可视化仪表盘    │
│   (Reporter)    │  │   (MailSender)  │  │   (Dashboard)   │
│                 │  │                 │  │                 │
│ - Markdown日报  │  │ - 邮件推送      │  │ - Flask Web     │
│ - CSV数据       │  │ - 报告附件      │  │ - 图表展示       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## 核心功能

| 模块 | 功能说明 |
|------|---------|
| **价格对比** | 竞品间同SKU价差对比，直接影响定价决策 |
| **价格趋势** | 7日价格走势、竞争力评分、异常波动预警 |
| **SKU监控** | 新增/下架/调价监控，产品策略C维度 |
| **促销策略** | 9种促销类型识别、实际折扣率计算 |
| **支付方式** | 支付渠道覆盖监控、竞争差距分析 |
| **结算链路** | 结算体验摩擦分析、转化漏斗优化 |
| **库存监控** | 商品可购买状态、缺货监控 |
| **评价分析** | 基于Trustpilot的第三方评价数据 |
| **新增游戏** | 发现竞品新上线的游戏品类 |

## 技术栈

- **Python 3.8+** - 核心开发语言
- **Playwright** - 浏览器自动化、页面抓取
- **BeautifulSoup** - HTML解析、数据提取
- **Flask** - 数据可视化仪表盘
- **APScheduler** - 定时任务调度
- **PyYAML** - 配置文件管理

## 目录结构

```
jpfx/
├── config/                      # 配置文件
│   ├── sites.yaml              # 站点与游戏配置
│   ├── settings.yaml           # 系统设置
│   ├── scheduler.yaml          # 调度配置
│   └── url_manifest.json       # URL监控清单
├── src/
│   ├── collector/              # 数据采集
│   │   ├── browser.py         # Playwright浏览器管理
│   │   └── crawler.py         # 爬虫主模块
│   ├── parser/                # 数据解析
│   │   ├── data_extractor.py  # 结构化数据提取
│   │   └── page_navigator.py  # 页面导航
│   ├── analyzer/              # 数据分析
│   │   ├── diff_engine.py     # 差异对比引擎
│   │   ├── change_classifier.py    # 变化归类
│   │   ├── price_comparison.py     # 价格对比
│   │   ├── price_trend.py          # 价格趋势
│   │   ├── promotion_analyzer.py   # 促销分析
│   │   ├── review_analyzer.py      # 评价分析
│   │   ├── checkout_analyzer.py    # 结算链路
│   │   └── payment_monitor.py      # 支付监控
│   ├── reporter/              # 报告生成
│   │   ├── report_builder.py       # 日报构建
│   │   └── mail_sender.py          # 邮件发送
│   ├── dashboard/             # 可视化仪表盘
│   │   ├── app.py             # Flask应用
│   │   ├── templates/         # HTML模板
│   │   └── static/            # 静态资源
│   ├── scheduler/             # 任务调度
│   │   └── daily_job.py       # 每日任务
│   └── config_loader.py       # 配置加载
├── data/                       # 数据存储
│   ├── snapshots/             # 页面快照(HTML/TXT)
│   ├── parsed/                # 结构化解析数据
│   └── history/               # 历史数据
├── reports/                    # 报告输出
│   ├── competitor_report_*.md # Markdown日报
│   ├── price_trend_*.csv      # 价格趋势数据
│   ├── promotion_analysis_*.csv  # 促销分析
│   ├── review_analysis_*.csv  # 评价分析
│   └── payment_analysis_*.csv    # 支付监控
├── logs/                       # 日志文件
├── main.py                     # 主入口
├── run_dashboard.py           # 仪表盘启动
└── requirements.txt           # 依赖清单
```

## 快速开始

### 环境要求

- Python 3.8+
- Windows/Linux/macOS

### 安装步骤

```bash
# 克隆项目
git clone <repository-url>
cd jpfx

# 安装依赖
pip install -r requirements.txt

# 安装浏览器
playwright install chromium
```

### 配置

1. 编辑 `config/sites.yaml` - 配置监控站点和目标游戏
2. 编辑 `config/settings.yaml` - 配置邮件发送参数
3. 编辑 `config/url_manifest.json` - 配置监控页面URL

### 运行

```bash
# 初始化系统
python main.py --init

# 运行单次监控任务
python main.py

# 运行指定日期
python main.py --date 2026-03-01

# 启动定时调度（每日17:00）
python main.py --schedule

# 启动数据可视化仪表盘
python run_dashboard.py
```

仪表盘访问地址：http://localhost:5000

### Windows定时任务

```powershell
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "D:\coding\jpfx\main.py"
$trigger = New-ScheduledTaskTrigger -Daily -At "17:30"
Register-ScheduledTask -TaskName "CompetitorMonitor" -Action $action -Trigger $trigger
```

## 报告输出

每日运行后生成：

**日报文档**：
- `reports/competitor_report_YYYY-MM-DD.md` - Markdown格式竞品策略变动日报

**数据文件（CSV）**：
- `reports/price_trend_YYYY-MM-DD.csv` - 7日价格趋势数据
- `reports/promotion_analysis_YYYY-MM-DD.csv` - 促销策略分析数据
- `reports/review_analysis_YYYY-MM-DD.csv` - 用户反馈分析数据
- `reports/payment_analysis_YYYY-MM-DD.csv` - 支付方式监控数据

## 数据源说明

本项目以 **Trustpilot** 平台数据为唯一评价基准：
- 忽略各竞品网站站内评价数量变化
- 仅从 Trustpilot 获取 LootBar 和 LDShop 的第三方评价数据
- 确保评价数据的客观性与可信度

## License

MIT
