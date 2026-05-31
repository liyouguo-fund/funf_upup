# 基金趋势分析系统

基于 Python 的场外基金与宽基指数趋势分析工具，采用 WMA（加权移动平均）和 EMA（指数移动平均）指标进行量化分析。

## 功能特性

- **场外基金分析**：使用 WMA 加权移动平均计算趋势线，结合 5 日高低价和布林带
- **宽基指数分析**：使用 EMA 指数移动平均计算趋势线
- **邮件报告**：自动生成 HTML 格式的分析报告，支持邮件发送
- **GitHub Actions**：支持每日定时自动运行，自动发送邮件通知

## 项目结构

```
.
├── .github/workflows/
│   └── fund-analysis.yml    # GitHub Actions 工作流配置
├── 基金趋势大模型_WMA.py     # 场外基金趋势分析（WMA版本）
├── 宽基指数趋势大模型_EMA.py  # 宽基指数趋势分析（EMA版本）
├── requirements.txt          # Python 依赖列表
├── .gitignore               # Git 忽略配置
└── README.md                # 项目说明文档
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 依赖列表

- pandas：数据处理
- numpy：数值计算
- matplotlib：图表绘制
- xalpha：基金数据获取
- openpyxl：Excel 导出
- pywencai：问财数据接口
- baostock：股票指数数据获取

## 使用方法

### 本地运行

```bash
# 运行场外基金分析
python "基金趋势大模型_WMA.py"

# 运行宽基指数分析
python "宽基指数趋势大模型_EMA.py"
```

### 环境变量配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| WENCAI_QUERY | 问财查询语句 | 场外基金近1年涨幅top200 |

### GitHub Actions 配置

在 GitHub Secrets 中添加以下配置：

| Secret | 示例值 | 说明 |
|--------|--------|------|
| SMTP_SERVER | `smtp.qq.com` | QQ 邮箱 SMTP 服务器地址 |
| SMTP_PORT | `465` | QQ 邮箱 SMTP 端口（SSL 加密） |
| SMTP_USER | `123456789@qq.com` | 发件人 QQ 邮箱地址 |
| SMTP_PASSWORD | `abcdefghijklmn` | QQ 邮箱授权码（非 QQ 密码） |
| RECIPIENTS | `recipient1@qq.com,recipient2@example.com` | 收件人邮箱（多个用逗号分隔） |
| WENCAI_QUERY | `场外基金近1年涨幅top200` | 问财查询语句（可选） |

#### 如何获取 QQ 邮箱授权码

1. 登录 QQ 邮箱网页版
2. 点击 **设置** → **账户**
3. 找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务**
4. 开启 **SMTP 服务**
5. 点击 **生成授权码**（需要手机验证码）
6. 将生成的授权码填入 GitHub Secrets 的 `SMTP_PASSWORD` 中

## 指标说明

### WMA（加权移动平均）
- 权重从周期递减到1
- 公式: WMA = (N×P1 + (N-1)×P2 + ... + 1×PN) / (N×(N+1)/2)

### EMA（指数移动平均）
- 对近期数据赋予更高权重
- alpha = 2 / (period + 1)

### 偏离率
- 衡量当前价格相对于趋势线的偏离程度
- 公式: (现价 - 趋势线) / 趋势线 × 100%

### 信号强度
- 极强: 偏离率 > 5%
- 强势: 偏离率 2% ~ 5%
- 偏强: 偏离率 0% ~ 2%
- 偏弱: 偏离率 -2% ~ 0%
- 超卖: 偏离率 < -2%

## 输出文件

运行后生成的文件：
- `基金趋势分析.xlsx`：场外基金分析结果
- `宽基指数趋势分析.xlsx`：宽基指数分析结果
- `基金与指数趋势分析.xlsx`：整合报告
- `基金趋势图_YYYYMMDD/`：基金趋势图表
- `宽基指数邮件正文.html`：邮件报告正文

## 许可证

MIT License