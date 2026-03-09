# TOPUPlive 竞品策略监控系统

> 独立站虚拟充值竞品策略监控分析员 - 每日自动生成结构化竞品日报

## 项目简介

服务于 **TOPUPlive** 运营的竞品策略监控系统，自动监控竞品在游戏充值/点卡业务上的策略变化，输出结构化、可执行的《竞品策略变动日报》。

**监控站点**：
- **TOPUPlive**（我方）- 独立站虚拟充值平台
- **LootBar** - 竞品站点
- **LDShop** - 竞品站点
- **Trustpilot** - 第三方评价平台（评价数据基准）

**重点游戏**：原神、PUBG、崩坏星穹铁道、绝区零、鸣潮、无尽对决、王者荣耀、三角洲行动、暗区突围

## 数据源说明

### 评价数据来源
本项目以 **Trustpilot** 平台数据为唯一评价基准：
- 忽略各竞品网站站内评价数量变化
- 仅从 Trustpilot 获取 LootBar 和 LDShop 的第三方评价数据
- 确保评价数据的客观性与可信度

## 核心功能

| 功能模块 | 说明 |
|---------|------|
| 价格对比 | 竞品间价差对比，直接影响定价策略 |
| 价格趋势 | 7日价格走势、竞争力评分、异常波动预警 |
| SKU监控 | 新增/下架/调价监控，产品策略C维度 |
| 促销策略 | 9种促销类型识别、实际折扣率计算 |
| 支付方式 | 支付渠道覆盖监控、竞争差距分析 |
| 结算链路 | 结算体验摩擦分析、优化建议 |
| 库存监控 | 商品可购买状态、缺货监控 |
| 评价分析 | 基于Trustpilot的第三方评价数据分析 |
| 新增游戏 | 发现竞品新上线的游戏品类 |

## 技术栈

- **Python 3.8+** - 核心开发语言
- **Playwright** - 浏览器自动化、页面抓取
- **BeautifulSoup** - HTML解析、数据提取
- **Flask** - 数据可视化仪表盘
- **APScheduler** - 定时任务调度

## 安装与运行

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

1. 编辑 `config/sites.yaml` 配置监控站点
2. 编辑 `config/settings.yaml` 配置邮件发送参数
3. 编辑 `config/url_manifest.json` 配置监控页面URL

### 运行

```bash
# 运行单次监控任务
python main.py

# 启动数据可视化仪表盘
python run_dashboard.py

# 设置定时任务（每天17:30）
python main.py --schedule
```

仪表盘访问地址：http://localhost:5000

## 目录结构

```
jpfx/
├── config/              # 配置文件
│   ├── sites.yaml       # 站点配置
│   ├── settings.yaml    # 系统设置
│   ├── scheduler.yaml   # 调度配置
│   └── url_manifest.json # URL清单
├── src/
│   ├── collector/       # 数据采集（爬虫、浏览器控制）
│   ├── parser/          # 数据解析（结构化提取）
│   ├── analyzer/        # 数据分析（差异、趋势、促销、评价）
│   ├── reporter/        # 报告生成（日报、邮件）
│   ├── dashboard/       # 可视化仪表盘
│   └── scheduler/       # 任务调度
├── data/                # 数据存储
│   ├── snapshots/       # 页面快照（HTML/文本）
│   ├── parsed/          # 结构化解析数据
│   └── history/         # 历史数据
├── reports/             # 报告输出（Markdown/CSV）
├── logs/                # 日志文件
├── main.py              # 主入口
├── run_dashboard.py     # 仪表盘启动
└── requirements.txt     # 依赖清单
```

## 使用说明

### 单次运行

```bash
# 运行今日监控
python main.py

# 运行指定日期
python main.py --date 2026-03-01
```

### 定时任务（Windows）

```powershell
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "D:\coding\jpfx\main.py"
$trigger = New-ScheduledTaskTrigger -Daily -At "17:30"
Register-ScheduledTask -TaskName "CompetitorMonitor" -Action $action -Trigger $trigger
```

### 查看报告

每日运行后生成：

**日报文档**：
- `reports/competitor_report_YYYY-MM-DD.md` - Markdown格式竞品策略变动日报

**数据文件（CSV）**：
- `reports/price_trend_YYYY-MM-DD.csv` - 7日价格趋势数据
- `reports/promotion_analysis_YYYY-MM-DD.csv` - 促销策略分析数据
- `reports/review_analysis_YYYY-MM-DD.csv` - 用户反馈深度分析数据

## 贡献方式

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 开源协议

[MIT](LICENSE) © TOPUPlive
