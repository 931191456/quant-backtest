# -*- coding: utf-8 -*-
"""
工具函数模块 v2.1
新增行业ETF映射表
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re


def format_money(amount):
    """格式化金额为中文格式"""
    if abs(amount) >= 100000000:
        return f"{amount/100000000:.2f}亿"
    elif abs(amount) >= 10000:
        return f"{amount/10000:.2f}万"
    else:
        return f"{amount:.2f}元"


def format_percent(value, show_sign=True):
    """格式化百分比"""
    if show_sign and value > 0:
        return f"+{value:.2f}%"
    return f"{value:.2f}%"


def get_date_range(years=5):
    """获取日期范围，默认5年前至今"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years*365)
    return start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")


def validate_stock_code(code, stock_type):
    """验证股票代码格式"""
    code = code.strip()
    
    if stock_type == "ETF":
        if not re.match(r'^\d{6}$', code):
            return False, "ETF代码应为6位数字"
    else:
        if not re.match(r'^\d{6}$', code):
            return False, "股票代码应为6位数字"
    
    return True, ""


def calculate_win_rate(trades):
    """计算胜率"""
    if not trades:
        return 0.0
    
    winning_trades = sum(1 for t in trades if t.get('盈亏金额', 0) > 0)
    return winning_trades / len(trades) * 100 if trades else 0


def calculate_profit_loss_ratio(trades):
    """计算盈亏比"""
    if not trades:
        return 0.0
    
    profits = [t['盈亏金额'] for t in trades if t.get('盈亏金额', 0) > 0]
    losses = [abs(t['盈亏金额']) for t in trades if t.get('盈亏金额', 0) < 0]
    
    avg_profit = np.mean(profits) if profits else 0
    avg_loss = np.mean(losses) if losses else 0
    
    if avg_loss == 0:
        return float('inf') if avg_profit > 0 else 0
    
    return avg_profit / avg_loss


def calculate_max_drawdown(equity_curve):
    """计算最大回撤"""
    if len(equity_curve) == 0:
        return 0.0, 0, 0
    
    peak = equity_curve[0]
    max_drawdown = 0
    peak_idx = 0
    trough_idx = 0
    
    for i, value in enumerate(equity_curve):
        if value > peak:
            peak = value
            peak_idx = i
        
        drawdown = (peak - value) / peak if peak > 0 else 0
        
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            trough_idx = i
    
    return max_drawdown * 100, peak_idx, trough_idx


# 常用指数代码映射
INDEX_MAP = {
    "沪深300": "000300",
    "上证50": "000016",
    "创业板指": "399006",
    "中证500": "000905",
    "上证指数": "000001",
    "深证成指": "399001"
}


# 行业ETF映射表
# 根据股票名称关键词匹配行业ETF
INDUSTRY_ETF_MAP = {
    # 银行
    "银行": {"code": "512800", "name": "银行ETF"},
    "招商银行": {"code": "512800", "name": "银行ETF"},
    "工商银行": {"code": "512800", "name": "银行ETF"},
    "建设银行": {"code": "512800", "name": "银行ETF"},
    "农业银行": {"code": "512800", "name": "银行ETF"},
    "中国银行": {"code": "512800", "name": "银行ETF"},
    
    # 白酒/酒
    "酒": {"code": "512690", "name": "酒ETF"},
    "茅台": {"code": "512690", "name": "酒ETF"},
    "五粮液": {"code": "512690", "name": "酒ETF"},
    "泸州老窖": {"code": "512690", "name": "酒ETF"},
    "汾酒": {"code": "512690", "name": "酒ETF"},
    "洋河": {"code": "512690", "name": "酒ETF"},
    
    # 医药
    "医药": {"code": "512010", "name": "医药ETF"},
    "药明": {"code": "512010", "name": "医药ETF"},
    "恒瑞": {"code": "512010", "name": "医药ETF"},
    "迈瑞": {"code": "512010", "name": "医药ETF"},
    "片仔癀": {"code": "512010", "name": "医药ETF"},
    "云南白药": {"code": "512010", "name": "医药ETF"},
    
    # 新能源
    "新能源": {"code": "516160", "name": "新能源ETF"},
    "宁德": {"code": "516160", "name": "新能源ETF"},
    "比亚迪": {"code": "516160", "name": "新能源ETF"},
    "隆基": {"code": "516160", "name": "新能源ETF"},
    "通威": {"code": "516160", "name": "新能源ETF"},
    
    # 半导体
    "半导体": {"code": "512480", "name": "半导体ETF"},
    "芯片": {"code": "512480", "name": "半导体ETF"},
    "集成电路": {"code": "512480", "name": "半导体ETF"},
    "中芯": {"code": "512480", "name": "半导体ETF"},
    "韦尔": {"code": "512480", "name": "半导体ETF"},
    
    # 军工
    "军工": {"code": "512660", "name": "军工ETF"},
    "航发": {"code": "512660", "name": "军工ETF"},
    "中航": {"code": "512660", "name": "军工ETF"},
    "航天": {"code": "512660", "name": "军工ETF"},
    
    # 消费
    "消费": {"code": "159928", "name": "消费ETF"},
    "美的": {"code": "159928", "name": "消费ETF"},
    "格力": {"code": "159928", "name": "消费ETF"},
    "海尔": {"code": "159928", "name": "消费ETF"},
    
    # 科技
    "科技": {"code": "515000", "name": "科技ETF"},
    "腾讯": {"code": "515000", "name": "科技ETF"},
    "阿里": {"code": "515000", "name": "科技ETF"},
    "百度": {"code": "515000", "name": "科技ETF"},
    "京东": {"code": "515000", "name": "科技ETF"},
    "网易": {"code": "515000", "name": "科技ETF"},
    
    # 房地产
    "房地产": {"code": "512200", "name": "房地产ETF"},
    "万科": {"code": "512200", "name": "房地产ETF"},
    "保利": {"code": "512200", "name": "房地产ETF"},
    "金地": {"code": "512200", "name": "房地产ETF"},
    "招蛇": {"code": "512200", "name": "房地产ETF"},
    
    # 券商
    "券商": {"code": "512000", "name": "券商ETF"},
    "证券": {"code": "512000", "name": "券商ETF"},
    "中信证券": {"code": "512000", "name": "券商ETF"},
    "华泰": {"code": "512000", "name": "券商ETF"},
    "国泰": {"code": "512000", "name": "券商ETF"},
    "海通": {"code": "512000", "name": "券商ETF"},
    
    # 汽车
    "汽车": {"code": "516110", "name": "汽车ETF"},
    "长城": {"code": "516110", "name": "汽车ETF"},
    "长安": {"code": "516110", "name": "汽车ETF"},
    "上汽": {"code": "516110", "name": "汽车ETF"},
    
    # 钢铁
    "钢铁": {"code": "515210", "name": "钢铁ETF"},
    "宝钢": {"code": "515210", "name": "钢铁ETF"},
    
    # 煤炭
    "煤炭": {"code": "515220", "name": "煤炭ETF"},
    "中国神华": {"code": "515220", "name": "煤炭ETF"},
    "陕西煤业": {"code": "515220", "name": "煤炭ETF"},
    
    # 有色
    "有色": {"code": "512400", "name": "有色ETF"},
    "紫金矿业": {"code": "512400", "name": "有色ETF"},
    "洛阳钼业": {"code": "512400", "name": "有色ETF"},
    
    # 电力
    "电力": {"code": "159611", "name": "电力ETF"},
    "长江电力": {"code": "159611", "name": "电力ETF"},
    "华能水电": {"code": "159611", "name": "电力ETF"},
    
    # 食品饮料
    "食品": {"code": "512690", "name": "酒ETF(食品饮料)"},
    "饮料": {"code": "512690", "name": "酒ETF(食品饮料)"},
    "伊利": {"code": "512690", "name": "酒ETF(食品饮料)"},
    "蒙牛": {"code": "512690", "name": "酒ETF(食品饮料)"},
    
    # 农业
    "农业": {"code": "159825", "name": "农业ETF"},
    "牧原": {"code": "159825", "name": "农业ETF"},
    "温氏": {"code": "159825", "name": "农业ETF"},
    
    # 家电
    "家电": {"code": "159996", "name": "家电ETF"},
    
    # 传媒
    "传媒": {"code": "159805", "name": "传媒ETF"},
    "分众": {"code": "159805", "name": "传媒ETF"},
    
    # 通信
    "通信": {"code": "515880", "name": "通信ETF"},
    "中兴": {"code": "515880", "name": "通信ETF"},
    "中国联通": {"code": "515880", "name": "通信ETF"},
    
    # 计算机
    "计算机": {"code": "512720", "name": "计算机ETF"},
    "软件": {"code": "512720", "name": "计算机ETF"},
    
    # 港股
    "港股": {"code": "159920", "name": "恒生ETF"},
    "腾讯控股": {"code": "159920", "name": "恒生ETF"},
}


def get_index_code(name_or_code):
    """获取指数代码"""
    if name_or_code in INDEX_MAP:
        return INDEX_MAP[name_or_code]
    return name_or_code


def match_industry_etf(stock_name):
    """
    根据股票名称匹配行业ETF
    
    Parameters:
    -----------
    stock_name : str
        股票名称
        
    Returns:
    --------
    dict or None : {"code": "xxx", "name": "xxx"} 或 None
    """
    if not stock_name:
        return None
    
    stock_name_upper = stock_name.upper()
    
    # 遍历映射表，匹配关键词
    for keyword, etf_info in INDUSTRY_ETF_MAP.items():
        if keyword in stock_name_upper or keyword in stock_name:
            return etf_info
    
    return None


def get_benchmark_options_with_industry(stock_name, stock_code):
    """
    获取基准选项列表，自动添加行业ETF
    
    Parameters:
    -----------
    stock_name : str
        股票名称
    stock_code : str
        股票代码
        
    Returns:
    --------
    list : 基准选项列表，每项为 {"label": "显示名称", "value": "代码或None"}
    """
    options = [
        {"label": "无基准", "value": None},
        {"label": "沪深300", "value": "000300"},
        {"label": "上证50", "value": "000016"},
        {"label": "创业板指", "value": "399006"},
        {"label": "中证500", "value": "000905"},
    ]
    
    # 尝试匹配行业ETF
    industry_etf = match_industry_etf(stock_name)
    if industry_etf:
        # 在合适位置插入行业ETF（在无基准之后）
        options.insert(1, {
            "label": f"行业: {industry_etf['name']}",
            "value": industry_etf['code']
        })
    
    return options
