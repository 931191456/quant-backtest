# -*- coding: utf-8 -*-
"""
数据获取模块 v6.1
- 腾讯API分段拉取作为首选（5-7年数据，稳定可靠）
- 东方财富push2his作为备用（Streamlit Cloud可能被封）
- akshare作为备用（Python 3.14不可用）
- 本地parquet缓存加速
- 修复北交所secid格式
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
AKSHARE_RETRIES = 2
TENCENT_RETRIES = 2
AKSHARE_RETRY_DELAY = 2
TENCENT_RETRY_DELAY = 1
EM_RETRIES = 2
EM_RETRY_DELAY = 1
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
DATA_STALE_DAYS = 3

# 东方财富API设置
EM_API_BASE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

# 腾讯API设置
TENCENT_API_BASE = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

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
    """读取本地parquet缓存，同时检查缓存是否覆盖请求的日期范围"""
    cache_file = os.path.join(DATA_DIR, f"{symbol}.parquet")
    if os.path.exists(cache_file):
        try:
            df = pd.read_parquet(cache_file)
            df['date'] = pd.to_datetime(df['date'])
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            # 检查缓存是否覆盖了请求的日期范围
            cache_start = df['date'].min()
            cache_end = df['date'].max()
            
            # 如果缓存的起始日期晚于请求的起始日期，说明缓存不够长，需要重新获取
            if cache_start > start_dt + timedelta(days=5):
                return None
            
            df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
            return df
        except:
            pass
    return None


def _save_to_parquet(df, symbol):
    """保存到本地parquet缓存，合并已有缓存数据"""
    os.makedirs(DATA_DIR, exist_ok=True)
    cache_file = os.path.join(DATA_DIR, f"{symbol}.parquet")
    try:
        if os.path.exists(cache_file):
            # 合并新旧数据
            old_df = pd.read_parquet(cache_file)
            old_df['date'] = pd.to_datetime(old_df['date'])
            df['date'] = pd.to_datetime(df['date'])
            combined = pd.concat([old_df, df], ignore_index=True)
            combined = combined.drop_duplicates(subset=['date'], keep='last')
            combined = combined.sort_values('date').reset_index(drop=True)
            combined.to_parquet(cache_file, index=False)
        else:
            df.to_parquet(cache_file, index=False)
    except:
        pass


def _check_data_freshness(df):
    """检查数据新鲜度，返回True表示需要更新"""
    if df is None or len(df) == 0:
        return True
    latest = pd.to_datetime(df['date']).max()
    return (datetime.now() - latest).days > DATA_STALE_DAYS


def _split_date_range(start_date, end_date, max_per_segment=780):
    """
    将日期范围按约3年分段（780个交易日≈3年）
    每段最多780条数据，确保不超过腾讯API的800条限制
    """
    start_dt = datetime.strptime(str(start_date).replace('-', ''), '%Y%m%d')
    end_dt = datetime.strptime(str(end_date).replace('-', ''), '%Y%m%d')
    
    # 3年≈1095天，但按交易日约780条
    segment_days = 1095  # 约3年
    segments = []
    
    current = start_dt
    while current < end_dt:
        seg_end = current + timedelta(days=segment_days)
        # 确保不超过end_date
        if seg_end > end_dt:
            seg_end = end_dt
        
        segments.append((
            current.strftime('%Y-%m-%d'),
            seg_end.strftime('%Y-%m-%d')
        ))
        
        # 下一段从seg_end的下一天开始
        current = seg_end + timedelta(days=1)
    
    return segments


def _get_tencent_secid(symbol, stock_type="stock"):
    """
    生成腾讯API的secid格式
    腾讯API使用 sh/sz 前缀
    """
    code = symbol.zfill(6)
    
    # ETF特殊处理
    if stock_type == "ETF":
        # 上海ETF: 51开头, 50开头
        if code.startswith("51") or code.startswith("50"):
            return f"sh{code}"
        # 深圳ETF: 15/16/13开头
        elif code.startswith("15") or code.startswith("16") or code.startswith("13"):
            return f"sz{code}"
        else:
            return f"sh{code}"  # 默认上海
    
    # 指数处理
    # 腾讯API：399开头→深圳(sz)，其他(000xxx等上证指数)→上海(sh)
    if stock_type == "指数":
        if code.startswith("399"):
            return f"sz{code}"
        else:
            return f"sh{code}"
    
    # 股票判断
    first_char = code[0]
    if first_char in ('5', '6', '9'):  # 上海：6开头主板、5开头ETF/基金、9开头沪市其他
        return f"sh{code}"
    elif first_char in ('0', '1', '2', '3', '4', '8'):  # 深圳：0/1/2/3/4/8开头
        return f"sz{code}"
    else:
        return f"sz{code}"  # 默认深圳


def _get_em_secid(symbol, stock_type="stock"):
    """
    获取东方财富API的secid格式
    1 = 上海市场
    0 = 深圳市场（包括创业板、中小板、北交所）
    """
    symbol = symbol.zfill(6)
    
    if stock_type == "ETF":
        # ETF判断
        if symbol.startswith("15") or symbol.startswith("16") or symbol.startswith("13"):
            return f"0.{symbol}"  # 深圳ETF
        else:
            return f"1.{symbol}"  # 上海ETF
    
    if stock_type == "指数":
        # 东方财富API：399开头→深圳(0)，000xxx等上证指数→上海(1)
        if symbol.startswith("399"):
            return f"0.{symbol}"
        else:
            return f"1.{symbol}"
    
    # 股票判断
    if symbol.startswith("6") or symbol.startswith("9") or symbol.startswith("8"):
        return f"1.{symbol}"  # 上海主板、科创板
    elif symbol.startswith("4") or symbol.startswith("8"):
        return f"0.{symbol}"  # 北交所用0前缀
    else:
        return f"0.{symbol}"  # 深圳主板、创业板、中小板


def _fetch_from_tencent(symbol, start_date, end_date, stock_type="stock"):
    """
    从腾讯财经API获取数据，支持分段拉取获取5-7年历史数据
    
    腾讯API每次最多800条，分段拉取可以获取完整的历史数据
    """
    symbol = symbol.zfill(6)
    secid = _get_tencent_secid(symbol, stock_type)
    
    # 将请求的日期范围分成多段，每段最多780条（约3年交易日）
    segments = _split_date_range(start_date, end_date, max_per_segment=780)
    
    all_klines = []
    
    for seg_start, seg_end in segments:
        url = f"{TENCENT_API_BASE}?_var=kline_dayqfq&param={secid},day,{seg_start},{seg_end},800,qfq"
        
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            text = resp.text
            
            if not text or '=' not in text:
                continue  # 该段失败，尝试下一段
            
            # 解析JSONP
            json_str = text[text.index('=') + 1:]
            data = json.loads(json_str)
            
            if f"{secid}" not in data.get('data', {}):
                continue  # 该段失败
            
            stock_data = data['data'][f"{secid}"]
            
            # ETF使用day字段，股票使用qfqday字段
            # 股票也尝试day字段作为fallback
            day_data = stock_data.get('qfqday', [])
            if not day_data and stock_type == "ETF":
                day_data = stock_data.get('day', [])
            elif not day_data:
                day_data = stock_data.get('day', [])
            
            if day_data:
                all_klines.extend(day_data)
                
        except Exception:
            continue  # 该段失败，继续下一段
    
    if not all_klines:
        raise DataFetchError(f"{symbol} 腾讯API无数据", "tencent_empty")
    
    # 解析数据
    records = []
    for item in all_klines:
        if len(item) >= 6:
            try:
                records.append({
                    'date': item[0],
                    'open': float(item[1]),
                    'close': float(item[2]),
                    'high': float(item[3]),
                    'low': float(item[4]),
                    'volume': float(item[5])
                })
            except (ValueError, IndexError):
                continue
    
    if not records:
        raise DataFetchError(f"{symbol} 腾讯API数据解析失败", "tencent_parse")
    
    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['date'])
    
    # 去重（按日期）+ 排序
    df = df.drop_duplicates(subset=['date'], keep='last')
    df = df.sort_values('date').reset_index(drop=True)
    
    # 按日期筛选
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
    
    if len(df) == 0:
        raise DataFetchError(f"{symbol} 腾讯API数据为空", "tencent_empty")
    
    return df


def _fetch_from_eastmoney(symbol, start_date, end_date, stock_type="stock"):
    """从东方财富API获取数据（支持获取5-7年历史数据）- 备用数据源"""
    symbol = symbol.zfill(6)
    secid = _get_em_secid(symbol, stock_type)
    
    # 计算获取的数据量：7年约1750条交易日
    lmt = 2000  # 请求2000条，足够5-7年
    
    url = f"{EM_API_BASE}?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&fqt=1&end=20991231&lmt={lmt}"
    
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        
        data = resp.json()
        
        klines = data.get('data', {}).get('klines', [])
        
        if not klines:
            raise DataFetchError(f"{symbol} 东方财富API无K线数据", "em_no_data")
        
        # 解析数据
        records = []
        for kline in klines:
            parts = kline.split(',')
            if len(parts) >= 6:
                try:
                    records.append({
                        'date': parts[0],
                        'open': float(parts[1]),
                        'close': float(parts[2]),
                        'high': float(parts[3]),
                        'low': float(parts[4]),
                        'volume': float(parts[5])
                    })
                except (ValueError, IndexError):
                    continue
        
        if not records:
            raise DataFetchError(f"{symbol} 东方财富API数据解析失败", "em_parse_error")
        
        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        
        # 按日期筛选
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
        
        df = df.sort_values('date').reset_index(drop=True)
        
        if len(df) == 0:
            raise DataFetchError(f"{symbol} 东方财富API数据为空", "em_empty")
        
        return df
        
    except requests.exceptions.Timeout:
        raise DataFetchError(f"{symbol} 东方财富API超时", "em_timeout")
    except requests.exceptions.ConnectionError as e:
        raise DataFetchError(f"{symbol} 东方财富API连接失败", "em_connection")
    except (ConnectionError, RemoteDisconnected) as e:
        raise DataFetchError(f"{symbol} 东方财富API连接中断", "em_connection")
    except KeyError:
        raise DataFetchError(f"{symbol} 东方财富API返回数据异常", "em_key_error")
    except json.JSONDecodeError:
        raise DataFetchError(f"{symbol} 东方财富API返回JSON解析失败", "em_parse")
    except DataFetchError:
        raise
    except Exception as e:
        raise DataFetchError(f"{symbol} 东方财富API错误: {str(e)}", "em_error")


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
    获取K线数据，本地优先模式（v5.3 全量数据本地化）
    
    获取顺序：
    1. 本地parquet缓存（优先使用，即使过期也用，因为全量数据已下载）
    2. 在线获取仅作为兜底（如果本地没有数据）
    3. 返回本地数据或报错
    
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
    
    # 1. 优先读取本地parquet（即使过期也使用，因为全量数据已下载到本地）
    local_df = _read_local_parquet(symbol, start_date, end_date)
    if local_df is not None and len(local_df) > 0:
        return local_df
    
    # 2. 本地没有才在线获取（兜底，仅用于首次下载）
    errors = []
    
    # 腾讯API获取
    for attempt in range(TENCENT_RETRIES):
        try:
            df = _fetch_from_tencent(symbol, start_date, end_date, stock_type)
            if df is not None and len(df) > 0:
                _save_to_parquet(df, symbol)
                return df
        except (ConnectionError, RemoteDisconnected, Timeout, SSLError) as e:
            errors.append(f"腾讯API: {type(e).__name__}")
        except DataFetchError as e:
            errors.append(f"腾讯API: {e.message}")
        except Exception as e:
            errors.append(f"腾讯API: {str(e)}")
        if attempt < TENCENT_RETRIES - 1:
            time.sleep(TENCENT_RETRY_DELAY)
    
    # 东方财富API获取
    for attempt in range(EM_RETRIES):
        try:
            df = _fetch_from_eastmoney(symbol, start_date, end_date, stock_type)
            if df is not None and len(df) > 0:
                _save_to_parquet(df, symbol)
                return df
        except Exception as e:
            errors.append(f"东方财富: {str(e)}")
        if attempt < EM_RETRIES - 1:
            time.sleep(EM_RETRY_DELAY)
    
    # akshare获取
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
            except (DataNotFoundError, DataSuspendedError) as e:
                errors.append(f"akshare: {e.message}")
                break
            except Exception as e:
                errors.append(f"akshare: {str(e)}")
            if attempt < AKSHARE_RETRIES - 1:
                time.sleep(AKSHARE_RETRY_DELAY)
    
    # 全失败
    raise DataFetchError(f"数据获取失败: {'; '.join(errors)}", "all_sources_failed")


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
