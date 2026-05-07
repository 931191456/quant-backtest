# -*- coding: utf-8 -*-
"""
数据获取模块 v5.0
- 重构数据获取流程：本地parquet → akshare(3次重试) → 腾讯API(2次重试)
- 修复腾讯API代码前缀判断逻辑
- ETF支持51/15/16开头
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
import requests
from requests.exceptions import ConnectionError, Timeout, SSLError
from http.client import RemoteDisconnected

# 超时设置
TIMEOUT = 15
AKSHARE_RETRIES = 3
TENCENT_RETRIES = 2
AKSHARE_RETRY_DELAY = 2  # 秒
TENCENT_RETRY_DELAY = 1  # 秒
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

# 为兼容旧代码保留这些
BUILTIN_STOCKS = {k: v['name'] for k, v in ALL_ITEMS.items() if v['type'] == '股票'}
BUILTIN_ETFS = {k: v['name'] for k, v in ALL_ITEMS.items() if v['type'] == 'ETF'}
BUILTIN_INDICES = {k: v['name'] for k, v in ALL_ITEMS.items() if v['type'] == '指数'}


def search_all(keyword, limit=10):
    """
    本地搜索：直接从 all_stocks.json 搜索
    支持中文名称模糊搜索、代码精确搜索
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
        if code.upper() == keyword:
            continue
        name = info['name'].upper()
        if keyword in name or name.startswith(keyword) or keyword in code.upper():
            results.append({
                "code": code,
                "name": info['name'],
                "type": info['type']
            })
    
    return results


# ==================== K线数据获取 ====================

class DataFetchError(Exception):
    """数据获取异常"""
    def __init__(self, message, error_type="unknown"):
        super().__init__(message)
        self.message = message
        self.error_type = error_type

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
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
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
    """检查数据新鲜度，返回True表示需要更新"""
    if df is None or len(df) == 0:
        return True
    latest = pd.to_datetime(df['date']).max()
    return (datetime.now() - latest).days > DATA_STALE_DAYS


def _get_symbol_prefix(symbol, stock_type="stock"):
    """
    根据代码判断腾讯API需要的前缀
    正确的规则：
    - 6开头 → sh（上海主板、科创板）
    - 0开头、3开头 → sz（深圳主板、创业板）
    - 688开头 → sh（科创板）
    - 8开头、4开头 → bj（北交所）
    - ETF：51开头→sh，15开头→sz，16开头→sz
    """
    symbol = symbol.zfill(6)
    
    # ETF特殊处理
    if stock_type == "ETF":
        if symbol.startswith("51") or symbol.startswith("50"):
            return "sh"
        elif symbol.startswith("15") or symbol.startswith("16") or symbol.startswith("13"):
            return "sz"
        elif symbol.startswith("8") or symbol.startswith("4"):
            return "bj"
        else:
            return "sh"  # 默认
    
    # 股票判断
    if symbol.startswith("688"):
        return "sh"  # 科创板
    elif symbol.startswith("6"):
        return "sh"  # 上海主板
    elif symbol.startswith("000") or symbol.startswith("001"):
        return "sz"  # 深圳主板
    elif symbol.startswith("002") or symbol.startswith("003"):
        return "sz"  # 中小板
    elif symbol.startswith("300"):
        return "sz"  # 创业板
    elif symbol.startswith("8") or symbol.startswith("4"):
        return "bj"  # 北交所
    else:
        return "sh"  # 默认


def _fetch_from_tencent(symbol, start_date, end_date, stock_type="stock"):
    """从腾讯财经API获取数据"""
    symbol = symbol.zfill(6)
    prefix = _get_symbol_prefix(symbol, stock_type)
    
    # 转换日期格式
    start_str = str(start_date).replace('-', '')
    end_str = str(end_date).replace('-', '')
    
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param={prefix}{symbol},day,{start_str},{end_str},320,qfq"
    
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        text = resp.text
        
        if not text or '=' not in text:
            raise DataFetchError(f"{symbol} 腾讯API返回数据异常", "tencent_error")
        
        # 解析JSONP
        json_str = text[text.index('=') + 1:]
        data = json.loads(json_str)
        
        if f"{prefix}{symbol}" not in data.get('data', {}):
            raise DataFetchError(f"{symbol} 腾讯API未找到该股票", "tencent_not_found")
        
        day_data = data['data'][f"{prefix}{symbol}"]['qfqday']
        
        df = pd.DataFrame(day_data, columns=['date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'unused'])
        df = df[['date', 'open', 'close', 'high', 'low', 'volume']]
        df['date'] = pd.to_datetime(df['date'])
        for col in ['open', 'close', 'high', 'low', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()
        df = df.sort_values('date').reset_index(drop=True)
        
        if len(df) == 0:
            raise DataFetchError(f"{symbol} 腾讯API数据为空", "empty_data")
        
        return df
        
    except requests.exceptions.Timeout:
        raise DataFetchError(f"{symbol} 腾讯API超时", "tencent_timeout")
    except requests.exceptions.ConnectionError as e:
        raise DataFetchError(f"{symbol} 腾讯API连接失败", "tencent_connection")
    except (ConnectionError, RemoteDisconnected) as e:
        raise DataFetchError(f"{symbol} 腾讯API连接中断", "tencent_connection")
    except json.JSONDecodeError:
        raise DataFetchError(f"{symbol} 腾讯API返回JSON解析失败", "tencent_parse")
    except Exception as e:
        raise DataFetchError(f"{symbol} 腾讯API错误: {str(e)}", "tencent_error")


def _fetch_stock_from_akshare(symbol, start_date, end_date, adjust="qfq"):
    """从akshare获取股票数据"""
    if ak is None:
        raise DataFetchError("akshare未安装", "no_akshare")
    
    symbol = symbol.zfill(6)
    adj_map = {"qfq": "qfq", "hfq": "hfq", "none": ""}
    adj = adj_map.get(adjust, "qfq")
    
    try:
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
    
    symbol = symbol.zfill(6)
    adj_map = {"qfq": "qfq", "hfq": "hfq", "none": ""}
    adj = adj_map.get(adjust, "qfq")
    
    try:
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
        err_msg = str(e).lower()
        if '不存在' in err_msg or '错误' in err_msg:
            raise DataNotFoundError(symbol)
        raise DataFetchError(str(e), "akshare_error")


def _fetch_index_from_akshare(symbol, start_date, end_date):
    """从akshare获取指数数据"""
    if ak is None:
        raise DataFetchError("akshare未安装", "no_akshare")
    
    symbol = symbol.zfill(6)
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


def fetch_data(symbol, start_date, end_date, stock_type="stock", adjust="qfq"):
    """
    获取K线数据，多源自动切换（带重试机制）
    
    获取顺序：
    1. 本地parquet缓存（如果数据足够新）
    2. akshare（重试3次，每次间隔2秒）
    3. 腾讯API（重试2次，每次间隔1秒）
    4. 返回旧缓存（即使过期）
    5. 全失败才报错
    
    Parameters:
    -----------
    symbol : str - 股票代码
    start_date : str - 开始日期（YYYYMMDD或YYYY-MM-DD）
    end_date : str - 结束日期（YYYYMMDD或YYYY-MM-DD）
    stock_type : str - 类型（stock/ETF/指数）
    adjust : str - 复权类型（qfq/hfq/none）
    
    Returns:
    --------
    pd.DataFrame - K线数据
    """
    symbol = symbol.zfill(6)
    errors = []
    
    # 1. 先尝试本地缓存
    local_df = _read_local_parquet(symbol, start_date, end_date)
    if local_df is not None and len(local_df) > 0 and not _check_data_freshness(local_df):
        return local_df
    
    # 2. akshare获取（重试3次，每次间隔2秒）
    if ak is not None:
        for attempt in range(AKSHARE_RETRIES):
            try:
                if stock_type == "ETF":
                    df = _fetch_etf_from_akshare(symbol, start_date, end_date, adjust)
                elif stock_type == "指数":
                    df = _fetch_index_from_akshare(symbol, start_date, end_date)
                else:
                    df = _fetch_stock_from_akshare(symbol, start_date, end_date, adjust)
                
                if df is not None and len(df) > 0:
                    _save_to_parquet(df, symbol)
                    return df
            except (ConnectionError, RemoteDisconnected, Timeout, SSLError) as e:
                # 网络问题，可重试
                errors.append(f"akshare尝试{attempt+1}: {type(e).__name__}")
                if attempt < AKSHARE_RETRIES - 1:
                    time.sleep(AKSHARE_RETRY_DELAY)
            except DataNotFoundError:
                # 数据不存在，不重试
                raise
            except DataSuspendedError:
                # 停牌，不重试
                raise
            except DataFetchError as e:
                if "timeout" in e.error_type.lower() or "connection" in e.error_type.lower():
                    errors.append(f"akshare尝试{attempt+1}: {e.message}")
                    if attempt < AKSHARE_RETRIES - 1:
                        time.sleep(AKSHARE_RETRY_DELAY)
                else:
                    errors.append(f"akshare尝试{attempt+1}: {e.message}")
                    if attempt == AKSHARE_RETRIES - 1:
                        # 最后一次也失败才继续
                        pass
            except Exception as e:
                errors.append(f"akshare尝试{attempt+1}: {str(e)}")
                if attempt < AKSHARE_RETRIES - 1:
                    time.sleep(AKSHARE_RETRY_DELAY)
    
    # 3. 腾讯API获取（重试2次）
    for attempt in range(TENCENT_RETRIES):
        try:
            df = _fetch_from_tencent(symbol, start_date, end_date, stock_type)
            if df is not None and len(df) > 0:
                _save_to_parquet(df, symbol)
                return df
        except (ConnectionError, RemoteDisconnected, Timeout, SSLError) as e:
            errors.append(f"腾讯API尝试{attempt+1}: {type(e).__name__}")
            if attempt < TENCENT_RETRIES - 1:
                time.sleep(TENCENT_RETRY_DELAY)
        except DataFetchError as e:
            if "timeout" in e.error_type.lower() or "connection" in e.error_type.lower():
                errors.append(f"腾讯API尝试{attempt+1}: {e.message}")
                if attempt < TENCENT_RETRIES - 1:
                    time.sleep(TENCENT_RETRY_DELAY)
            else:
                errors.append(f"腾讯API尝试{attempt+1}: {e.message}")
        except Exception as e:
            errors.append(f"腾讯API尝试{attempt+1}: {str(e)}")
            if attempt < TENCENT_RETRIES - 1:
                time.sleep(TENCENT_RETRY_DELAY)
    
    # 4. 返回旧缓存（即使过期）
    if local_df is not None and len(local_df) > 0:
        return local_df
    
    # 5. 全失败
    raise DataFetchError(f"所有数据源均失败: {'; '.join(errors)}", "all_sources_failed")


# ==================== 兼容旧接口 ====================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(symbol, start_date, end_date, adjust="qfq"):
    """获取股票历史数据（兼容旧接口）"""
    return fetch_data(symbol, start_date, end_date, "stock", adjust)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_etf_data(symbol, start_date, end_date, adjust="qfq"):
    """获取ETF历史数据（兼容旧接口）"""
    return fetch_data(symbol, start_date, end_date, "ETF", adjust)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_index_data(symbol, start_date, end_date):
    """获取指数历史数据（兼容旧接口）"""
    return fetch_data(symbol, start_date, end_date, "指数")


def get_stock_name(symbol, stock_type="stock"):
    """获取股票名称"""
    symbol = symbol.zfill(6)
    return BUILTIN_STOCKS.get(symbol, BUILTIN_ETFS.get(symbol, BUILTIN_INDICES.get(symbol, symbol)))


@st.cache_data(ttl=86400, show_spinner=False)
def get_hot_stocks():
    """获取热门股票推荐"""
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
