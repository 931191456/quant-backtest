# -*- coding: utf-8 -*-
"""
数据获取测试脚本
用于验证akshare数据接口是否正常
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import fetch_etf_data, fetch_stock_data, fetch_index_data, get_stock_name


def test_fetch_etf():
    """测试ETF数据获取"""
    print("=" * 50)
    print("测试ETF数据获取")
    print("=" * 50)
    
    try:
        df = fetch_etf_data("515000", "20240101", "20241231")
        print(f"✅ ETF 515000 数据获取成功")
        print(f"   数据条数: {len(df)}")
        print(f"   列名: {list(df.columns)}")
        print(f"   日期范围: {df['date'].min()} 至 {df['date'].max()}")
        print(f"   最新收盘价: {df['close'].iloc[-1]}")
        return True
    except Exception as e:
        print(f"❌ ETF数据获取失败: {e}")
        return False


def test_fetch_stock():
    """测试股票数据获取"""
    print("\n" + "=" * 50)
    print("测试股票数据获取")
    print("=" * 50)
    
    try:
        df = fetch_stock_data("000001", "20240101", "20241231")
        print(f"✅ 股票 000001 数据获取成功")
        print(f"   数据条数: {len(df)}")
        print(f"   列名: {list(df.columns)}")
        print(f"   日期范围: {df['date'].min()} 至 {df['date'].max()}")
        print(f"   最新收盘价: {df['close'].iloc[-1]}")
        return True
    except Exception as e:
        print(f"❌ 股票数据获取失败: {e}")
        return False


def test_fetch_index():
    """测试指数数据获取"""
    print("\n" + "=" * 50)
    print("测试指数数据获取")
    print("=" * 50)
    
    try:
        df = fetch_index_data("000300", "20240101", "20241231")
        print(f"✅ 沪深300指数数据获取成功")
        print(f"   数据条数: {len(df)}")
        print(f"   列名: {list(df.columns)}")
        print(f"   日期范围: {df['date'].min()} 至 {df['date'].max()}")
        print(f"   最新收盘价: {df['close'].iloc[-1]}")
        return True
    except Exception as e:
        print(f"❌ 指数数据获取失败: {e}")
        return False


def test_get_name():
    """测试获取股票名称"""
    print("\n" + "=" * 50)
    print("测试获取股票名称")
    print("=" * 50)
    
    try:
        name = get_stock_name("000001", "stock")
        print(f"✅ 股票名称获取成功: {name}")
        return True
    except Exception as e:
        print(f"❌ 股票名称获取失败: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🧪 量化回测系统 - 数据接口测试")
    print("=" * 60 + "\n")
    
    results = []
    
    results.append(("ETF数据获取", test_fetch_etf()))
    results.append(("股票数据获取", test_fetch_stock()))
    results.append(("指数数据获取", test_fetch_index()))
    results.append(("获取股票名称", test_get_name()))
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "-" * 60)
    if all_passed:
        print("🎉 所有测试通过！数据接口工作正常。")
    else:
        print("⚠️ 部分测试失败，请检查网络连接和数据接口。")
    print("-" * 60)
