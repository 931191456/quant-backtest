# -*- coding: utf-8 -*-
"""
策略引擎模块
实现各种技术指标和交易策略
"""

import pandas as pd
import numpy as np


# ==================== 基础技术指标计算 ====================

def calculate_ma(df, periods=[5, 10, 20, 60]):
    """
    计算简单移动平均线
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含收盘价的数据
    periods : list
        周期列表
    
    Returns:
    --------
    pd.DataFrame
        添加了MA列的数据
    """
    for period in periods:
        df[f'ma{period}'] = df['close'].rolling(window=period).mean()
    return df


def calculate_ema(df, periods=[12, 26]):
    """
    计算指数移动平均线
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含收盘价的数据
    periods : list
        周期列表
    
    Returns:
    --------
    pd.DataFrame
        添加了EMA列的数据
    """
    for period in periods:
        df[f'ema{period}'] = df['close'].ewm(span=period, adjust=False).mean()
    return df


def calculate_macd(df, fast=12, slow=26, signal=9):
    """
    计算MACD指标
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含收盘价的数据
    fast : int
        快线周期
    slow : int
        慢线周期
    signal : int
        信号线周期
    
    Returns:
    --------
    pd.DataFrame
        添加了macd、macd_signal、macd_hist列的数据
    """
    df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = df['ema_fast'] - df['ema_slow']
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # 删除中间列
    df.drop(['ema_fast', 'ema_slow'], axis=1, inplace=True)
    return df


def calculate_rsi(df, period=14):
    """
    计算RSI指标
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含收盘价的数据
    period : int
        RSI周期
    
    Returns:
    --------
    pd.DataFrame
        添加了rsi列的数据
    """
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df


def calculate_bollinger_bands(df, period=20, std_dev=2):
    """
    计算布林带
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含收盘价的数据
    period : int
        周期
    std_dev : float
        标准差倍数
    
    Returns:
    --------
    pd.DataFrame
        添加了bb_upper、bb_middle、bb_lower列的数据
    """
    df['bb_middle'] = df['close'].rolling(window=period).mean()
    df['bb_std'] = df['close'].rolling(window=period).std()
    df['bb_upper'] = df['bb_middle'] + std_dev * df['bb_std']
    df['bb_lower'] = df['bb_middle'] - std_dev * df['bb_std']
    df.drop('bb_std', axis=1, inplace=True)
    return df


def calculate_kdj(df, n=9, m1=3, m2=3):
    """
    计算KDJ指标
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含高、低、收盘价的数据
    n : int
        RSV周期
    m1 : int
        K值平滑周期
    m2 : int
        D值平滑周期
    
    Returns:
    --------
    pd.DataFrame
        添加了kdj_k、kdj_d、kdj_j列的数据
    """
    low_n = df['low'].rolling(window=n, min_periods=1).min()
    high_n = df['high'].rolling(window=n, min_periods=1).max()
    
    rsv = (df['close'] - low_n) / (high_n - low_n) * 100
    rsv = rsv.fillna(50)
    
    df['kdj_k'] = rsv.ewm(com=m1-1, adjust=False).mean()
    df['kdj_d'] = df['kdj_k'].ewm(com=m2-1, adjust=False).mean()
    df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
    return df


def calculate_volume_ma(df, periods=[5, 10, 20]):
    """
    计算成交量移动平均线
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含成交量数据
    periods : list
        周期列表
    
    Returns:
    --------
    pd.DataFrame
        添加了vol_ma列的数据
    """
    for period in periods:
        df[f'vol_ma{period}'] = df['volume'].rolling(window=period).mean()
    return df


# ==================== 策略信号生成 ====================

def ma_cross_signal(df, short_period=5, long_period=20):
    """
    均线交叉策略
    金叉买入，死叉卖出
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含收盘价的数据
    short_period : int
        短期均线周期
    long_period : int
        长期均线周期
    
    Returns:
    --------
    pd.DataFrame
        添加了signal列(1买入, -1卖出, 0观望)
    """
    df = calculate_ma(df.copy(), periods=[short_period, long_period])
    df['signal'] = 0
    
    short_ma = f'ma{short_period}'
    long_ma = f'ma{long_period}'
    
    # 金叉：短期均线上穿长期均线
    golden_cross = (df[short_ma] > df[long_ma]) & (df[short_ma].shift(1) <= df[long_ma].shift(1))
    # 死叉：短期均线下穿长期均线
    dead_cross = (df[short_ma] < df[long_ma]) & (df[short_ma].shift(1) >= df[long_ma].shift(1))
    
    df.loc[golden_cross, 'signal'] = 1  # 买入信号
    df.loc[dead_cross, 'signal'] = -1   # 卖出信号
    
    return df


def macd_signal_strategy(df, fast=12, slow=26, signal=9):
    """
    MACD策略
    MACD金叉买入，死叉卖出
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含收盘价的数据
    fast : int
        快线周期
    slow : int
        慢线周期
    signal : int
        信号线周期
    
    Returns:
    --------
    pd.DataFrame
        添加了signal列
    """
    df = calculate_macd(df.copy(), fast, slow, signal)
    df['signal'] = 0
    
    # 金叉：MACD上穿信号线
    golden_cross = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
    # 死叉：MACD下穿信号线
    dead_cross = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))
    
    df.loc[golden_cross, 'signal'] = 1  # 买入信号
    df.loc[dead_cross, 'signal'] = -1   # 卖出信号
    
    return df


def rsi_signal_strategy(df, period=14, oversold=30, overbought=70):
    """
    RSI超买超卖策略
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含收盘价的数据
    period : int
        RSI周期
    oversold : float
        超卖阈值
    overbought : float
        超买阈值
    
    Returns:
    --------
    pd.DataFrame
        添加了signal列
    """
    df = calculate_rsi(df.copy(), period)
    df['signal'] = 0
    
    # RSI从超卖区回升买入
    buy_condition = (df['rsi'] < oversold) & (df['rsi'].shift(1) >= oversold)
    # RSI从超买区回落卖出
    sell_condition = (df['rsi'] > overbought) & (df['rsi'].shift(1) <= overbought)
    
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    return df


def bollinger_signal_strategy(df, period=20, std_dev=2):
    """
    布林带策略
    价格触及下轨买入，触及上轨卖出
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含收盘价的数据
    period : int
        周期
    std_dev : float
        标准差倍数
    
    Returns:
    --------
    pd.DataFrame
        添加了signal列
    """
    df = calculate_bollinger_bands(df.copy(), period, std_dev)
    df['signal'] = 0
    
    # 价格触及下轨买入
    buy_condition = (df['close'] <= df['bb_lower']) & (df['close'].shift(1) > df['bb_lower'].shift(1))
    # 价格触及上轨卖出
    sell_condition = (df['close'] >= df['bb_upper']) & (df['close'].shift(1) < df['bb_upper'].shift(1))
    
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    return df


def kdj_signal_strategy(df, n=9, m1=3, m2=3):
    """
    KDJ策略
    K值从下往上穿越D值买入，反之卖出
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含高、低、收盘价的数据
    n : int
        RSV周期
    m1 : int
        K值平滑周期
    m2 : int
        D值平滑周期
    
    Returns:
    --------
    pd.DataFrame
        添加了signal列
    """
    df = calculate_kdj(df.copy(), n, m1, m2)
    df['signal'] = 0
    
    # 金叉
    golden_cross = (df['kdj_k'] > df['kdj_d']) & (df['kdj_k'].shift(1) <= df['kdj_d'].shift(1))
    # 死叉
    dead_cross = (df['kdj_k'] < df['kdj_d']) & (df['kdj_k'].shift(1) >= df['kdj_d'].shift(1))
    
    df.loc[golden_cross, 'signal'] = 1
    df.loc[dead_cross, 'signal'] = -1
    
    return df


def volume_reversal_signal(df, period=20, threshold=0.5):
    """
    缩量反转策略
    在放量下跌后缩量反弹时买入
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含成交量数据
    period : int
        观察周期
    threshold : float
        缩量比例阈值
    
    Returns:
    --------
    pd.DataFrame
        添加了signal列
    """
    df = calculate_volume_ma(df.copy())
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    df['signal'] = 0
    
    # 放量下跌（跌幅大于2%且成交量大于均量1.5倍）
    volume_surge = (df['pct_change'] < -2) & (df['vol_ratio'] > 1.5)
    
    # 缩量反弹（缩量至均量以下且价格上涨）
    volume_shrink = (df['vol_ratio'] < threshold) & (df['pct_change'] > 0)
    
    # 连续出现放量下跌后的缩量反弹
    df['volume_surge_flag'] = volume_surge.astype(int)
    df['surge_count'] = df['volume_surge_flag'].rolling(window=3, min_periods=1).sum()
    
    buy_condition = volume_shrink & (df['surge_count'] >= 1)
    
    # 价格跌破5日均线卖出
    df = calculate_ma(df, periods=[5])
    sell_condition = (df['close'] < df['ma5']) & (df['close'].shift(1) >= df['ma5'].shift(1))
    
    df.loc[buy_condition, 'signal'] = 1
    df.loc[sell_condition, 'signal'] = -1
    
    df.drop(['vol_ratio', 'volume_surge_flag', 'surge_count'], axis=1, inplace=True)
    
    return df


def panic_buy_signal(df, drop_threshold=-5, volume_threshold=2):
    """
    恐慌抄底策略
    在大幅下跌且放量时买入
    
    Parameters:
    -----------
    df : pd.DataFrame
        包含成交量数据
    drop_threshold : float
        跌幅阈值（负数）
    volume_threshold : float
        放量倍数
    
    Returns:
    --------
    pd.DataFrame
        添加了signal列
    """
    df = calculate_volume_ma(df.copy())
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    df['signal'] = 0
    
    # 恐慌条件：大幅下跌且放量
    panic_condition = (df['pct_change'] < drop_threshold) & (df['vol_ratio'] > volume_threshold)
    
    # 买入信号
    df.loc[panic_condition, 'signal'] = 1
    
    # 止盈止损出场：5日后或盈利/亏损达到阈值
    # 这里简化为持有5天后自动卖出
    df.drop(['vol_ratio'], axis=1, inplace=True)
    
    return df


# ==================== 策略选择映射 ====================

STRATEGY_FUNCTIONS = {
    "均线交叉策略": {
        "function": ma_cross_signal,
        "params": {
            "short_period": {"type": "int", "default": 5, "min": 2, "max": 60, "label": "短期均线天数"},
            "long_period": {"type": "int", "default": 20, "min": 5, "max": 250, "label": "长期均线天数"}
        }
    },
    "MACD策略": {
        "function": macd_signal_strategy,
        "params": {
            "fast": {"type": "int", "default": 12, "min": 5, "max": 30, "label": "快线周期"},
            "slow": {"type": "int", "default": 26, "min": 10, "max": 60, "label": "慢线周期"},
            "signal": {"type": "int", "default": 9, "min": 5, "max": 20, "label": "信号线周期"}
        }
    },
    "RSI策略": {
        "function": rsi_signal_strategy,
        "params": {
            "period": {"type": "int", "default": 14, "min": 5, "max": 30, "label": "RSI周期"},
            "oversold": {"type": "float", "default": 30, "min": 10, "max": 40, "label": "超卖线"},
            "overbought": {"type": "float", "default": 70, "min": 60, "max": 90, "label": "超买线"}
        }
    },
    "布林带策略": {
        "function": bollinger_signal_strategy,
        "params": {
            "period": {"type": "int", "default": 20, "min": 10, "max": 60, "label": "周期"},
            "std_dev": {"type": "float", "default": 2, "min": 1, "max": 4, "label": "标准差倍数"}
        }
    },
    "KDJ策略": {
        "function": kdj_signal_strategy,
        "params": {
            "n": {"type": "int", "default": 9, "min": 5, "max": 30, "label": "K周期"}
        }
    },
    "缩量反转策略": {
        "function": volume_reversal_signal,
        "params": {
            "period": {"type": "int", "default": 20, "min": 10, "max": 60, "label": "观察周期"},
            "threshold": {"type": "float", "default": 0.5, "min": 0.2, "max": 1, "label": "缩量比例"}
        }
    },
    "恐慌抄底策略": {
        "function": panic_buy_signal,
        "params": {
            "drop_threshold": {"type": "float", "default": -5, "min": -15, "max": -2, "label": "跌幅阈值(%)"},
            "volume_threshold": {"type": "float", "default": 2, "min": 1.5, "max": 5, "label": "放量倍数"}
        }
    }
}


def apply_strategy(df, strategy_name, **params):
    """
    应用策略生成信号
    
    Parameters:
    -----------
    df : pd.DataFrame
        原始数据
    strategy_name : str
        策略名称
    **params : dict
        策略参数
    
    Returns:
    --------
    pd.DataFrame
        添加了signal列的数据
    """
    if strategy_name not in STRATEGY_FUNCTIONS:
        raise ValueError(f"未知策略: {strategy_name}")
    
    strategy = STRATEGY_FUNCTIONS[strategy_name]
    func = strategy["function"]
    
    # 构建参数字典
    strategy_params = {}
    for key, value in params.items():
        if key in strategy["params"]:
            strategy_params[key] = value
    
    return func(df, **strategy_params)


def get_strategy_params(strategy_name):
    """
    获取策略参数定义
    
    Parameters:
    -----------
    strategy_name : str
        策略名称
    
    Returns:
    --------
    dict
        参数定义字典
    """
    if strategy_name in STRATEGY_FUNCTIONS:
        return STRATEGY_FUNCTIONS[strategy_name]["params"]
    return {}
