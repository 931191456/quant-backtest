# -*- coding: utf-8 -*-
"""
数据获取模块 v2.0
支持缓存、超时、异步加载的akshare数据获取
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import streamlit as st
from functools import lru_cache
import warnings
warnings.filterwarnings('ignore')

# 超时设置（秒）
TIMEOUT = 15


def _fetch_with_timeout(func, *args, **kwargs):
    """带超时的数据获取"""
    import signal
    
    class TimeoutError(Exception):
        pass
    
    def timeout_handler(signum, frame):
        raise TimeoutError("数据获取超时")
    
    # 设置超时
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TIMEOUT)
    
    try:
        result = func(*args, **kwargs)
        return result
    except TimeoutError:
        raise Exception(f"数据获取超时（{TIMEOUT}秒），请稍后重试或选择其他标的")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_etf_data(symbol, start_date, end_date, adjust="qfq"):
    """
    获取ETF历史数据（带缓存）
    """
    try:
        df = ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )
        
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_change',
            '涨跌额': 'change', '换手率': 'turnover'
        })
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        return df
        
    except Exception as e:
        raise Exception(f"获取ETF数据失败: {str(e)}")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(symbol, start_date, end_date, adjust="qfq"):
    """
    获取个股历史数据（带缓存）
    """
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )
        
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_change',
            '涨跌额': 'change', '换手率': 'turnover'
        })
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        return df
        
    except Exception as e:
        raise Exception(f"获取股票数据失败: {str(e)}")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_index_data(symbol, start_date, end_date):
    """
    获取指数历史数据（带缓存）
    """
    try:
        df = ak.index_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date
        )
        
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_change',
            '涨跌额': 'change', '换手率': 'turnover'
        })
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        return df
        
    except Exception as e:
        raise Exception(f"获取指数数据失败: {str(e)}")


# 股票名称缓存（预加载）
_stock_name_cache = {}
_etf_name_cache = {}


@st.cache_data(ttl=86400, show_spinner=False)
def get_stock_name_cached(symbol, stock_type="stock"):
    """获取股票名称（带缓存）"""
    try:
        if stock_type == "ETF":
            if symbol in _etf_name_cache:
                return _etf_name_cache[symbol]
            df = ak.fund_etf_spot_em()
            name_row = df[df['代码'] == symbol]
            if not name_row.empty:
                name = name_row.iloc[0]['名称']
                _etf_name_cache[symbol] = name
                return name
        else:
            if symbol in _stock_name_cache:
                return _stock_name_cache[symbol]
            df = ak.stock_info_a_code_name()
            name_row = df[df['code'] == symbol]
            if not name_row.empty:
                name = name_row.iloc[0]['name']
                _stock_name_cache[symbol] = name
                return name
        return symbol
    except:
        return symbol


def get_stock_name(symbol, stock_type="stock"):
    """获取股票名称（兼容旧接口）"""
    return get_stock_name_cached(symbol, stock_type)


# 股票搜索缓存
@st.cache_data(ttl=3600, show_spinner=False)
def get_stock_list_cached():
    """获取股票列表（带缓存）"""
    try:
        df = ak.stock_info_a_code_name()
        return df[['code', 'name']].values.tolist()
    except:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def get_etf_list_cached():
    """获取ETF列表（带缓存）"""
    try:
        df = ak.fund_etf_spot_em()
        return df[['代码', '名称']].values.tolist()
    except:
        return []


def search_stocks(keyword, stock_type="stock", limit=10):
    """搜索股票"""
    if not keyword:
        return []
    
    keyword = keyword.upper()
    
    if stock_type == "ETF":
        stock_list = get_etf_list_cached()
        results = []
        for code, name in stock_list:
            if keyword in str(code) or keyword in name.upper():
                results.append((code, name))
                if len(results) >= limit:
                    break
        return results
    else:
        stock_list = get_stock_list_cached()
        results = []
        for code, name in stock_list:
            if keyword in str(code) or keyword.upper() in name.upper():
                results.append((code, name))
                if len(results) >= limit:
                    break
        return results


def fetch_data(symbol, start_date, end_date, stock_type="stock", adjust="qfq"):
    """统一的数据获取接口"""
    if stock_type == "ETF":
        return fetch_etf_data(symbol, start_date, end_date, adjust)
    else:
        return fetch_stock_data(symbol, start_date, end_date, adjust)


# 预加载热门股票
@st.cache_data(ttl=86400, show_spinner=False)
def get_hot_stocks():
    """获取热门股票列表"""
    hot_stocks = [
        ("000001", "平安银行"),
        ("000002", "万科A"),
        ("600000", "浦发银行"),
        ("600519", "贵州茅台"),
        ("600036", "招商银行"),
        ("000858", "五粮液"),
        ("601318", "中国平安"),
        ("000333", "美的集团"),
        ("002594", "比亚迪"),
        ("300750", "宁德时代"),
        ("688981", "中芯国际"),
        ("515000", "科技ETF"),
        ("513500", "标普500ETF"),
        ("510300", "沪深300ETF"),
        ("159915", "创业板ETF"),
    ]
    return hot_stocks
