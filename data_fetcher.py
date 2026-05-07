# -*- coding: utf-8 -*-
"""
数据获取模块 v4.1
全市场覆盖：搜索走本地 all_stocks.json（6971条数据）
不再依赖东方财富在线API搜索，更稳定
K线数据仍通过akshare/腾讯API在线获取
"""

try:
    import akshare as ak
except ImportError:
    ak = None
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import streamlit as st
import json
import os
from pathlib import Path
import signal

# 超时设置
TIMEOUT = 10
MAX_RETRIES = 2
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
DATA_STALE_DAYS = 3  # 数据超过3天自动更新

# ==================== 从本地JSON加载全量数据 ====================
def load_all_items():
    """从本地JSON文件加载全量股票/ETF/指数数据"""
    json_file = os.path.join(os.path.dirname(__file__), 'all_stocks.json')
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"警告: {json_file} 不存在，请运行 download_all_stocks.py 下载数据")
        return {}
    except Exception as e:
        print(f"加载JSON失败: {e}")
        return {}

# 加载全量数据
ALL_ITEMS = load_all_items()

# 为兼容旧代码保留这些（用于 get_stock_name 等函数）
BUILTIN_STOCKS = {k: v['name'] for k, v in ALL_ITEMS.items() if v['type'] == '股票'}
BUILTIN_ETFS = {k: v['name'] for k, v in ALL_ITEMS.items() if v['type'] == 'ETF'}
BUILTIN_INDICES = {k: v['name'] for k, v in ALL_ITEMS.items() if v['type'] == '指数'}


def search_all(keyword, limit=10):
    """
    本地搜索：直接从 all_stocks.json 搜索
    支持中文名称模糊搜索、代码精确搜索
    1个字就开始出候选
    """
    if not keyword or len(keyword.strip()) == 0:
        return []
    
    keyword = keyword.strip().upper()
    results = []
    
    # 先精确匹配代码
    for code, info in ALL_ITEMS.items():
        if code.upper() == keyword:
            results.append({
                "code": code,
                "name": info['name'],
                "type": info['type']
            })
            if len(results) >= limit:
                return results
    
    # 再模糊匹配名称
    for code, info in ALL_ITEMS.items():
        if len(results) >= limit:
            break
        if code.upper() == keyword:  # 已匹配过
            continue
        name = info['name'].upper()
        # 名称包含关键词 或 关键词开头
        if keyword in name or name.startswith(keyword) or keyword in code.upper():
            results.append({
                "code": code,
                "name": info['name'],
                "type": info['type']
            })
    
    return results


# ==================== K线数据获取（保留在线功能） ====================

class DataFetchError(Exception):
    """数据获取异常"""
    pass

class DataNotFoundError(DataFetchError):
    """数据不存在"""
    pass

class DataSuspendedError(DataFetchError):
    """数据停牌"""
    pass


def _read_local_parquet(symbol, start_date, end_date):
    """读取本地parquet缓存"""
    cache_file = os.path.join(DATA_DIR, f"{symbol}.parquet")
    if os.path.exists(cache_file):
        try:
            df = pd.read_parquet(cache_file)
            df['date'] = pd.to_datetime(df['date'])
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
            return df
        except:
            pass
    return None


def _save_to_parquet(df, symbol):
    """保存到本地parquet缓存"""
    os.makedirs(DATA_DIR, exist_ok=True)
    cache_file = os.path.join(DATA_DIR, f"{symbol}.parquet")
    try:
        df.to_parquet(cache_file, index=False)
    except:
        pass


def _check_data_freshness(df):
    """检查数据新鲜度"""
    if df is None or len(df) == 0:
        return True
    latest = pd.to_datetime(df['date']).max()
    return (datetime.now() - latest).days > DATA_STALE_DAYS


def _fetch_from_tencent(symbol, start_date, end_date, stock_type="stock"):
    """从腾讯财经API获取数据"""
    import requests
    
    # 判断代码前缀
    if symbol.startswith("000") or symbol.startswith("001"):
        prefix = "sh" if symbol.startswith("000") else "sz"
    elif symbol.startswith("002") or symbol.startswith("003"):
        prefix = "sz"
    elif symbol.startswith("300"):
        prefix = "sz"
    elif symbol.startswith("688"):
        prefix = "sh"
    elif symbol.startswith("8") or symbol.startswith("4"):
        prefix = "bj"
    else:
        prefix = "sh"
    
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param={prefix}{symbol},day,{start_date},{end_date},320,qfq"
    
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        text = resp.text
        # 解析JSONP
        json_str = text[text.index('=') + 1:]
        data = json.loads(json_str)
        
        day_data = data['data'][f"{prefix}{symbol}"]['qfqday']
        
        df = pd.DataFrame(day_data, columns=['date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'unused'])
        df = df[['date', 'open', 'close', 'high', 'low', 'volume']]
        df['date'] = pd.to_datetime(df['date'])
        for col in ['open', 'close', 'high', 'low', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()
        df = df.sort_values('date').reset_index(drop=True)
        
        if len(df) == 0:
            raise DataFetchError(f"{symbol} 数据为空", "empty_data")
        
        return df
        
    except Exception as e:
        raise DataFetchError(str(e), "tencent_error")


def _fetch_stock_from_akshare(symbol, start_date, end_date, adjust="qfq"):
    """从akshare获取股票数据"""
    if ak is None:
        raise DataFetchError("akshare未安装", "no_akshare")
    
    try:
        adj_map = {"qfq": "qfq", "hfq": "hfq", "none": ""}
        adj = adj_map.get(adjust, "qfq")
        
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                               start_date=start_date.replace('-', ''),
                               end_date=end_date.replace('-', ''),
                               adjust=adj)
        
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
        err_msg = str(e).lower()
        if '不存在' in err_msg or '错误' in err_msg:
            raise DataNotFoundError(symbol)
        if '停牌' in err_msg:
            raise DataSuspendedError(symbol)
        raise DataFetchError(str(e), "akshare_error")


def _fetch_etf_from_akshare(symbol, start_date, end_date, adjust="qfq"):
    """从akshare获取ETF数据"""
    if ak is None:
        raise DataFetchError("akshare未安装", "no_akshare")
    
    try:
        adj_map = {"qfq": "qfq", "hfq": "hfq", "none": ""}
        adj = adj_map.get(adjust, "qfq")
        
        # 尝试fund_etf_hist_em
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily",
                                 start_date=start_date.replace('-', ''),
                                 end_date=end_date.replace('-', ''),
                                 adjust=adj)
        
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount', '涨跌幅': 'pct_change', '涨跌额': 'change'
        })
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        return df
    except Exception as e:
        raise DataFetchError(str(e), "akshare_error")


def _fetch_index_from_akshare(symbol, start_date, end_date):
    """从akshare获取指数数据"""
    if ak is None:
        raise DataFetchError("akshare未安装", "no_akshare")
    
    try:
        df = ak.index_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start_date, end_date=end_date
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
        err_msg = str(e).lower()
        if '不存在' in err_msg:
            raise DataNotFoundError(symbol)
        raise DataFetchError(str(e), "akshare_error")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(symbol, start_date, end_date, adjust="qfq"):
    """获取股票历史数据：优先本地缓存，其次腾讯API，最后akshare"""
    symbol = symbol.zfill(6)
    
    # 1. 读本地缓存
    df = _read_local_parquet(symbol, start_date, end_date)
    if df is not None and len(df) > 0 and not _check_data_freshness(df):
        return df
    
    # 2. 腾讯财经API（最可靠）
    try:
        new_df = _fetch_from_tencent(symbol, start_date, end_date, "stock")
        if new_df is not None and len(new_df) > 0:
            _save_to_parquet(new_df, symbol)
            return new_df
    except DataFetchError:
        pass
    
    # 3. akshare fallback
    if ak is not None:
        try:
            new_df = _fetch_stock_from_akshare(symbol, start_date, end_date, adjust)
            if new_df is not None and len(new_df) > 0:
                _save_to_parquet(new_df, symbol)
                return new_df
        except DataFetchError:
            pass
    
    # 4. 返回旧缓存（即使过期）
    if df is not None and len(df) > 0:
        return df
    
    raise DataFetchError(f"无法获取股票 {symbol} 的数据", "all_sources_failed")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_etf_data(symbol, start_date, end_date, adjust="qfq"):
    """获取ETF历史数据：优先本地缓存，其次腾讯API，最后akshare"""
    symbol = symbol.zfill(6)
    
    # 1. 读本地缓存
    df = _read_local_parquet(symbol, start_date, end_date)
    if df is not None and len(df) > 0 and not _check_data_freshness(df):
        return df
    
    # 2. 腾讯财经API
    try:
        new_df = _fetch_from_tencent(symbol, start_date, end_date, "ETF")
        if new_df is not None and len(new_df) > 0:
            _save_to_parquet(new_df, symbol)
            return new_df
    except DataFetchError:
        pass
    
    # 3. akshare fallback
    if ak is not None:
        try:
            new_df = _fetch_etf_from_akshare(symbol, start_date, end_date, adjust)
            if new_df is not None and len(new_df) > 0:
                _save_to_parquet(new_df, symbol)
                return new_df
        except DataFetchError:
            pass
    
    # 4. 返回旧缓存
    if df is not None and len(df) > 0:
        return df
    
    raise DataFetchError(f"无法获取ETF {symbol} 的数据", "all_sources_failed")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_index_data(symbol, start_date, end_date):
    """获取指数历史数据：优先本地缓存，其次腾讯API，最后akshare"""
    symbol = symbol.zfill(6)
    
    # 1. 读本地缓存
    df = _read_local_parquet(symbol, start_date, end_date)
    if df is not None and len(df) > 0 and not _check_data_freshness(df):
        return df
    
    # 2. 腾讯财经API
    try:
        new_df = _fetch_from_tencent(symbol, start_date, end_date, "指数")
        if new_df is not None and len(new_df) > 0:
            _save_to_parquet(new_df, symbol)
            return new_df
    except DataFetchError:
        pass
    
    # 3. akshare fallback
    if ak is not None:
        try:
            new_df = _fetch_index_from_akshare(symbol, start_date, end_date)
            if new_df is not None and len(new_df) > 0:
                _save_to_parquet(new_df, symbol)
                return new_df
        except DataFetchError:
            pass
    
    # 4. 返回旧缓存
    if df is not None and len(df) > 0:
        return df
    
    raise DataFetchError(f"无法获取指数 {symbol} 的数据", "all_sources_failed")


def fetch_data(symbol, start_date, end_date, stock_type="stock", adjust="qfq"):
    """统一的数据获取接口"""
    symbol = symbol.zfill(6)
    if stock_type == "ETF":
        return fetch_etf_data(symbol, start_date, end_date, adjust)
    elif stock_type == "指数":
        return fetch_index_data(symbol, start_date, end_date)
    else:
        return fetch_stock_data(symbol, start_date, end_date, adjust)


# ==================== 兼容旧接口 ====================

def get_stock_name(symbol, stock_type="stock"):
    """获取股票名称"""
    symbol = symbol.zfill(6)
    return BUILTIN_STOCKS.get(symbol, BUILTIN_ETFS.get(symbol, BUILTIN_INDICES.get(symbol, symbol)))


@st.cache_data(ttl=86400, show_spinner=False)
def get_hot_stocks():
    """获取热门股票推荐"""
    # 从全量数据中选择热门股票
    hot_codes = [
        "000001", "000002", "600000", "600036", "600519", "600887",
        "000858", "601318", "000333", "002594", "300750", "688981",
        "515000", "513500", "510300", "159915",
    ]
    return [(code, ALL_ITEMS.get(code, {}).get('name', code)) for code in hot_codes if code in ALL_ITEMS]


def search_stocks(keyword, stock_type="stock", limit=10):
    """搜索股票（旧接口兼容）"""
    results = search_all(keyword, limit)
    if stock_type == "ETF":
        return [(r['code'], r['name']) for r in results if r['type'] == "ETF"]
    elif stock_type == "指数":
        return [(r['code'], r['name']) for r in results if r['type'] == "指数"]
    else:
        return [(r['code'], r['name']) for r in results]
