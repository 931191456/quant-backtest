# -*- coding: utf-8 -*-
"""
策略引擎模块 v2.1
支持多策略组合计算，新增SKDJ指标和参数可自定义
"""

import pandas as pd
import numpy as np


# ==================== 基础技术指标计算 ====================

def calculate_ma(df, periods=[5, 10, 20, 60]):
    """计算简单移动平均线"""
    for period in periods:
        df[f'ma{period}'] = df['close'].rolling(window=period).mean()
    return df


def calculate_ema(df, periods=[12, 26]):
    """计算指数移动平均线"""
    for period in periods:
        df[f'ema{period}'] = df['close'].ewm(span=period, adjust=False).mean()
    return df


def calculate_macd(df, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = df['ema_fast'] - df['ema_slow']
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    df.drop(['ema_fast', 'ema_slow'], axis=1, inplace=True)
    return df


def calculate_rsi(df, period=14):
    """计算RSI指标"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df


def calculate_bollinger_bands(df, period=20, std_dev=2):
    """计算布林带"""
    df['bb_middle'] = df['close'].rolling(window=period).mean()
    df['bb_std'] = df['close'].rolling(window=period).std()
    df['bb_upper'] = df['bb_middle'] + std_dev * df['bb_std']
    df['bb_lower'] = df['bb_middle'] - std_dev * df['bb_std']
    df.drop('bb_std', axis=1, inplace=True)
    return df


def calculate_kdj(df, n=9, m1=3, m2=3):
    """计算KDJ指标"""
    low_n = df['low'].rolling(window=n, min_periods=1).min()
    high_n = df['high'].rolling(window=n, min_periods=1).max()
    rsv = (df['close'] - low_n) / (high_n - low_n) * 100
    rsv = rsv.fillna(50)
    df['kdj_k'] = rsv.ewm(com=m1-1, adjust=False).mean()
    df['kdj_d'] = df['kdj_k'].ewm(com=m2-1, adjust=False).mean()
    df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
    return df


def calculate_skdj(df, n=9, m=3):
    """
    计算SKDJ（慢速随机指标）
    
    Parameters:
    -----------
    df : DataFrame - K线数据
    n : int - RSV周期（默认9）
    m : int - 平滑周期（默认3），K和D都用此周期平滑
    
    SKDJ计算公式：
    - RSV = (Close - Low_N) / (High_N - Low_N) * 100
    - K = SMA(RSV, M) - M周期平滑
    - D = SMA(K, M) - M周期平滑
    """
    # 计算N日内最低价和最高价
    low_n = df['low'].rolling(window=n, min_periods=1).min()
    high_n = df['high'].rolling(window=n, min_periods=1).max()
    
    # 计算RSV
    rsv = (df['close'] - low_n) / (high_n - low_n) * 100
    rsv = rsv.fillna(50)
    
    # K值：RSV的M周期简单移动平均
    df['skdj_k'] = rsv.rolling(window=m, min_periods=1).mean()
    
    # D值：K的M周期简单移动平均
    df['skdj_d'] = df['skdj_k'].rolling(window=m, min_periods=1).mean()
    
    return df


def calculate_volume_ma(df, periods=[5, 10, 20]):
    """计算成交量移动平均线"""
    for period in periods:
        df[f'vol_ma{period}'] = df['volume'].rolling(window=period).mean()
    return df


# ==================== 单一策略信号生成 ====================

def ma_cross_signal(df, short_period=5, long_period=20):
    """双均线交叉策略"""
    if f'ma{short_period}' not in df.columns or f'ma{long_period}' not in df.columns:
        df = calculate_ma(df, [short_period, long_period])
    
    ma_short = df[f'ma{short_period}']
    ma_long = df[f'ma{long_period}']
    
    # 金叉（买入）：短期均线上穿长期均线
    buy = (ma_short > ma_long) & (ma_short.shift(1) <= ma_long.shift(1))
    # 死叉（卖出）：短期均线下穿长期均线
    sell = (ma_short < ma_long) & (ma_short.shift(1) >= ma_long.shift(1))
    
    return buy, sell


def macd_cross_signal(df, fast=12, slow=26, signal=9):
    """MACD金叉死叉策略"""
    if 'macd' not in df.columns:
        df = calculate_macd(df, fast, slow, signal)
    
    macd = df['macd']
    macd_signal = df['macd_signal']
    
    buy = (macd > macd_signal) & (macd.shift(1) <= macd_signal.shift(1))
    sell = (macd < macd_signal) & (macd.shift(1) >= macd_signal.shift(1))
    
    return buy, sell


def rsi_signal(df, period=14, oversold=30, overbought=70):
    """RSI超买超卖策略"""
    if 'rsi' not in df.columns:
        df = calculate_rsi(df, period)
    
    rsi = df['rsi']
    
    buy = rsi < oversold
    sell = rsi > overbought
    
    return buy, sell


def kdj_cross_signal(df, n=9, m1=3, m2=3):
    """KDJ金叉死叉策略"""
    if 'kdj_k' not in df.columns:
        df = calculate_kdj(df, n, m1, m2)
    
    k = df['kdj_k']
    d = df['kdj_d']
    
    buy = (k > d) & (k.shift(1) <= d.shift(1))
    sell = (k < d) & (k.shift(1) >= d.shift(1))
    
    return buy, sell


def skdj_cross_signal(df, n=9, m=3):
    """
    SKDJ金叉死叉策略
    
    金叉：K上穿D → 买入信号
    死叉：K下穿D → 卖出信号
    """
    if 'skdj_k' not in df.columns:
        df = calculate_skdj(df, n, m)
    
    k = df['skdj_k']
    d = df['skdj_d']
    
    # 金叉：K从下往上穿过D
    buy = (k > d) & (k.shift(1) <= d.shift(1))
    # 死叉：K从上往下穿过D
    sell = (k < d) & (k.shift(1) >= d.shift(1))
    
    return buy, sell


def volume_breakout_signal(df, period=20, multiplier=1.5):
    """成交量突破策略"""
    if f'vol_ma{period}' not in df.columns:
        df = calculate_volume_ma(df, [period])
    
    volume = df['volume']
    vol_ma = df[f'vol_ma{period}']
    
    buy = volume > vol_ma * multiplier
    sell = False  # 成交量突破不产生卖出信号
    
    return buy, sell


def bollinger_breakout_signal(df, period=20, std_dev=2):
    """布林带突破策略"""
    if 'bb_upper' not in df.columns:
        df = calculate_bollinger_bands(df, period, std_dev)
    
    close = df['close']
    bb_upper = df['bb_upper']
    bb_lower = df['bb_lower']
    
    buy = close < bb_lower  # 价格跌破下轨买入
    sell = close > bb_upper  # 价格突破上轨卖出
    
    return buy, sell


def ma_arrangement_signal(df, short_period=5, long_period=60):
    """均线多头/空头排列策略"""
    if f'ma{short_period}' not in df.columns or f'ma{long_period}' not in df.columns:
        df = calculate_ma(df, [short_period, 20, long_period])
    
    ma_short = df[f'ma{short_period}']
    ma_mid = df['ma20']
    ma_long = df[f'ma{long_period}']
    
    # 多头排列：短>中>长
    buy = (ma_short > ma_mid) & (ma_mid > ma_long)
    # 空头排列：短<中<长
    sell = (ma_short < ma_mid) & (ma_mid < ma_long)
    
    return buy, sell


# ==================== 策略注册表 ====================

STRATEGIES = {
    "MACD金叉/死叉": {
        "func": macd_cross_signal,
        "params": {
            "fast": {"label": "快线周期", "default": 12, "min": 5, "max": 30},
            "slow": {"label": "慢线周期", "default": 26, "min": 10, "max": 60},
            "signal": {"label": "信号线周期", "default": 9, "min": 5, "max": 20}
        },
        "description": "MACD金叉买入，死叉卖出"
    },
    "RSI超买超卖": {
        "func": rsi_signal,
        "params": {
            "period": {"label": "RSI周期", "default": 14, "min": 5, "max": 30},
            "oversold": {"label": "超卖阈值", "default": 30, "min": 10, "max": 40},
            "overbought": {"label": "超买阈值", "default": 70, "min": 60, "max": 90}
        },
        "description": "RSI低于超卖线买入，高于超买线卖出"
    },
    "KDJ金叉/死叉": {
        "func": kdj_cross_signal,
        "params": {
            "n": {"label": "RSV周期", "default": 9, "min": 5, "max": 20},
            "m1": {"label": "K值平滑", "default": 3, "min": 1, "max": 10},
            "m2": {"label": "D值平滑", "default": 3, "min": 1, "max": 10}
        },
        "description": "KDJ金叉买入，死叉卖出"
    },
    "SKDJ金叉/死叉": {
        "func": skdj_cross_signal,
        "params": {
            "n": {"label": "RSV周期(N)", "default": 9, "min": 5, "max": 30},
            "m": {"label": "平滑周期(M)", "default": 3, "min": 2, "max": 15}
        },
        "description": "慢速KDJ金叉买入，死叉卖出。参数N为RSV计算周期，M为K/D平滑周期"
    },
    "成交量突破": {
        "func": volume_breakout_signal,
        "params": {
            "period": {"label": "均量周期", "default": 20, "min": 5, "max": 60},
            "multiplier": {"label": "突破倍数", "default": 1.5, "min": 1.0, "max": 3.0}
        },
        "description": "成交量突破均量的指定倍数时买入"
    },
    "布林带突破": {
        "func": bollinger_breakout_signal,
        "params": {
            "period": {"label": "周期", "default": 20, "min": 10, "max": 60},
            "std_dev": {"label": "标准差倍数", "default": 2, "min": 1, "max": 3}
        },
        "description": "价格跌破布林下轨买入，突破上轨卖出"
    },
    "均线多头排列": {
        "func": ma_arrangement_signal,
        "params": {
            "short_period": {"label": "短期均线", "default": 5, "min": 3, "max": 20},
            "long_period": {"label": "长期均线", "default": 60, "min": 30, "max": 120}
        },
        "description": "均线多头排列买入，空头排列卖出"
    },
    "双均线交叉": {
        "func": ma_cross_signal,
        "params": {
            "short_period": {"label": "短期均线", "default": 5, "min": 2, "max": 20},
            "long_period": {"label": "长期均线", "default": 20, "min": 10, "max": 120}
        },
        "description": "短期均线上穿长期均线买入，下穿卖出"
    }
}


def apply_single_strategy(df, strategy_name, **params):
    """
    应用单一策略，返回买卖信号
    """
    if strategy_name not in STRATEGIES:
        raise ValueError(f"未知策略: {strategy_name}")
    
    strategy = STRATEGIES[strategy_name]
    func = strategy["func"]
    
    # 计算所有必要的指标
    df = calculate_all_indicators(df)
    
    # 调用策略函数
    buy_signal, sell_signal = func(df, **params)
    
    # 标记信号
    df['buy_signal'] = buy_signal
    df['sell_signal'] = sell_signal
    
    return df


def apply_multi_strategy(df, selected_strategies, params_dict, buy_mode="any", sell_mode="any"):
    """
    应用多策略组合，支持买入和卖出条件独立控制
    
    Parameters:
    -----------
    df : pd.DataFrame
        K线数据
    selected_strategies : list
        选中的策略名称列表
    params_dict : dict
        各策略的参数字典 {"策略名": {"param1": value1, ...}}
    buy_mode : str
        买入模式
        "all": 所有策略都满足才买入（保守）
        "any": 任一策略满足就买入（激进）
    sell_mode : str
        卖出模式
        "all": 所有策略都满足才卖出（保守）
        "any": 任一策略满足就卖出（激进，更及时止损）
    
    Returns:
    --------
    pd.DataFrame : 带买卖信号的DataFrame
    """
    if not selected_strategies:
        df['buy_signal'] = False
        df['sell_signal'] = False
        return df
    
    # 计算所有指标
    df = calculate_all_indicators(df)
    
    # 收集各策略的信号
    strategy_buy_signals = []
    strategy_sell_signals = []
    
    for strategy_name in selected_strategies:
        if strategy_name not in STRATEGIES:
            continue
        
        params = params_dict.get(strategy_name, {})
        func = STRATEGIES[strategy_name]["func"]
        buy, sell = func(df, **params)
        strategy_buy_signals.append(buy)
        strategy_sell_signals.append(sell)
    
    if not strategy_buy_signals:
        df['buy_signal'] = False
        df['sell_signal'] = False
        return df
    
    # 组合信号 - 买入条件
    if buy_mode == "all":
        # 所有策略都满足才买入（AND逻辑）
        combined_buy = strategy_buy_signals[0]
        for i in range(1, len(strategy_buy_signals)):
            combined_buy = combined_buy & strategy_buy_signals[i]
    else:
        # 任一策略满足就买入（OR逻辑）
        combined_buy = strategy_buy_signals[0]
        for i in range(1, len(strategy_buy_signals)):
            combined_buy = combined_buy | strategy_buy_signals[i]
    
    # 组合信号 - 卖出条件
    if sell_mode == "all":
        # 所有策略都满足才卖出（AND逻辑，更保守）
        combined_sell = strategy_sell_signals[0]
        for i in range(1, len(strategy_sell_signals)):
            combined_sell = combined_sell & strategy_sell_signals[i]
    else:
        # 任一策略满足就卖出（OR逻辑，更激进，及时止损）
        combined_sell = strategy_sell_signals[0]
        for i in range(1, len(strategy_sell_signals)):
            combined_sell = combined_sell | strategy_sell_signals[i]
    
    df['buy_signal'] = combined_buy
    df['sell_signal'] = combined_sell
    
    return df


def calculate_all_indicators(df):
    """计算所有技术指标"""
    df = calculate_ma(df, [5, 10, 20, 60])
    df = calculate_macd(df)
    df = calculate_rsi(df)
    df = calculate_kdj(df)
    df = calculate_skdj(df)
    df = calculate_bollinger_bands(df)
    df = calculate_volume_ma(df, [5, 10, 20])
    return df


# 兼容旧接口
def apply_strategy(df, strategy_name, **params):
    """兼容旧接口"""
    return apply_single_strategy(df, strategy_name, **params)
