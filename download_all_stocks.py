# -*- coding: utf-8 -*-
"""
下载全量A股+ETF+指数数据到本地JSON文件
用途：替换东方财富在线API搜索，本地搜索更稳定
"""

import akshare as ak
import json
import time
import sys

print("=" * 50)
print("开始下载全量市场数据...")
print("=" * 50)

all_items = {}
stock_count = 0
etf_count = 0

# 1. 全部A股（使用轻量接口）
print("\n[1/3] 下载全部A股列表...")
try:
    # 使用轻量接口获取A股代码和名称
    df_stock = ak.stock_info_a_code_name()
    print(f"  获取到 {len(df_stock)} 只A股")
    
    # 检查列名
    print(f"  列名: {list(df_stock.columns)}")
    
    # 根据实际列名获取代码和名称
    for _, row in df_stock.iterrows():
        code = str(row.get('code', row.get('代码', ''))).strip()
        name = str(row.get('name', row.get('名称', ''))).strip()
        
        if not code or not name:
            continue
        
        # 过滤退市等
        if '退' in name:
            continue
        
        all_items[code] = {"name": name, "type": "股票"}
        stock_count += 1
        
    print(f"  A股: {stock_count} 只")
    
except Exception as e:
    print(f"  A股下载失败: {e}")
    import traceback
    traceback.print_exc()

time.sleep(1)

# 2. 全部ETF
print("\n[2/3] 下载全部ETF列表...")
try:
    df_etf = ak.fund_etf_spot_em()
    print(f"  获取到 {len(df_etf)} 只ETF")
    
    for _, row in df_etf.iterrows():
        code = str(row['代码']).strip()
        name = str(row['名称']).strip()
        
        if not code or not name:
            continue
        if code in all_items:  # 避免重复
            continue
            
        all_items[code] = {"name": name, "type": "ETF"}
        etf_count += 1
        
    print(f"  ETF: {etf_count} 只")
except Exception as e:
    print(f"  ETF下载失败: {e}")

time.sleep(1)

# 3. 主要指数
print("\n[3/3] 添加主要指数...")
indices = {
    # 主要宽基指数
    "000001": "上证指数",
    "399001": "深证成指",
    "399006": "创业板指",
    "000300": "沪深300",
    "000016": "上证50",
    "000905": "中证500",
    "000852": "中证1000",
    "399303": "国证2000",
    "000688": "科创50",
    "399005": "中小板指",
    "399106": "深证综指",
    "899050": "北证50",
    # 行业指数
    "000912": "证券公司",
    "000993": "全指金融",
    "000928": "中证内地低碳",
    "000978": "中证医药100",
    "000925": "中证基本面50",
    "000926": "中证央企",
    # 海外指数
    "HSI": "恒生指数",
    "SPX": "标普500",
    "IXIC": "纳斯达克",
    "DJI": "道琼斯",
}

index_count = 0
for code, name in indices.items():
    if code not in all_items:
        all_items[code] = {"name": name, "type": "指数"}
        index_count += 1

print(f"  指数: {index_count} 只")

# 保存
output_file = 'all_stocks.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(all_items, f, ensure_ascii=False, indent=1)

print("\n" + "=" * 50)
print(f"完成! 总计: {len(all_items)} 条")
print(f"  - A股: {stock_count} 只")
print(f"  - ETF: {etf_count} 只")
print(f"  - 指数: {index_count} 只")
print(f"文件: {output_file}")
print("=" * 50)
