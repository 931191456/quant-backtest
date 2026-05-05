# -*- coding: utf-8 -*-
"""
数据获取模块
使用akshare从东方财富获取A股数据
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time
import streamlit as st


def fetch_etf_data(symbol, start_date, end_date, adjust="qfq"):
    """
    获取ETF历史数据
    
    Parameters:
    -----------
    symbol : str
        ETF代码，如"515000"
    start_date : str
        开始日期，格式YYYYMMDD
    end_date : str
        结束日期，格式YYYYMMDD
    adjust : str
        复权类型：qfq(前复权)、hfq(后复权)
    
    Returns:
    --------
    pd.DataFrame
        包含日期、开盘、收盘、最高、最低价、成交量等
    """
    try:
        df = ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )
        
        # 重命名列为标准格式
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '振幅': 'amplitude',
            '涨跌幅': 'pct_change',
            '涨跌额': 'change',
            '换手率': 'turnover'
        })
        
        # 确保日期列是datetime类型
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        return df
        
    except Exception as e:
        raise Exception(f"获取ETF数据失败: {str(e)}")


def fetch_stock_data(symbol, start_date, end_date, adjust="qfq"):
    """
    获取个股历史数据
    
    Parameters:
    -----------
    symbol : str
        股票代码，如"000001"
    start_date : str
        开始日期，格式YYYYMMDD
    end_date : str
        结束日期，格式YYYYMMDD
    adjust : str
        复权类型：qfq(前复权)、hfq(后复权)
    
    Returns:
    --------
    pd.DataFrame
        包含日期、开盘、收盘、最高、最低价、成交量等
    """
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )
        
        # 重命名列为标准格式
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '振幅': 'amplitude',
            '涨跌幅': 'pct_change',
            '涨跌额': 'change',
            '换手率': 'turnover'
        })
        
        # 确保日期列是datetime类型
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        return df
        
    except Exception as e:
        raise Exception(f"获取股票数据失败: {str(e)}")


def fetch_index_data(symbol, start_date, end_date):
    """
    获取指数历史数据（用于基准对比）
    
    Parameters:
    -----------
    symbol : str
        指数代码，如"000300"(沪深300)
    start_date : str
        开始日期，格式YYYYMMDD
    end_date : str
        结束日期，格式YYYYMMDD
    
    Returns:
    --------
    pd.DataFrame
        包含日期、开盘、收盘、最高、最低价、成交量等
    """
    try:
        df = ak.index_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date
        )
        
        # 重命名列为标准格式
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '振幅': 'amplitude',
            '涨跌幅': 'pct_change',
            '涨跌额': 'change',
            '换手率': 'turnover'
        })
        
        # 确保日期列是datetime类型
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        return df
        
    except Exception as e:
        raise Exception(f"获取指数数据失败: {str(e)}")


def get_stock_name(symbol, stock_type="stock"):
    """
    获取股票或ETF名称
    
    Parameters:
    -----------
    symbol : str
        股票/ETF代码
    stock_type : str
        类型：stock(个股)、etf(ETF)
    
    Returns:
    --------
    str
        股票/ETF名称
    """
    try:
        if stock_type == "ETF":
            # 获取ETF信息
            df = ak.fund_etf_spot_em()
            name_row = df[df['代码'] == symbol]
            if not name_row.empty:
                return name_row.iloc[0]['名称']
        else:
            # 获取股票信息
            df = ak.stock_info_a_code_name()
            name_row = df[df['code'] == symbol]
            if not name_row.empty:
                return name_row.iloc[0]['name']
        
        return symbol
        
    except Exception:
        return symbol


def fetch_data(symbol, start_date, end_date, stock_type="stock", adjust="qfq"):
    """
    统一的数据获取接口
    
    Parameters:
    -----------
    symbol : str
        标的代码
    start_date : str
        开始日期，格式YYYYMMDD
    end_date : str
        结束日期，格式YYYYMMDD
    stock_type : str
        标的类型：stock(个股)、etf(ETF)、index(指数)
    adjust : str
        复权类型：qfq(前复权)、hfq(后复权)
    
    Returns:
    --------
    pd.DataFrame
        标准格式的历史数据
    """
    if stock_type == "ETF":
        return fetch_etf_data(symbol, start_date, end_date, adjust)
    elif stock_type == "index":
        return fetch_index_data(symbol, start_date, end_date)
    else:
        return fetch_stock_data(symbol, start_date, end_date, adjust)


def get_available_etf_list():
    """
    获取可用的ETF列表
    
    Returns:
    --------
    pd.DataFrame
        ETF代码和名称列表
    """
    try:
        df = ak.fund_etf_spot_em()
        return df[['代码', '名称']].rename(columns={'代码': 'code', '名称': 'name'})
    except Exception:
        return pd.DataFrame(columns=['code', 'name'])
