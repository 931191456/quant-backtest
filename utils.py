# -*- coding: utf-8 -*-
"""
工具函数模块
提供通用的辅助功能
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
        # ETF代码通常为6位数字
        if not re.match(r'^\d{6}$', code):
            return False, "ETF代码应为6位数字"
    else:
        # 个股代码通常为6位数字
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


def get_benchmark_name(benchmark):
    """获取基准名称"""
    names = {
        "000300": "沪深300",
        "000016": "上证50",
        "399006": "创业板指",
        "000001": "上证指数"
    }
    return names.get(benchmark, benchmark)


def parse_adjust_param(adjust):
    """解析复权参数"""
    adjust_map = {
        "前复权": "qfq",
        "后复权": "hfq",
        "不复权": None
    }
    return adjust_map.get(adjust, "qfq")
