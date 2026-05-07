# -*- coding: utf-8 -*-
"""
数据获取模块 v4.0
全市场覆盖：搜索统一走东方财富在线API，支持全市场股票/ETF/指数
内置字典仅用于首页热门推荐展示
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

# ==================== 内置字典（用于搜索） ====================
BUILTIN_STOCKS = {
    # 沪深主板热门
    "000001": "平安银行", "000002": "万科A", "000063": "中兴通讯", "000100": "TCL科技",
    "000157": "中联重科", "000333": "美的集团", "000338": "潍柴动力", "000425": "徐工机械",
    "000538": "云南白药", "000568": "泸州老窖", "000596": "古井贡酒", "000651": "格力电器",
    "000661": "长春高新", "000708": "大冶特钢", "000725": "京东方A", "000729": "燕京啤酒",
    "000768": "中航西飞", "000858": "五粮液", "000876": "新希望", "000895": "双汇发展",
    "000898": "鞍钢股份", "000932": "华菱钢铁", "000938": "紫光股份",
    "600000": "浦发银行", "600004": "白云机场", "600009": "上海机场", "600011": "华能国际",
    "600015": "华夏银行", "600016": "民生银行", "600018": "上港集团", "600019": "宝钢股份",
    "600023": "浙能电力", "600026": "中金公司", "600028": "中国石化", "600029": "南方航空",
    "600030": "中信证券", "600031": "三一重工", "600036": "招商银行", "600038": "中航沈飞",
    "600048": "保利发展", "600050": "中国联通", "600056": "中国医药", "600061": "国投资本",
    "600066": "宇通客车", "600089": "特变电工", "600100": "同方股份", "600104": "上汽集团",
    "600109": "国金证券", "600111": "北方稀土", "600115": "东方航空", "600118": "中国卫星",
    "600150": "中国船舶", "600153": "建发股份", "600160": "巨化股份", "600170": "上海建工",
    "600183": "生益科技", "600188": "兖州煤业", "600196": "复星医药", "600208": "新湖中宝",
    "600219": "南山铝业", "600236": "桂冠电力", "600256": "广汇能源", "600267": "海正药业",
    "600276": "恒瑞医药", "600309": "万华化学", "600346": "恒力石化", "600352": "浙江龙盛",
    "600362": "江西铜业", "600383": "金地集团", "600406": "国电南瑞", "600418": "江淮汽车",
    "600426": "华鲁恒升", "600436": "片仔癀", "600438": "通威股份", "600460": "士兰微",
    "600489": "中金黄金", "600497": "驰宏锌锗", "600519": "贵州茅台", "600547": "山东黄金",
    "600570": "恒生电子", "600585": "海螺水泥", "600588": "用友网络", "600606": "绿地控股",
    "600690": "海尔智家", "600703": "三安光电", "600741": "华域汽车", "600745": "闻泰科技",
    "600760": "中航沈飞", "600809": "山西汾酒", "600837": "海通证券", "600887": "伊利股份",
    "600893": "航发动力", "600900": "长江电力", "600905": "三峡能源", "601006": "大秦铁路",
    "601012": "隆基绿能", "601066": "中信建投", "601088": "中国神华", "601118": "海南橡胶",
    "601166": "兴业银行", "601186": "中国铁建", "601211": "国泰君安", "601225": "陕西煤业",
    "601288": "农业银行", "601318": "中国平安", "601328": "交通银行", "601336": "新华保险",
    "601390": "中国中铁", "601398": "工商银行", "601601": "中国太保", "601628": "中国人寿",
    "601668": "中国建筑", "601688": "华泰证券", "601818": "光大银行", "601857": "中国石油",
    "601888": "中国中免", "601939": "建设银行", "601989": "中国重工", "601998": "中信银行",
    "603259": "药明康德", "603288": "海天味业", "603501": "韦尔股份", "603799": "华友钴业",
    "603986": "兆易创新",
    # 创业板
    "300001": "特锐德", "300002": "神州泰岳", "300003": "乐普医疗", "300004": "南风股份",
    "300015": "爱尔眼科", "300033": "同花顺", "300059": "东方财富", "300124": "汇川技术",
    "300142": "沃森生物", "300223": "北京君正", "300274": "阳光电源", "300364": "中文在线",
    "300498": "温氏股份", "300601": "康泰生物", "300662": "科锐国际", "300750": "宁德时代",
    "300896": "爱美客",
    # 科创板
    "688001": "华兴源创", "688005": "容百科技", "688008": "澜起科技", "688009": "中国通号",
    "688012": "中微公司", "688036": "传音控股", "688111": "金山办公", "688126": "沪硅产业",
    "688185": "康希诺", "688187": "时代电气", "688223": "晶科能源", "688363": "华熙生物",
    "688981": "中芯国际",
}

BUILTIN_ETFS = {
    "510050": "上证50ETF", "510100": "纳指ETF", "510300": "沪深300ETF", "510500": "中证500ETF",
    "510900": "H股ETF", "512000": "证券ETF", "512100": "MSCI易基", "512200": "房地产ETF",
    "512380": "银行ETF", "512480": "半导体ETF", "512660": "军工ETF", "512690": "酒ETF",
    "512760": "芯片ETF", "512880": "证券ETF", "513050": "中概互联ETF", "513100": "纳指ETF",
    "513500": "标普500ETF", "513660": "港股通ETF", "515000": "科技ETF", "515050": "5GETF",
    "515120": "创新药ETF", "515170": "食品饮料ETF", "515220": "煤炭ETF", "515980": "云计算ETF",
    "516020": "化工ETF", "516350": "稀土ETF", "516950": "基建ETF", "518880": "黄金ETF",
    "159915": "创业板ETF", "159901": "深证100ETF", "159919": "沪深300ETF", "159928": "中证消费ETF",
    "159941": "纳指ETF", "159995": "芯片ETF", "588000": "科创50ETF", "588050": "科创ETF",
}

BUILTIN_INDICES = {
    "000001": "上证指数", "399001": "深证成指", "399006": "创业板指", "000300": "沪深300",
    "000016": "上证50", "000905": "中证500", "000852": "中证1000", "399005": "中小板指",
    "399673": "创业板50", "000688": "科创50", "399106": "深证综指", "899050": "北证50",
}

# 统一搜索字典
ALL_ITEMS = {}
for code, name in BUILTIN_STOCKS.items():
    ALL_ITEMS[code] = {"name": name, "type": "股票"}
for code, name in BUILTIN_ETFS.items():
    if code not in ALL_ITEMS:
        ALL_ITEMS[code] = {"name": name, "type": "ETF"}
for code, name in BUILTIN_INDICES.items():
    if code not in ALL_ITEMS:
        ALL_ITEMS[code] = {"name": name, "type": "指数"}


def _query_stock_info_online(code):
    """通过东方财富搜索API在线查询股票/ETF信息"""
    import requests
    url = "https://searchapi.eastmoney.com/api/suggest/get"
    params = {
        "input": code,
        "type": "14",
        "token": "D43BF722C8E33BDC906FB84D85E326E8",
        "count": "5"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/"
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        if data and 'QuotationCodeTable' in data and 'Data' in data['QuotationCodeTable']:
            items = data['QuotationCodeTable']['Data']
            for item in items:
                if item.get('Code') == code or item.get('UnifiedCode') == code:
                    name = item.get('Name', '')
                    security_type = item.get('SecurityTypeName', '')
                    # 判断类型
                    if 'ETF' in name.upper() or '基金' in security_type:
                        stock_type = "ETF"
                    elif '指数' in security_type or 'Index' in security_type:
                        stock_type = "指数"
                    else:
                        stock_type = "股票"
                    return {"code": code, "name": name, "type": stock_type}
    except:
        pass
    return None


def _get_item_type(name, security_type):
    """根据名称和安全类型判断标的类型"""
    if 'ETF' in name.upper() or '基金' in security_type or 'LOF' in name.upper():
        return "ETF"
    elif '指数' in security_type or 'Index' in security_type:
        return "指数"
    else:
        return "股票"


def search_all(keyword, limit=10):
    """
    统一搜索：全量走东方财富在线API搜索
    内置字典不再用于搜索结果，仅用于首页热门推荐
    支持中文名称、代码、拼音首字母搜索
    """
    if not keyword or len(keyword.strip()) == 0:
        return []
    
    keyword = keyword.strip()
    
    try:
        import requests
        url = "https://searchapi.eastmoney.com/api/suggest/get"
        params = {
            "input": keyword,
            "type": "14",
            "token": "D43BF722C8E33BDC906FB84D85E326E8",
            "count": str(limit)
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://data.eastmoney.com/"
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        
        results = []
        if data and 'QuotationCodeTable' in data and 'Data' in data['QuotationCodeTable']:
            for item in data['QuotationCodeTable']['Data']:
                code = item.get('UnifiedCode') or item.get('Code', '')
                name = item.get('Name', '')
                security_type = item.get('SecurityTypeName', '')
                
                if code and name:
                    item_type = _get_item_type(name, security_type)
                    results.append({
                        "code": code,
                        "name": name,
                        "type": item_type
                    })
        
        return results
        
    except Exception as e:
        # 搜索失败时返回空列表，不影响用户使用
        print(f"搜索API错误: {e}")
        return []


# ==================== 异常错误类 ====================
class DataFetchError(Exception):
    """数据获取错误"""
    def __init__(self, message, error_type="unknown"):
        self.message = message
        self.error_type = error_type
        super().__init__(self.message)


class DataTimeoutError(DataFetchError):
    """超时错误"""
    def __init__(self, message="数据获取超时，请稍后重试"):
        super().__init__(message, "timeout")


class DataNotFoundError(DataFetchError):
    """未找到错误"""
    def __init__(self, code):
        super().__init__(f"未找到股票 {code}，请检查代码是否正确", "not_found")


class DataSuspendedError(DataFetchError):
    """停牌错误"""
    def __init__(self, code):
        super().__init__(f"股票 {code} 当前停牌或无数据", "suspended")


# ==================== 超时装饰器 ====================
def timeout_handler(signum, frame):
    raise TimeoutError("请求超时")


def with_timeout(func):
    """带超时的函数装饰器"""
    def wrapper(*args, **kwargs):
        # 注意：这里简化了，实际可用signal或threading实现真正的超时
        return func(*args, **kwargs)
    return wrapper


# ==================== 腾讯财经API（主数据源） ====================
def _fetch_from_tencent(symbol, start_date, end_date, stock_type="stock"):
    """
    从腾讯财经API获取K线数据（最可靠的数据源）
    
    Parameters:
    -----------
    symbol : str - 股票/ETF代码
    start_date : str - 开始日期，格式YYYYMMDD
    end_date : str - 结束日期，格式YYYYMMDD
    stock_type : str - 类型：stock/ETF/指数
        
    Returns:
    --------
    pd.DataFrame : 包含date, open, close, high, low, volume列
    """
    import requests
    
    # 构造腾讯格式的代码：sh/sz + 6位代码
    if symbol.startswith(('5', '6', '9')):
        secid = f"sh{symbol}"
    else:
        secid = f"sz{symbol}"
    
    # 指数特殊处理
    if stock_type == "指数":
        if symbol.startswith('000'):
            secid = f"sh{symbol}"  # 上证指数等
        elif symbol.startswith('399'):
            secid = f"sz{symbol}"  # 深证指数等
    
    # 格式化日期为YYYY-MM-DD
    start_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
    end_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
    
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {
        "param": f"{secid},day,{start_fmt},{end_fmt},800,qfq"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        data = resp.json()
    except Exception as e:
        raise DataFetchError(f"腾讯财经API请求失败: {str(e)}", "tencent_request_error")
    
    if not data or data.get('code') != 0 or 'data' not in data:
        raise DataFetchError("腾讯财经API返回异常", "tencent_bad_response")
    
    # 解析数据：data -> {secid: {day/qfqday: [...]}}
    stock_data = data['data']
    key = list(stock_data.keys())[0] if stock_data else None
    if not key:
        raise DataFetchError("腾讯财经API返回空数据", "tencent_empty_data")
    
    # 优先用前复权数据
    klines = stock_data[key].get('qfqday', []) or stock_data[key].get('day', [])
    if not klines:
        raise DataFetchError("腾讯财经API返回空K线", "tencent_empty_klines")
    
    rows = []
    for item in klines:
        # 格式：[日期, 开盘, 收盘, 最高, 最低, 成交量]
        if len(item) >= 6:
            rows.append({
                'date': item[0],
                'open': float(item[1]) if item[1] else 0,
                'close': float(item[2]) if item[2] else 0,
                'high': float(item[3]) if item[3] else 0,
                'low': float(item[4]) if item[4] else 0,
                'volume': float(item[5]) if item[5] else 0,
                'amount': 0  # 腾讯API不直接返回成交额
            })
    
    if not rows:
        raise DataFetchError("腾讯财经API数据解析失败", "tencent_parse_error")
    
    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    return df


# ==================== 核心：本地Parquet读取 ====================
def _read_local_parquet(code, start_date=None, end_date=None):
    """从本地parquet读取数据"""
    parquet_path = os.path.join(DATA_DIR, f"{code}.parquet")
    
    if not os.path.exists(parquet_path):
        return None
    
    try:
        df = pd.read_parquet(parquet_path, engine='pyarrow')
        
        if df is None or len(df) == 0:
            return None
        
        if 'date' not in df.columns:
            return None
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        # 日期筛选
        if start_date:
            if isinstance(start_date, str):
                start_date = pd.to_datetime(start_date)
            df = df[df['date'] >= start_date]
        if end_date:
            if isinstance(end_date, str):
                end_date = pd.to_datetime(end_date)
            df = df[df['date'] <= end_date]
        
        return df
    except Exception:
        return None


def _check_data_freshness(df):
    """检查数据新鲜度"""
    if df is None or len(df) == 0:
        return True  # 需要更新
    
    try:
        last_date = pd.to_datetime(df['date'].max())
        days_since_update = (datetime.now() - last_date).days
        return days_since_update > DATA_STALE_DAYS
    except:
        return True


def _save_to_parquet(df, code):
    """保存数据到parquet"""
    parquet_path = os.path.join(DATA_DIR, f"{code}.parquet")
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_parquet(parquet_path, engine='pyarrow')
        return True
    except:
        return False


# ==================== 数据获取（完善的异常处理） ====================
def _fetch_etf_from_akshare(symbol, start_date, end_date, adjust="qfq"):
    if ak is None: raise DataFetchError("akshare未安装，请检查依赖", "no_akshare")
    """从akshare获取ETF数据，失败则fallback到腾讯财经API"""
    try:
        df = ak.fund_etf_hist_em(
            symbol=symbol, period="daily",
            start_date=start_date, end_date=end_date, adjust=adjust
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
        if '停牌' in err_msg or '无数据' in err_msg:
            raise DataSuspendedError(symbol)
        # akshare失败，fallback到腾讯财经API
        try:
            return _fetch_from_tencent(symbol, start_date, end_date, "ETF")
        except DataFetchError:
            raise DataFetchError(str(e), "akshare_error")


def _fetch_stock_from_akshare(symbol, start_date, end_date, adjust="qfq"):
    if ak is None: raise DataFetchError("akshare未安装，请检查依赖", "no_akshare")
    """从akshare获取股票数据，失败则fallback到腾讯财经API"""
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start_date, end_date=end_date, adjust=adjust
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
        if '不存在' in err_msg or 'not found' in err_msg:
            raise DataNotFoundError(symbol)
        if '停牌' in err_msg or '无数据' in err_msg:
            raise DataSuspendedError(symbol)
        # akshare失败，fallback到腾讯财经API
        try:
            return _fetch_from_tencent(symbol, start_date, end_date, "stock")
        except DataFetchError:
            raise DataFetchError(str(e), "akshare_error")


def _fetch_index_from_akshare(symbol, start_date, end_date):
    if ak is None: raise DataFetchError("akshare未安装，请检查依赖", "no_akshare")
    """从akshare获取指数数据，失败则fallback到腾讯财经API"""
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
        # akshare失败，fallback到腾讯财经API
        try:
            return _fetch_from_tencent(symbol, start_date, end_date, "指数")
        except DataFetchError:
            raise DataFetchError(str(e), "akshare_error")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_etf_data(symbol, start_date, end_date, adjust="qfq"):
    """获取ETF历史数据：优先本地缓存，其次腾讯API，最后akshare"""
    symbol = symbol.zfill(6)
    
    # 1. 读本地缓存
    df = _read_local_parquet(symbol, start_date, end_date)
    if df is not None and len(df) > 0 and not _check_data_freshness(df):
        return df
    
    # 2. 腾讯财经API（最可靠）
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
    
    # 4. 返回旧缓存（即使过期）
    if df is not None and len(df) > 0:
        return df
    
    raise DataFetchError(f"无法获取ETF {symbol} 的数据", "all_sources_failed")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(symbol, start_date, end_date, adjust="qfq"):
    """获取个股历史数据：优先本地缓存，其次腾讯API，最后akshare"""
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
def fetch_index_data(symbol, start_date, end_date):
    """获取指数历史数据：优先本地缓存，其次腾讯API，最后akshare"""
    symbol = symbol.zfill(6)
    
    # 1. 读本地缓存
    df = _read_local_parquet(symbol, start_date, end_date)
    if df is not None and len(df) > 0 and not _check_data_freshness(df):
        return df
    
    # 2. 腾讯财经API（最可靠）
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
    
    # 4. 返回旧缓存（即使过期）
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
def get_stock_name_cached(symbol, stock_type="stock"):
    symbol = symbol.zfill(6)
    if stock_type == "ETF":
        return BUILTIN_ETFS.get(symbol, symbol)
    elif stock_type == "指数":
        return BUILTIN_INDICES.get(symbol, symbol)
    else:
        return BUILTIN_STOCKS.get(symbol, symbol)


def get_stock_name(symbol, stock_type="stock"):
    return get_stock_name_cached(symbol, stock_type)


@st.cache_data(ttl=86400, show_spinner=False)
def get_stock_list_cached():
    return list(BUILTIN_STOCKS.items())


@st.cache_data(ttl=86400, show_spinner=False)
def get_etf_list_cached():
    return list(BUILTIN_ETFS.items())


def search_stocks(keyword, stock_type="stock", limit=10):
    if not keyword:
        return []
    keyword = keyword.upper()
    results = []
    if stock_type == "ETF":
        stock_dict = BUILTIN_ETFS
    elif stock_type == "指数":
        stock_dict = BUILTIN_INDICES
    else:
        stock_dict = BUILTIN_STOCKS
    for code, name in stock_dict.items():
        if keyword in str(code) or keyword.upper() in name.upper():
            results.append((code, name))
            if len(results) >= limit:
                break
    return results


@st.cache_data(ttl=86400, show_spinner=False)
def get_hot_stocks():
    return [
        ("000001", "平安银行"), ("000002", "万科A"), ("600000", "浦发银行"),
        ("600519", "贵州茅台"), ("600036", "招商银行"), ("000858", "五粮液"),
        ("601318", "中国平安"), ("000333", "美的集团"), ("002594", "比亚迪"),
        ("300750", "宁德时代"), ("688981", "中芯国际"), ("515000", "科技ETF"),
        ("513500", "标普500ETF"), ("510300", "沪深300ETF"), ("159915", "创业板ETF"),
    ]
