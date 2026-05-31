"""
宽基指数趋势大模型 - EMA版本 - 逸飞ETF量化

指标计算（使用EMA指数移动平均）：
- 趋势线: (最高价 + 最低价) / 2 的20日指数移动平均(EMA)
- 偏离率: (现价 - 趋势线) / 趋势线 × 100%
- 强度排序: 按偏离率数值排序，数值最大=1（最强）

"""

import baostock as bs
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta


def get_stock_data(stock_code: str, days: int = 100, end_date: str = None) -> pd.DataFrame:
    """获取股票/指数数据"""
    bs.login()
    
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=days)).strftime('%Y-%m-%d')
    
    rs = bs.query_history_k_data_plus(
        stock_code,
        'date,code,open,high,low,close,volume',
        start_date=start_date,
        end_date=end_date,
        frequency='d'
    )
    
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    
    bs.logout()
    
    df = pd.DataFrame(data_list, columns=rs.fields)
    
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df


def calculate_indicators_ema(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    计算趋势线指标（使用EMA指数移动平均）
    
    公式：
    1. 均价 = (最高价 + 最低价) / 2
    2. 趋势线 = 均价的20日指数移动平均(EMA)
       EMA_t = alpha × price_t + (1-alpha) × EMA_{t-1}
       alpha = 2 / (period + 1) = 2/21 ≈ 0.0952
    """
    # 计算 (最高价 + 最低价) / 2
    df['hl2'] = (df['high'] + df['low']) / 2
    
    # 计算20日指数移动平均(EMA)
    # adjust=False 表示使用标准的递归 EMA 计算
    df['trend_line'] = df['hl2'].ewm(span=period, adjust=False).mean()
    
    # 计算偏离率
    df['deviation'] = (df['close'] - df['trend_line']) / df['trend_line'] * 100
    
    return df


def analyze_index(stock_code: str, name: str = None, period: int = 20) -> dict:
    """分析单只指数/股票"""
    try:
        df = get_stock_data(stock_code, days=period * 4)
        df = calculate_indicators_ema(df, period)
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        today_change = (latest['close'] - prev['close']) / prev['close'] * 100
        
        change_5d = 0
        change_20d = 0
        if len(df) > 5:
            change_5d = (df['close'].iloc[-1] - df['close'].iloc[-6]) / df['close'].iloc[-6] * 100
        if len(df) > 20:
            change_20d = (df['close'].iloc[-1] - df['close'].iloc[-21]) / df['close'].iloc[-21] * 100
        
        # 根据偏离率确定信号强度
        dev = latest['deviation']
        if dev > 5:
            signal = '极强'
        elif dev > 2:
            signal = '强势'
        elif dev > 0:
            signal = '偏强'
        elif dev > -2:
            signal = '偏弱'
        else:
            signal = '超卖'
        
        return {
            'code': stock_code,
            'name': name or stock_code,
            'current_price': latest['close'],
            'trend_line': latest['trend_line'],
            'deviation': latest['deviation'],
            'signal': signal,
            'today_change': today_change,
            'change_5d': change_5d,
            'change_20d': change_20d,
        }
        
    except Exception as e:
        return {'code': stock_code, 'name': name or stock_code, 'error': str(e)}


def display_analysis(results: list) -> str:
    """展示分析结果，返回文本格式输出"""
    output_lines = []
    
    # 过滤掉有错误的结果
    valid_results = [r for r in results if 'current_price' in r]
    valid_results.sort(key=lambda x: x.get('deviation', 0), reverse=True)
    
    header = '=' * 95
    output_lines.append(header)
    output_lines.append('宽基指数趋势大模型 - EMA版本')
    output_lines.append('   日期: ' + datetime.now().strftime('%Y年%m月%d日'))
    output_lines.append(header)
    output_lines.append('{:<4} {:<12} {:>10} {:>8} {:>8} {:>9} {:>10} {:>8} {:<6}'.format(
        '强度', '指数名称', '现价', '今日涨跌', '5日涨跌', '20日涨跌', '趋势线', '偏离率', '信号'))
    output_lines.append('-' * 95)
    
    for i, r in enumerate(valid_results, 1):
        output_lines.append('{:<4} {:<12} {:>10.3f} {:>+7.2f}% {:>+7.2f}% {:>+8.2f}% {:>10.3f} {:>+7.2f}% {:<6}'.format(
            i, r['name'], r['current_price'], r['today_change'], 
            r['change_5d'], r['change_20d'], r['trend_line'], r['deviation'], r['signal']))
    
    output_lines.append(header)
    output_lines.append('趋势线 = (最高价+最低价)/2 的20日指数移动平均(EMA)')
    output_lines.append('EMA alpha = 2/(period+1) = 2/21 ≈ 0.0952')
    output_lines.append('偏离率 = (现价-趋势线)/趋势线 × 100%')
    output_lines.append('强度排序按偏离率数值，数值越大=短期走势越强')
    output_lines.append('EMA相比SMA对近期数据更敏感，反应更灵敏')
    output_lines.append(header)
    
    return '\n'.join(output_lines)


def generate_email_body(results: list) -> str:
    """生成邮件正文格式的分析报告"""
    # 过滤掉有错误的结果
    valid_results = [r for r in results if 'current_price' in r]
    valid_results.sort(key=lambda x: x.get('deviation', 0), reverse=True)
    
    body_lines = []
    
    body_lines.append('<html>')
    body_lines.append('<head>')
    body_lines.append('<meta charset="UTF-8">')
    body_lines.append('<style>')
    body_lines.append('table { border-collapse: collapse; width: 100%; font-size: 14px; }')
    body_lines.append('th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }')
    body_lines.append('th { background-color: #f2f2f2; }')
    body_lines.append('tr:nth-child(even) { background-color: #f9f9f9; }')
    body_lines.append('.strong { color: #c00; font-weight: bold; }')
    body_lines.append('.weak { color: #060; }')
    body_lines.append('</style>')
    body_lines.append('</head>')
    body_lines.append('<body>')
    body_lines.append(f'<h2>📊 宽基指数趋势分析报告</h2>')
    body_lines.append(f'<p><strong>日期：</strong>{datetime.now().strftime("%Y年%m月%d日")}</p>')
    body_lines.append('<p><strong>指标说明：</strong></p>')
    body_lines.append('<ul>')
    body_lines.append('<li>趋势线 = (最高价+最低价)/2 的20日指数移动平均(EMA)</li>')
    body_lines.append('<li>偏离率 = (现价-趋势线)/趋势线 × 100%</li>')
    body_lines.append('<li>强度排序按偏离率数值，数值越大=短期走势越强</li>')
    body_lines.append('</ul>')
    body_lines.append('<table>')
    body_lines.append('<tr>')
    body_lines.append('<th>强度排名</th>')
    body_lines.append('<th>指数名称</th>')
    body_lines.append('<th>现价</th>')
    body_lines.append('<th>今日涨跌</th>')
    body_lines.append('<th>5日涨跌</th>')
    body_lines.append('<th>20日涨跌</th>')
    body_lines.append('<th>趋势线</th>')
    body_lines.append('<th>偏离率</th>')
    body_lines.append('<th>信号强度</th>')
    body_lines.append('</tr>')
    
    for i, r in enumerate(valid_results, 1):
        deviation_color = 'style="color: #c00; font-weight: bold;"' if r['deviation'] > 5 else \
                         'style="color: #c60;"' if r['deviation'] > 2 else \
                         'style="color: #666;"' if r['deviation'] > 0 else \
                         'style="color: #060;"'
        
        signal_color = 'style="color: #c00; font-weight: bold;"' if r['signal'] == '极强' else \
                      'style="color: #c60;"' if r['signal'] == '强势' else \
                      'style="color: #060;"' if r['signal'] == '超卖' else \
                      'style="color: #666;"'
        
        body_lines.append('<tr>')
        body_lines.append(f'<td>{i}</td>')
        body_lines.append(f'<td>{r["name"]}</td>')
        body_lines.append(f'<td>{r["current_price"]:.3f}</td>')
        body_lines.append(f'<td>{r["today_change"]:+.2f}%</td>')
        body_lines.append(f'<td>{r["change_5d"]:+.2f}%</td>')
        body_lines.append(f'<td>{r["change_20d"]:+.2f}%</td>')
        body_lines.append(f'<td>{r["trend_line"]:.3f}</td>')
        body_lines.append(f'<td {deviation_color}>{r["deviation"]:+.2f}%</td>')
        body_lines.append(f'<td {signal_color}>{r["signal"]}</td>')
        body_lines.append('</tr>')
    
    body_lines.append('</table>')
    body_lines.append('<p style="margin-top: 15px; font-size: 12px; color: #666;">')
    body_lines.append('注：EMA相比SMA对近期数据更敏感，反应更灵敏 | 数据来源：baostock')
    body_lines.append('</p>')
    body_lines.append('</body>')
    body_lines.append('</html>')
    
    return '\n'.join(body_lines)


def export_to_excel(results: list, output_path: str = None):
    """导出分析结果到Excel"""
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 设置默认输出路径
    if output_path is None:
        output_path = os.path.join(script_dir, '宽基指数趋势分析.xlsx')
    
    # 过滤掉有错误的结果
    valid_results = [r for r in results if 'current_price' in r]
    valid_results.sort(key=lambda x: x.get('deviation', 0), reverse=True)
    
    # 准备数据
    data = []
    for i, r in enumerate(valid_results, 1):
        data.append({
            '强度': i,
            '指数代码': r['code'],
            '指数名称': r['name'],
            '现价': round(r['current_price'], 4),
            '今日涨跌': f"{r['today_change']:+.2f}%",
            '5日涨跌': f"{r['change_5d']:+.2f}%",
            '20日涨跌': f"{r['change_20d']:+.2f}%",
            '趋势线': round(r['trend_line'], 4),
            '偏离率': f"{r['deviation']:+.2f}%",
            '信号': r['signal']
        })
    
    # 创建DataFrame并导出Excel
    df = pd.DataFrame(data)
    df = df[['强度', '指数代码', '指数名称', '现价', '今日涨跌', '5日涨跌', '20日涨跌',
             '趋势线', '偏离率', '信号']]
    
    df.to_excel(output_path, index=False, engine='openpyxl')
    print(f'\nExcel表格已保存至: {output_path}')


if __name__ == "__main__":
    indices = [
        # A股主要指数
        ('sh.000001', '上证指数'),
        ('sz.399001', '深证成指'),
        ('sz.399006', '创业板指'),
        
        # 宽基ETF
        ('sh.510050', '上证50'),
        ('sh.510300', '沪深300'),
        ('sh.510500', '中证500'),
        ('sh.512100', '中证1000'),
        ('sh.563300', '国证2000'),
        
        # 风格/策略ETF
        ('sz.159949', '创业板50'),
        ('sz.159967', '创成长'),
        ('sh.588000', '科创50'),
        ('sh.588220', '科创100'),
        ('sh.512890', '红利低波'),
        
        # 跨境ETF（QDII）
        ('sz.159920', '恒生ETF'),
        ('sh.513130', '恒生科技'),
        ('sh.513100', '纳指'),
        ('sh.513030', '德国'),
        ('sh.513520', '日经'),
        ('sh.513310', '中韩半导体'),
        ('sz.164824', '印度基金'),
        
        # 商品ETF
        ('sh.518880', '黄金'),
        ('sz.161226', '白银'),
        ('sz.159985', '豆粕'),
        ('sz.162411', '华宝油气'),
    ]
    
    print('\n正在获取数据（EMA版本）...\n')
    
    results = []
    for code, name in indices:
        try:
            result = analyze_index(code, name)
            results.append(result)
            print(f'OK {name}')
        except Exception as e:
            print(f'FAIL {name}: {str(e)}')
    
    if results:
        # 显示终端输出
        output_text = display_analysis(results)
        print('\n')
        print(output_text)
        
        # 导出Excel
        export_to_excel(results)
        
        # 生成邮件正文并保存
        email_body = generate_email_body(results)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        email_body_path = os.path.join(script_dir, '宽基指数邮件正文.html')
        with open(email_body_path, 'w', encoding='utf-8') as f:
            f.write(email_body)
        print(f'\n邮件正文已保存至: {email_body_path}')
    
    print('\n分析完成!')