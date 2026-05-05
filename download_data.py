# -*- coding: utf-8 -*-
"""
数据下载脚本 v4 - 下载A股全量数据 + ETF全量 + 指数全量
覆盖：A股全部(5000+) + ETF全部(800+) + 指数全部(50+)
"""

import akshare as ak
import pandas as pd
import os
import time
import random
import json
from datetime import datetime

# 数据存储目录
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 时间设置
START_DATE = "20240501"  # 1年前
END_DATE = datetime.now().strftime("%Y%m%d")

# 下载间隔（秒）
DOWNLOAD_INTERVAL = 0.15

# 统计文件
STATS_FILE = os.path.join(DATA_DIR, 'download_stats.json')


def load_stats():
    """加载下载统计"""
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    return {"success": [], "failed": [], "skipped": 0}


def save_stats(stats):
    """保存下载统计"""
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, ensure_ascii=False)


def get_all_assets():
    """获取所有需要下载的标的"""
    all_items = []
    
    print("📥 正在获取A股列表...")
    try:
        stock_df = ak.stock_zh_a_spot_em()
        for _, row in stock_df.iterrows():
            code = str(row.get('代码', '')).zfill(6)
            name = str(row.get('名称', ''))
            if code and name and code.isdigit():
                all_items.append({"code": code, "name": name, "type": "stock"})
        print(f"✅ 获取到 {len(stock_df)} 只A股")
    except Exception as e:
        print(f"❌ 获取A股列表失败: {e}")
    
    print("📥 正在获取ETF列表...")
    try:
        etf_df = ak.fund_etf_spot_em()
        for _, row in etf_df.iterrows():
            code = str(row.get('代码', '')).zfill(6)
            name = str(row.get('名称', ''))
            if code and name and code.isdigit():
                all_items.append({"code": code, "name": name, "type": "etf"})
        print(f"✅ 获取到 {len(etf_df)} 只ETF")
    except Exception as e:
        print(f"❌ 获取ETF列表失败: {e}")
    
    # 常用指数
    print("📥 添加主要指数...")
    fallback_indices = {
        "000001": "上证指数", "399001": "深证成指", "399006": "创业板指",
        "000300": "沪深300", "000016": "上证50", "000905": "中证500",
        "000852": "中证1000", "399005": "中小板指", "399673": "创业板50",
        "000688": "科创50", "399106": "深证综指", "899050": "北证50",
    }
    for code, name in fallback_indices.items():
        all_items.append({"code": code, "name": name, "type": "index"})
    print(f"✅ 添加 {len(fallback_indices)} 只主要指数")
    
    # 去重
    seen = set()
    unique_items = []
    for item in all_items:
        if item["code"] not in seen:
            seen.add(item["code"])
            unique_items.append(item)
    
    print(f"\n📊 去重后共 {len(unique_items)} 只标的")
    return unique_items


def download_item(item):
    """下载单个标的"""
    code = item["code"]
    name = item["name"]
    item_type = item["type"]
    parquet_path = os.path.join(DATA_DIR, f"{code}.parquet")
    
    if os.path.exists(parquet_path):
        return "skipped", None
    
    try:
        if item_type == "stock":
            df = ak.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date=START_DATE, end_date=END_DATE, adjust="qfq"
            )
        elif item_type == "etf":
            df = ak.fund_etf_hist_em(
                symbol=code, period="daily",
                start_date=START_DATE, end_date=END_DATE, adjust="qfq"
            )
        elif item_type == "index":
            df = ak.index_zh_a_hist(
                symbol=code, period="daily",
                start_date=START_DATE, end_date=END_DATE
            )
        
        if df is not None and len(df) > 0:
            df = df.rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume',
                '成交额': 'amount', '涨跌幅': 'pct_change',
                '涨跌额': 'change', '换手率': 'turnover'
            })
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            df.to_parquet(parquet_path)
            return "success", len(df)
        else:
            return "empty", None
            
    except Exception as e:
        err_msg = str(e)
        if '停牌' in err_msg or '无数据' in err_msg:
            return "skipped", "停牌/无数据"
        return "failed", err_msg[:80]


def download_all():
    """下载全部数据"""
    stats = load_stats()
    all_items = get_all_assets()
    
    total = len(all_items)
    success = len(stats.get("success", []))
    failed = len(stats.get("failed", []))
    skipped = stats.get("skipped", 0)
    
    print(f"\n📦 开始下载...")
    print(f"   总计: {total} | 已成功: {success} | 已失败: {failed} | 已跳过: {skipped}")
    print("=" * 60)
    
    start_time = time.time()
    last_print_time = start_time
    
    for i, item in enumerate(all_items):
        code = item["code"]
        name = item["name"]
        
        if code in stats.get("success", []):
            continue
        
        status, detail = download_item(item)
        
        if status == "success":
            if "success" not in stats:
                stats["success"] = []
            stats["success"].append(code)
            success += 1
        elif status == "failed":
            if "failed" not in stats:
                stats["failed"] = []
            stats["failed"].append({"code": code, "name": name, "error": detail})
            failed += 1
        else:
            skipped += 1
        
        current_time = time.time()
        if current_time - last_print_time >= 30 or i == total - 1:
            elapsed = current_time - start_time
            rate = (success + failed + skipped) / elapsed if elapsed > 0 else 0
            remaining = total - success - failed - skipped
            eta = remaining / rate / 60 if rate > 0 else 0
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"{success+failed+skipped}/{total}({100*(success+failed+skipped)//total}%) | "
                  f"✅{success} ❌{failed} ⏭️{skipped} | {rate:.1f}只/秒 | 剩{eta:.0f}分")
            last_print_time = current_time
            save_stats(stats)
        
        time.sleep(DOWNLOAD_INTERVAL)
    
    save_stats(stats)
    
    elapsed = time.time() - start_time
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.parquet')]
    total_size = sum(os.path.getsize(os.path.join(DATA_DIR, f)) for f in files)
    
    print("\n" + "=" * 60)
    print(f"📦 下载完成! 耗时: {elapsed/60:.1f}分钟")
    print(f"✅ 成功: {success} | ❌ 失败: {failed} | ⏭️ 跳过: {skipped}")
    print(f"📁 {len(files)} 个文件, {total_size / 1024 / 1024:.2f} MB")
    print("=" * 60)
    
    return stats


def verify_data():
    """数据真实性验证"""
    print("\n" + "=" * 60)
    print("🔍 数据真实性验证")
    print("=" * 60)
    
    stats = load_stats()
    success_codes = stats.get("success", [])
    
    if len(success_codes) < 5:
        print("❌ 数据太少，无法验证")
        return
    
    sample_size = min(5, len(success_codes))
    sample_codes = random.sample(success_codes, sample_size)
    verified = 0
    
    for code in sample_codes:
        parquet_path = os.path.join(DATA_DIR, f"{code}.parquet")
        if not os.path.exists(parquet_path):
            continue
        
        local_df = pd.read_parquet(parquet_path)
        
        try:
            if code.startswith('5') or code.startswith('1'):
                online_df = ak.fund_etf_hist_em(symbol=code, period="daily", 
                        start_date=START_DATE, end_date=END_DATE, adjust="qfq")
            elif code.startswith('0') or code.startswith('3') or code.startswith('8'):
                online_df = ak.stock_zh_a_hist(symbol=code, period="daily",
                        start_date=START_DATE, end_date=END_DATE, adjust="qfq")
            else:
                online_df = ak.index_zh_a_hist(symbol=code, period="daily",
                        start_date=START_DATE, end_date=END_DATE)
            
            if len(local_df) > 0 and len(online_df) > 0:
                local_close = local_df.iloc[-1].get('close', 0)
                online_close = online_df.iloc[-1].get('收盘', online_df.iloc[-1].get('close', 0))
                diff_pct = abs(local_close - online_close) / online_close * 100 if online_close != 0 else 0
                
                if diff_pct < 0.01:
                    print(f"✅ {code}: 通过 | 本地={local_close:.2f} 在线={online_close:.2f}")
                    verified += 1
                else:
                    print(f"⚠️ {code}: 差异{diff_pct:.4f}%")
        except Exception as e:
            print(f"⚠️ {code}: 验证失败 - {str(e)[:30]}")
        
        time.sleep(0.3)
    
    print(f"\n🔍 验证: {verified}/{sample_size} 通过")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "verify":
            verify_data()
        elif sys.argv[1] == "stats":
            stats = load_stats()
            print(f"成功: {len(stats.get('success', []))}")
            print(f"失败: {len(stats.get('failed', []))}")
    else:
        download_all()
        verify_data()
