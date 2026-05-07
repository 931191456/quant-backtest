# -*- coding: utf-8 -*-
"""
全量A股+ETF+指数5年日K数据下载脚本
使用akshare下载所有标的到本地parquet
"""
import akshare as ak
import pandas as pd
import json
import os
import time
from datetime import datetime

DATA_DIR = 'data'
JSON_FILE = 'all_stocks.json'
START_DATE = '20200101'  # 5年数据
END_DATE = datetime.now().strftime('%Y%m%d')

os.makedirs(DATA_DIR, exist_ok=True)

# 加载全量标的列表
with open(JSON_FILE, 'r', encoding='utf-8') as f:
    all_items = json.load(f)

print(f"总标的数: {len(all_items)}")
success = 0
fail = 0
skip = 0
existing = 0

for i, (code, info) in enumerate(all_items.items()):
    name = info['name']
    stock_type = info['type']
    
    # 跳过ST和退市
    if '退' in name or 'ST' in name or '*' in name:
        skip += 1
        continue
    
    parquet_path = os.path.join(DATA_DIR, f'{code}.parquet')
    
    # 已存在且足够新就跳过
    if os.path.exists(parquet_path):
        try:
            df = pd.read_parquet(parquet_path)
            if 'date' in df.columns and len(df) > 0:
                latest = pd.to_datetime(df['date']).max()
                if (datetime.now() - latest).days <= 5:
                    existing += 1
                    continue
        except:
            pass
    
    try:
        if stock_type == 'ETF':
            df = ak.fund_etf_hist_em(symbol=code, period='daily', 
                                      start_date=START_DATE, end_date=END_DATE, adjust='qfq')
        elif stock_type == '指数':
            df = ak.index_zh_a_hist(symbol=code, period='daily',
                                     start_date=START_DATE, end_date=END_DATE)
        else:  # 股票
            df = ak.stock_zh_a_hist(symbol=code, period='daily',
                                     start_date=START_DATE, end_date=END_DATE, adjust='qfq')
        
        if df is not None and len(df) > 0:
            # 统一列名
            col_map = {
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume',
                '成交额': 'amount', '涨跌幅': 'pct_change'
            }
            df = df.rename(columns=col_map)
            
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                for col in ['open', 'close', 'high', 'low', 'volume']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df.sort_values('date').reset_index(drop=True)
                # 只保留需要的列
                keep_cols = [c for c in ['date', 'open', 'close', 'high', 'low', 'volume'] if c in df.columns]
                df = df[keep_cols]
                df.to_parquet(parquet_path, index=False)
                success += 1
                if (i+1) % 100 == 0:
                    print(f'[{i+1}/{len(all_items)}] 已有{existing}, 新增{success}, 失败{fail}, 跳过{skip}')
            else:
                fail += 1
        else:
            fail += 1
    except Exception as e:
        fail += 1
        if fail <= 10:
            print(f'失败: {code} {name} - {str(e)[:50]}')
    
    # 控制频率，避免被封
    time.sleep(0.3)

print(f'\n========== 完成! ==========')
print(f'已有: {existing}, 新增: {success}, 失败: {fail}, 跳过: {skip}')
