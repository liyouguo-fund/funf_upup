"""
场外基金趋势大模型 - WMA版本
===============================================

项目概述：
----------
本脚本用于分析场外基金的趋势走势，采用线性加权移动平均(WMA)作为核心指标，
结合5日高低价和布林带进行综合分析。

核心算法原理：
-------------
1. WMA（线性加权移动平均）：权重从指定周期递减到1
   公式: WMA = (N*P1 + (N-1)*P2 + ... + 1*PN) / (N*(N+1)/2)
   特点：对近期数据赋予更高权重，比简单移动平均更灵敏

2. 偏离率：衡量当前净值相对于趋势线的偏离程度
   公式: 偏离率 = (现价 - 趋势线) / 趋势线 × 100%

3. 布林带：基于标准差的价格通道
   - 中轨：20日简单移动平均
   - 上轨：中轨 + 2×标准差
   - 下轨：中轨 - 2×标准差

4. 5日高低价：平滑的价格区间表示

5. 均线多头排列：判断 ma10 > ma20 > ma30 > ma60 是否成立

输出内容：
---------
- 终端显示：基金列表按偏离率排序，包含强度排名、现价、涨跌幅等信息
- 图表输出：前3名基金的趋势分析图（含色阶背景、布林带、趋势线）
- Excel导出：所有基金指标数据导出到表格

使用说明：
---------
1. 修改 funds 列表添加要分析的基金代码
2. 运行脚本自动获取数据并生成分析报告
3. 图表保存在 g:\\场外\\基金趋势图_YYYYMMDD\\ 目录下

依赖库：
-------
- pandas: 数据处理
- numpy: 数值计算
- matplotlib: 图表绘制
- xalpha: 基金数据获取（需提前安装）
- openpyxl: Excel导出（需提前安装）
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from datetime import datetime, timedelta
import sys
import os


# 获取脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))

# 添加模块搜索路径（确保能找到xalpha库）
sys.path.insert(0, script_dir)
sys.path.insert(0, os.path.join(script_dir, 'xalpha'))


# ==================== 全局配置 ====================
# 设置字体以支持中文显示
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号
plt.rcParams['savefig.dpi'] = 150          # 保存图片的DPI
plt.rcParams['figure.dpi'] = 100           # 显示图片的DPI


def get_fund_data(fund_code, start_date=None):
    """
    获取基金净值数据（通过xalpha库）
    
    Args:
        fund_code: 基金代码（6位数字），如 '000001'
        start_date: 起始日期，格式 'YYYY-MM-DD'，默认获取最近约200天数据
    
    Returns:
        tuple: (DataFrame, fund_name)
            - DataFrame: 包含 'date'（日期）和 'nav'（单位净值）两列
            - fund_name: 基金名称（从xalpha自动获取）
    
    Raises:
        Exception: 获取数据失败时打印错误信息并返回 (None, None)
    """
    import xalpha as xa  # 延迟导入，避免启动时加载
    
    # 设置默认起始日期（约6个月前）
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=300)).strftime('%Y-%m-%d')
    
    # 确保基金代码为6位字符串（不足6位前面补零）
    fund_code = str(fund_code).zfill(6)
    
    # 提示用户正在获取数据
    print(f"正在获取基金 {fund_code} 的数据...")
    
    try:
        # 使用xalpha获取基金信息
        fund = xa.fundinfo(fund_code)
        df = fund.price.copy()  # 获取净值数据
        df = df.reset_index()   # 将日期从索引转为列
        
        # 列名标准化：确保存在 'nav' 列
        df = df.rename(columns={'netvalue': 'nav'})
        if 'nav' not in df.columns and 'totvalue' in df.columns:
            df['nav'] = df['totvalue']  # 备选方案
        
        # 只保留需要的列并处理日期格式
        df = df[['date', 'nav']].copy()
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        df = df.dropna(subset=['nav']).reset_index(drop=True)  # 去除无效数据
        
        # 根据起始日期过滤数据
        if start_date:
            df = df[df['date'] >= start_date].copy()
        
        # 获取基金名称（优先从fund对象获取，失败则使用代码）
        fund_name = getattr(fund, 'name', f'基金{fund_code}')
        print(f"获取到 {len(df)} 条净值数据（从 {df['date'].iloc[0]} 开始）")
        return df, fund_name
    
    except Exception as e:
        print(f"获取基金数据失败: {e}")
        return None, None


def calculate_wma(data, period=20):
    """
    计算线性加权移动平均 (Weighted Moving Average, WMA)
    
    WMA是一种技术分析指标，对近期数据赋予更高的权重，
    权重从period递减到1，因此比简单移动平均(SMA)更灵敏。
    
    Args:
        data: pandas Series，包含要计算的价格数据
        period: 计算周期，默认20天
    
    Returns:
        pandas Series: WMA计算结果，前period-1个值为NaN
    
    公式示例（period=3）：
        WMA = (3*P1 + 2*P2 + 1*P3) / (3+2+1)
        其中 P1 是最新数据，P3 是最早数据
    """
    # 创建权重数组 [period, period-1, ..., 1]
    weights = np.arange(period, 0, -1)
    
    def weighted_avg(x):
        """滚动窗口内的加权平均计算"""
        if len(x) < period:
            return np.nan  # 数据不足时返回NaN
        return np.sum(weights * x) / weights.sum()  # 加权求和后除以权重和
    
    # 应用滚动窗口计算WMA
    return data.rolling(window=period).apply(weighted_avg, raw=True)


def calculate_indicators_wma_5dhl(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    计算完整的趋势指标体系
    
    计算流程：
    1. 5日高低价 → 2. WMA趋势线 → 3. 布林带 → 4. 偏离率
    5. 计算各周期均线 → 6. 判断均线多头排列
    
    Args:
        df: 输入DataFrame，必须包含 'date' 和 'nav' 列
        period: WMA计算周期，默认20天
    
    Returns:
        DataFrame: 包含原始数据和所有计算指标的完整数据
    """
    df = df.copy()  # 避免修改原始数据
    
    # ========== 步骤1: 计算5日高低价 ==========
    # 使用滚动窗口计算最近5个交易日的最高/最低净值
    df['high_5d'] = df['nav'].rolling(window=5).max()
    df['low_5d'] = df['nav'].rolling(window=5).min()
    
    # 计算高低价均值 (High-Low Average)
    df['hl2_5d'] = (df['high_5d'] + df['low_5d']) / 2
    
    # ========== 步骤2: 计算WMA趋势线 ==========
    # 基于5日高低价均值计算加权移动平均
    df['trend_line'] = calculate_wma(df['hl2_5d'], period)
    
    # ========== 步骤3: 计算布林带 ==========
    # 中轨：20日简单移动平均
    df['bb_mid'] = df['nav'].rolling(window=20).mean()
    # 标准差（用于计算上下轨）
    bb_std = df['nav'].rolling(window=20).std()
    # 上轨 = 中轨 + 2×标准差
    df['bb_upper'] = df['bb_mid'] + 2 * bb_std
    # 下轨 = 中轨 - 2×标准差
    df['bb_lower'] = df['bb_mid'] - 2 * bb_std
    
    # ========== 步骤4: 计算偏离率 ==========
    # 偏离率衡量当前净值相对于趋势线的偏离程度
    df['deviation'] = (df['nav'] - df['trend_line']) / df['trend_line'] * 100
    
    # ========== 步骤5: 计算各周期均线 ==========
    df['ma10'] = df['nav'].rolling(window=10).mean()
    df['ma20'] = df['nav'].rolling(window=20).mean()
    df['ma30'] = df['nav'].rolling(window=30).mean()
    df['ma60'] = df['nav'].rolling(window=60).mean()
    
    # ========== 步骤6: 判断均线多头排列 ==========
    # 多头排列条件：ma10 > ma20 > ma30 > ma60
    df['ma_bullish'] = (df['ma10'] > df['ma20']) & (df['ma20'] > df['ma30']) & (df['ma30'] > df['ma60'])
    
    return df


def analyze_fund(fund_code: str, fund_name: str = None, period: int = 20) -> dict:
    """
    分析单只基金的完整流程（获取数据后立即计算）
    
    Args:
        fund_code: 基金代码（6位数字）
        fund_name: 基金名称（可选，若不提供则自动获取）
        period: WMA计算周期
    
    Returns:
        dict: 分析结果字典，包含：
            - code: 基金代码
            - name: 基金名称
            - current_price: 当前净值
            - high_5d/low_5d: 5日最高/最低净值
            - trend_line: 趋势线值
            - deviation: 偏离率(%)
            - today_change: 今日涨跌幅(%)
            - change_5d/change_20d: 5日/20日涨跌幅(%)
            - ma_bullish: 均线多头排列（是/否）
            - df: 完整的DataFrame数据（用于绘图）
            - error: 错误信息（如果失败）
    """
    try:
        # 1. 获取基金数据
        df, auto_name = get_fund_data(fund_code)
        
        # 2. 检查数据是否足够
        if df is None or len(df) < period + 5:
            return {
                'code': fund_code,
                'name': fund_name or auto_name or f'基金{fund_code}',
                'error': '数据不足'
            }
        
        # 3. 立即计算指标
        df = calculate_indicators_wma_5dhl(df, period)
        
        # 4. 提取最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest  # 避免只有一条数据的情况
        
        # 5. 计算涨跌幅
        today_change = (latest['nav'] - prev['nav']) / prev['nav'] * 100
        
        change_5d = 0
        change_20d = 0
        if len(df) > 5:
            change_5d = (df['nav'].iloc[-1] - df['nav'].iloc[-6]) / df['nav'].iloc[-6] * 100
        if len(df) > 20:
            change_20d = (df['nav'].iloc[-1] - df['nav'].iloc[-21]) / df['nav'].iloc[-21] * 100
        
        # 6. 判断均线多头排列
        ma_bullish = '是' if latest['ma_bullish'] else '否'
        
        # 7. 返回结果
        return {
            'code': fund_code,
            'name': fund_name or auto_name or f'基金{fund_code}',
            'current_price': latest['nav'],
            'high_5d': latest['high_5d'],
            'low_5d': latest['low_5d'],
            'trend_line': latest['trend_line'],
            'deviation': latest['deviation'],
            'today_change': today_change,
            'change_5d': change_5d,
            'change_20d': change_20d,
            'ma_bullish': ma_bullish,
            'df': df  # 保留完整数据用于绘图
        }
    
    except Exception as e:
        # 捕获所有异常并返回错误信息
        return {
            'code': fund_code,
            'name': fund_name or f'基金{fund_code}',
            'error': str(e)
        }


def display_single_result(result: dict, rank: int = None):
    """
    显示单只基金的分析结果（实时显示）
    
    Args:
        result: 单只基金的分析结果字典
        rank: 排名（可选）
    """
    if 'error' in result:
        print(f'FAIL {result["code"]}: {result["error"]}')
        return
    
    dev = result.get('deviation', 0)
    
    # 根据偏离率确定信号强度
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
    
    # 格式化输出（精简版）
    if rank is not None:
        print(f'{rank:>2}. {result["code"]}  {result["name"][:10]:<10} '
              f'{result["current_price"]:>8.4f}  {result["today_change"]:>+6.2f}%  '
              f'{result["deviation"]:>+7.2f}%  {signal}')
    else:
        print(f'    {result["code"]}  {result["name"][:10]:<10} '
              f'{result["current_price"]:>8.4f}  {result["today_change"]:>+6.2f}%  '
              f'{result["deviation"]:>+7.2f}%  {signal}')


def display_analysis(results: list):
    """
    在终端显示分析结果表格
    
    按偏离率从高到低排序，显示强度排名、基金信息和各项指标，
    并根据偏离率给出信号判断。
    
    Args:
        results: 分析结果列表（由analyze_fund返回的字典组成）
    """
    # 过滤掉有错误的结果，只保留有效数据
    valid_results = [r for r in results if 'current_price' in r]
    # 按偏离率降序排序（偏离率越高表示越强）
    valid_results.sort(key=lambda x: x.get('deviation', 0), reverse=True)
    
    # 打印表头
    header = '=' * 115
    print(header)
    print('场外基金趋势大模型 - WMA版本（5日高低价）')
    print('   日期: ' + datetime.now().strftime('%Y年%m月%d日'))
    print(header)
    
    # 打印列标题
    print('{:<4} {:<12} {:<10} {:>10} {:>8} {:>9} {:>10} {:>10} {:>10} {:>8} {:<6} {:>6}'.format(
        '强度', '基金代码', '基金名称', '现价', '今日涨跌', '5日涨跌', '20日涨跌', 
        '5日最高', '5日最低', '趋势线', '偏离率', '信号', '多头'))
    print('-' * 115)
    
    # 打印每一行数据
    for i, r in enumerate(valid_results, 1):
        dev = r.get('deviation', 0)
        
        # 根据偏离率确定信号强度
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
        
        # 格式化输出
        print('{:<4} {:<12} {:<10} {:>10.4f} {:>+7.2f}% {:>+7.2f}% {:>+8.2f}% {:>10.4f} {:>10.4f} {:>10.4f} {:>+7.2f}% {:<6} {:>6}'.format(
            i, r['code'], r['name'][:10], r['current_price'], r['today_change'], 
            r['change_5d'], r['change_20d'], r['high_5d'], r['low_5d'],
            r['trend_line'], dev, signal, r.get('ma_bullish', '否')))
    
    # 打印公式说明
    print(header)
    print('【指标说明】')
    print('  5日高低价: 过去5个交易日的最高/最低净值')
    print(f'  趋势线   : 均价的{period}日线性加权移动平均(WMA)')
    print(f'  WMA权重  : 第1天={period}, 第2天={period-1}, ..., 第{period}天=1')
    print(f'  偏离率   : (现价-趋势线)/趋势线 × 100%')
    print('  强度排序 : 按偏离率数值，数值越大=短期走势越强')
    print('  多头排列 : ma10>ma20>ma30>ma60，满足为"是"，否则为"否"')
    print(header)


def export_to_excel(results: list, output_path: str = r'g:\场外\基金趋势分析.xlsx'):
    """
    将分析结果导出到Excel文件
    
    Args:
        results: 分析结果列表
        output_path: Excel文件保存路径
    """
    # 过滤掉有错误的结果，只保留有效数据
    valid_results = [r for r in results if 'current_price' in r]
    # 按偏离率降序排序（偏离率越高表示越强）
    valid_results.sort(key=lambda x: x.get('deviation', 0), reverse=True)
    
    # 准备数据
    data = []
    for i, r in enumerate(valid_results, 1):
        # 根据偏离率确定信号强度
        dev = r.get('deviation', 0)
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
        
        data.append({
            '强度': i,
            '基金代码': r['code'],
            '基金名称': r['name'],
            '现价': round(r['current_price'], 4),
            '今日涨跌': f"{r['today_change']:+.2f}%",
            '5日涨跌': f"{r['change_5d']:+.2f}%",
            '20日涨跌': f"{r['change_20d']:+.2f}%",
            '5日最高': round(r['high_5d'], 4),
            '5日最低': round(r['low_5d'], 4),
            '趋势线': round(r['trend_line'], 4),
            '偏离率': f"{r['deviation']:+.2f}%",
            '信号': signal,
            '多头排列': r.get('ma_bullish', '否')
        })
    
    # 创建DataFrame并导出Excel
    df = pd.DataFrame(data)
    
    # 设置列顺序
    df = df[['强度', '基金代码', '基金名称', '现价', '今日涨跌', '5日涨跌', '20日涨跌',
             '5日最高', '5日最低', '趋势线', '偏离率', '信号', '多头排列']]
    
    # 导出Excel
    df.to_excel(output_path, index=False, engine='openpyxl')
    print(f'\nExcel表格已保存至: {output_path}')


def get_deviation_color(dev):
    """
    根据偏离率值获取对应的颜色（用于图表背景色阶）
    
    颜色映射规则（红色代表强，绿色代表弱）：
    - >5%   : 深红色 (#CD5C5C) - 极强
    - 2~5%  : 浅红色 (#FF9999) - 强势
    - 0~2%  : 淡红色 (#FFCCCC) - 偏强
    - -2~0% : 淡绿色 (#CCFFCC) - 偏弱
    - <-2%  : 深绿色 (#006400) - 超卖
    
    Args:
        dev: 偏离率值（百分比）
    
    Returns:
        str: 颜色的十六进制代码
    """
    if dev > 5:
        return '#CD5C5C'  # 深红 - 极强
    elif dev > 2:
        return '#FF9999'  # 浅红 - 强势
    elif dev > 0:
        return '#FFCCCC'  # 很淡的红 - 偏强
    elif dev > -2:
        return '#CCFFCC'  # 很淡的绿 - 偏弱
    else:
        return '#006400'  # 深绿 - 超卖


def plot_fund_trend(result: dict, save_path=None):
    """
    绘制基金趋势分析图表
    
    图表结构（上下两部分）：
    1. 上半部分（主图）：净值走势 + WMA趋势线 + 5日高低价 + 布林带 + 色阶背景
    2. 下半部分：偏离率柱状图
    
    Args:
        result: analyze_fund返回的结果字典
        save_path: 图片保存路径（可选）
    
    Returns:
        None（图表会自动保存或显示）
    """
    # 检查数据是否完整
    if 'df' not in result:
        print("无数据可绘制")
        return
    
    # 准备数据
    df = result['df'].copy()
    df['date'] = pd.to_datetime(df['date'])  # 转换日期格式
    
    # ========== 创建图表布局 ==========
    fig = plt.figure(figsize=(14, 10))  # 设置画布大小
    gs = fig.add_gridspec(2, 1, height_ratios=[4, 2.5])  # 上下两部分，比例4:2.5
    fig.suptitle(f'{result["name"]} ({result["code"]}) 趋势分析 - WMA', 
                 fontsize=16, fontweight='bold')  # 主标题
    
    # ========== 上半部分：主图（净值走势） ==========
    ax1 = fig.add_subplot(gs[0])  # 创建第一个子图
    
    # 1. 绘制偏离率强度色阶背景
    colors = [get_deviation_color(d) for d in df['deviation']]
    dates = mdates.date2num(df['date'])  # 将日期转换为matplotlib数值
    width = np.diff(dates, append=dates[-1] + (dates[-1] - dates[-2]))  # 计算每个条带宽度
    
    # 计算y轴范围（包含所有指标）
    all_data = pd.concat([df['nav'], df['high_5d'], df['low_5d'], df['trend_line'], 
                          df['bb_upper'], df['bb_lower']], axis=1)
    y_min = all_data.min().min()
    y_max = all_data.max().max()
    y_pad = (y_max - y_min) * 0.1  # 预留10%边距
    y_low, y_high = y_min - y_pad, y_max + y_pad
    
    # 绘制色阶背景条
    for i in range(len(dates)):
        ax1.axvspan(dates[i] - width[i]/2, dates[i] + width[i]/2,
                    ymin=0, ymax=1, color=colors[i], alpha=0.3)
    
    # 2. 绘制各项指标线（按zorder顺序，数值越大越在上方）
    ax1.plot(df['date'], df['nav'], label='净值', color='black', linewidth=2.5, zorder=10)
    ax1.plot(df['date'], df['trend_line'], label='趋势线(WMA)', color='blue', linewidth=2, zorder=5)
    ax1.plot(df['date'], df['high_5d'], label='5日最高', color='green', linestyle='--', alpha=0.8, zorder=3)
    ax1.plot(df['date'], df['low_5d'], label='5日最低', color='red', linestyle='--', alpha=0.8, zorder=3)
    ax1.fill_between(df['date'], df['low_5d'], df['high_5d'], color='gray', alpha=0.15, zorder=2)
    
    # 3. 绘制布林带
    ax1.plot(df['date'], df['bb_upper'], label='布林带上轨', color='orange', linewidth=1.5, zorder=4)
    ax1.plot(df['date'], df['bb_mid'], label='布林带中轨', color='orange', linewidth=1, linestyle='--', zorder=4)
    ax1.plot(df['date'], df['bb_lower'], label='布林带下轨', color='orange', linewidth=1.5, zorder=4)
    ax1.fill_between(df['date'], df['bb_lower'], df['bb_upper'], color='orange', alpha=0.1, zorder=2)
    
    # 设置主图属性
    ax1.set_ylim(y_low, y_high)  # 设置y轴范围
    ax1.set_ylabel('净值', fontsize=12)
    ax1.set_title('净值、趋势线、5日高低价与布林带 (WMA)', fontsize=12)
    ax1.grid(True, alpha=0.3, zorder=1)  # 添加网格
    ax1.xaxis_date()  # 确保x轴按日期格式显示
    
    # 4. 创建图例（整合色阶和线条）
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#CD5C5C', label='极强 (>5%)'),
        Patch(facecolor='#FF9999', label='强势 (2%~5%)'),
        Patch(facecolor='#FFCCCC', label='偏强 (0%~2%)'),
        Patch(facecolor='#CCFFCC', label='偏弱 (-2%~0%)'),
        Patch(facecolor='#006400', label='超卖 (<-2%)'),
        Line2D([0], [0], color='black', linewidth=2.5, label='净值'),
        Line2D([0], [0], color='blue', linewidth=2, label='趋势线(WMA)'),
        Line2D([0], [0], color='green', linestyle='--', label='5日最高'),
        Line2D([0], [0], color='red', linestyle='--', label='5日最低'),
        Line2D([0], [0], color='orange', linewidth=1.5, label='布林带上轨'),
        Line2D([0], [0], color='orange', linewidth=1, linestyle='--', label='布林带中轨'),
        Line2D([0], [0], color='orange', linewidth=1.5, label='布林带下轨'),
    ]
    ax1.legend(handles=legend_elements, loc='upper left', fontsize=8, ncol=2)
    
    # ========== 下半部分：偏离率柱状图 ==========
    ax2 = fig.add_subplot(gs[1], sharex=ax1)  # 创建第二个子图，共享x轴
    
    # 根据偏离率正负设置颜色（正数红色，负数绿色）
    bar_colors = ['red' if x >= 0 else 'green' for x in df['deviation']]
    ax2.bar(df['date'], df['deviation'], color=bar_colors, alpha=0.6, width=1)
    
    # 添加参考线
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=1)      # 零轴
    ax2.axhline(y=5, color='red', linestyle='--', alpha=0.5, label='强势线(+5%)')
    ax2.axhline(y=2, color='orange', linestyle='--', alpha=0.5, label='弱势线(+2%)')
    
    # 设置偏离率图属性
    ax2.set_ylabel('偏离率 (%)', fontsize=12)
    ax2.legend(loc='upper left', fontsize=10)
    ax2.set_title('偏离率 (WMA)', fontsize=12)
    ax2.grid(True, alpha=0.3)
    
    # 设置x轴格式（按月显示）
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)  # 旋转日期标签便于阅读
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图片（如果指定了路径）
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"图表已保存至: {save_path}")
    
    plt.close(fig)  # 关闭图形，释放资源


# 导入基金代码获取函数
import pywencai


def get_fund_codes(question=None):
    """查询基金 - 获取完整数据
    
    Args:
        question: 问财查询语句，如果为None则从环境变量WENCAI_QUERY读取
    """
    # 优先级：函数参数 > 环境变量 > 默认值
    if question is None:
        question = os.environ.get('WENCAI_QUERY', '近一年涨幅前1000名，C类基金')
    
    try:
        funds = pywencai.get(
            question=question,
            query_type="fund",
            per_page=100,
            loop=True
        )

        # 提取基金编号
        fund_codes = []
        for code in funds['基金代码']:
            # 提取前6位数字
            if '.' in code:
                code_num = code.split('.')[0]
            else:
                code_num = code
            # 确保是6位数字
            code_num = code_num.zfill(6)[:6]
            fund_codes.append(code_num)

        print(f"\n获取到 {len(fund_codes)} 只基金")
        return fund_codes

    except Exception as e:
        print(f"\n发生错误: {str(e)}")
        print("请检查网络连接或API限制")
        return []


if __name__ == "__main__":
    """
    主程序入口
    
    执行流程（实时处理）：
    1. 获取基金列表
    2. 创建图片保存目录
    3. 循环获取每只基金数据 → 立即计算指标 → 立即显示结果 → 立即保存图表
    4. 全部完成后显示汇总表格
    5. 导出Excel
    """
    # ==================== 配置参数 ====================
    # 基金列表（从pywencai获取）
    funds = get_fund_codes()
    
    period = 20  # WMA计算周期
    
    # 创建图片保存目录（格式：基金趋势图_YYYYMMDD）
    today_str = datetime.now().strftime('%Y%m%d')
    image_dir = os.path.join(script_dir, f'基金趋势图_{today_str}')
    os.makedirs(image_dir, exist_ok=True)
    print(f"\n图片将保存到目录: {image_dir}")
    
    # ==================== 实时获取和计算 ====================
    print('\n正在获取基金数据并计算指标...\n')
    print(f'{"排名":>2}  {"基金代码":<8}  {"基金名称":<10}  {"现价":>8}  {"今日涨跌":>7}  {"偏离率":>7}  {"信号"}')
    print('-' * 75)
    
    results = []
    for idx, code in enumerate(funds, 1):
        try:
            # 获取数据并立即计算指标
            result = analyze_fund(code)
            results.append(result)
            
            # 立即显示结果
            if 'error' not in result:
                display_single_result(result, idx)
                
                # 立即保存图表到指定目录
                try:
                    # 清理文件名中的特殊字符
                    clean_name = result['name']
                    for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\t', '\n']:
                        clean_name = clean_name.replace(char, '_')
                    # 文件名格式：偏离率_基金名称_基金代码.png
                    deviation_str = f'{result["deviation"]:+.2f}'.replace('.', '')
                    # save_path = f'{image_dir}\\/{deviation_str}_{clean_name}_{result["code"]}.png'
                    save_path = f'{image_dir}\\/{clean_name}_{result["code"]}.png'
                    plot_fund_trend(result, save_path)
                except Exception as e:
                    print(f"    绘图失败: {str(e)}")
            else:
                print(f'{idx:>2}. FAIL {code}: {result["error"]}')
                
        except Exception as e:
            print(f'{idx:>2}. FAIL {code}: {str(e)}')
    
    # ==================== 显示汇总表格 ====================
    if results:
        print('\n')
        display_analysis(results)
        
        # 导出Excel
        excel_path = os.path.join(script_dir, '基金趋势分析.xlsx')
        export_to_excel(results, excel_path)
    
    print('\n分析完成!')
