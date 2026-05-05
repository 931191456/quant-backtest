# -*- coding: utf-8 -*-
"""
数据下载脚本 v2 - 下载A股热门股票+ETF+指数的1年日线数据到parquet文件
"""

import akshare as ak
import pandas as pd
import os
import time
from datetime import datetime

# 数据存储目录
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 开始日期（1年前）
START_DATE = "20240101"
END_DATE = datetime.now().strftime("%Y%m%d")

# ==================== 指数列表 ====================
INDICES = {
    "000001": "上证指数",
    "399001": "深证成指",
    "000300": "沪深300",
    "000905": "中证500",
    "399006": "创业板指",
    "000688": "科创50",
    "000016": "上证50",
    "000852": "中证1000",
    "399673": "国证2000",
    "899050": "北证50",
}

# ==================== 主流ETF列表 ====================
ETFS = {
    "510050": "上证50ETF", "510100": "纳指ETF", "510300": "沪深300ETF", "510500": "中证500ETF",
    "510900": "H股ETF", "512000": "证券ETF", "512100": "MSCI易基", "512200": "房地产ETF",
    "512380": "银行ETF", "512480": "半导体ETF", "512660": "军工ETF", "512760": "芯片ETF",
    "512880": "证券ETF", "513050": "中概互联ETF", "513100": "纳指ETF", "513500": "标普500ETF",
    "513660": "港股通ETF", "515000": "科技ETF", "515050": "5GETF", "515120": "创新药ETF",
    "515170": "食品饮料ETF", "515220": "煤炭ETF", "515980": "云计算ETF", "516020": "化工ETF",
    "516350": "稀土ETF", "516950": "基建ETF", "518880": "黄金ETF", "159915": "创业板ETF",
    "159901": "深证100ETF", "159919": "沪深300ETF", "159928": "中证消费ETF", "159941": "纳指ETF",
    "159995": "芯片ETF", "588000": "科创50ETF", "588050": "科创ETF",
}

# ==================== 获取沪深300成分股 ====================
def get_hs300_stocks():
    """获取沪深300成分股"""
    try:
        print("📥 正在获取沪深300成分股列表...")
        df = ak.index_stock_cons(symbol="000300")
        codes = df['品种代码'].tolist()
        names = df['品种名称'].tolist()
        result = dict(zip(codes, names))
        print(f"✅ 获取到 {len(result)} 只沪深300成分股")
        return result
    except Exception as e:
        print(f"❌ 获取沪深300成分股失败: {e}")
        return {}

# ==================== 获取中证500成分股 ====================
def get_zz500_stocks():
    """获取中证500成分股"""
    try:
        print("📥 正在获取中证500成分股列表...")
        df = ak.index_stock_cons(symbol="000905")
        codes = df['品种代码'].tolist()
        names = df['品种名称'].tolist()
        result = dict(zip(codes, names))
        print(f"✅ 获取到 {len(result)} 只中证500成分股")
        return result
    except Exception as e:
        print(f"❌ 获取中证500成分股失败: {e}")
        return {}


# ==================== 下载指数数据 ====================
def download_index(code, name):
    """下载指数数据"""
    parquet_path = os.path.join(DATA_DIR, f"{code}.parquet")
    if os.path.exists(parquet_path):
        print(f"⏭️  {name}({code}) 已存在")
        return True
    
    try:
        df = ak.index_zh_a_hist(symbol=code, period="daily", start_date=START_DATE, end_date=END_DATE)
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_change',
            '涨跌额': 'change', '换手率': 'turnover'
        })
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df.to_parquet(parquet_path)
        print(f"✅ {name}({code}) - {len(df)} 条")
        return True
    except Exception as e:
        print(f"❌ {name}({code}): {e}")
        return False


# ==================== 下载股票数据 ====================
def download_stock(code, name):
    """下载股票数据"""
    parquet_path = os.path.join(DATA_DIR, f"{code}.parquet")
    if os.path.exists(parquet_path):
        return True
    
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=START_DATE, end_date=END_DATE, adjust="qfq")
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_change',
            '涨跌额': 'change', '换手率': 'turnover'
        })
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df.to_parquet(parquet_path)
        print(f"✅ {name}({code})")
        return True
    except Exception as e:
        print(f"❌ {name}({code}): {e}")
        return False


# ==================== 下载ETF数据 ====================
def download_etf(code, name):
    """下载ETF数据"""
    parquet_path = os.path.join(DATA_DIR, f"{code}.parquet")
    if os.path.exists(parquet_path):
        return True
    
    try:
        df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=START_DATE, end_date=END_DATE, adjust="qfq")
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_change',
            '涨跌额': 'change', '换手率': 'turnover'
        })
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df.to_parquet(parquet_path)
        print(f"✅ {name}({code})")
        return True
    except Exception as e:
        print(f"❌ {name}({code}): {e}")
        return False


# ==================== 主下载流程 ====================
def main():
    print("=" * 60)
    print("📦 量化回测系统 - 数据下载脚本 v2")
    print(f"📅 数据范围: {START_DATE} ~ {END_DATE}")
    print(f"📁 保存目录: {DATA_DIR}")
    print("=" * 60)
    
    success_count = 0
    fail_count = 0
    
    # 1. 下载指数数据
    print("\n📈 步骤1: 下载主要指数数据")
    for code, name in INDICES.items():
        if download_index(code, name):
            success_count += 1
        else:
            fail_count += 1
        time.sleep(0.2)
    
    # 2. 获取并下载沪深300成分股
    print("\n📊 步骤2: 获取并下载沪深300成分股")
    hs300 = get_hs300_stocks()
    for i, (code, name) in enumerate(hs300.items()):
        print(f"[{i+1}/{len(hs300)}] ", end="", flush=True)
        if download_stock(code, name):
            success_count += 1
        else:
            fail_count += 1
        time.sleep(0.15)
    
    # 3. 获取并下载中证500热门（前100只）
    print("\n📊 步骤3: 下载中证500热门成分股")
    zz500 = get_zz500_stocks()
    for i, (code, name) in enumerate(list(zz500.items())[:100]):
        print(f"[{i+1}/100] ", end="", flush=True)
        if download_stock(code, name):
            success_count += 1
        else:
            fail_count += 1
        time.sleep(0.15)
    
    # 4. 下载ETF
    print("\n📊 步骤4: 下载主流ETF")
    for i, (code, name) in enumerate(ETFS.items()):
        print(f"[{i+1}/{len(ETFS)}] ", end="", flush=True)
        if download_etf(code, name):
            success_count += 1
        else:
            fail_count += 1
        time.sleep(0.2)
    
    # 统计
    print("\n" + "=" * 60)
    print("📦 下载完成!")
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {fail_count}")
    
    files = os.listdir(DATA_DIR)
    total_size = sum(os.path.getsize(os.path.join(DATA_DIR, f)) for f in files)
    print(f"📁 共 {len(files)} 个文件, 总大小: {total_size / 1024 / 1024:.2f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
