# -*- coding: utf-8 -*-
"""
量化回测网站全面测试脚本 v4.x
测试各种类型标的的数据获取
"""

import sys
sys.path.insert(0, '/app/data/所有对话/主对话/量化回测网站')

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import time

# 测试标的列表
TEST_SYMBOLS = [
    # 主板大盘股
    {"code": "600519", "name": "贵州茅台", "type": "stock"},
    {"code": "601318", "name": "中国平安", "type": "stock"},
    {"code": "600036", "name": "招商银行", "type": "stock"},
    {"code": "601888", "name": "中国中免", "type": "stock"},
    # 中小板
    {"code": "002714", "name": "牧原股份", "type": "stock"},
    {"code": "002594", "name": "比亚迪", "type": "stock"},
    # 创业板
    {"code": "300015", "name": "爱尔眼科", "type": "stock"},
    {"code": "300750", "name": "宁德时代", "type": "stock"},
    {"code": "300059", "name": "东方财富", "type": "stock"},
    # 科创板
    {"code": "688981", "name": "中芯国际", "type": "stock"},
    {"code": "301267", "name": "华纬科技", "type": "stock"},
    # 沪深ETF
    {"code": "510300", "name": "沪深300ETF", "type": "ETF"},
    {"code": "159992", "name": "创新药ETF银华", "type": "ETF"},
    {"code": "512690", "name": "白酒ETF", "type": "ETF"},
    {"code": "515000", "name": "科技ETF", "type": "ETF"},
    # ST股
    {"code": "ST曙光", "name": "ST曙光", "type": "stock"},
    # 北交所
    {"code": "430047", "name": "百济神州", "type": "stock"},
]

# 腾讯API配置
TENCENT_API = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
TIMEOUT = 15

def get_prefix(code, stock_type="stock"):
    """根据代码判断腾讯API需要的前缀"""
    code = code.zfill(6)
    
    if stock_type == "ETF":
        if code.startswith("51") or code.startswith("50"):
            return "sh"
        elif code.startswith("15") or code.startswith("16") or code.startswith("13"):
            return "sz"
        else:
            return "sh"
    
    if code.startswith("688"):
        return "sh"
    elif code.startswith("6"):
        return "sh"
    elif code.startswith("000") or code.startswith("001"):
        return "sz"
    elif code.startswith("002") or code.startswith("003"):
        return "sz"
    elif code.startswith("300"):
        return "sz"
    elif code.startswith("8") or code.startswith("4"):
        return "bj"
    else:
        return "sh"

def fetch_tencent_single(code, start_date, end_date, stock_type="stock", limit=800):
    """从腾讯API单次获取数据"""
    prefix = get_prefix(code, stock_type)
    start_str = str(start_date).replace('-', '')
    end_str = str(end_date).replace('-', '')
    
    url = f"{TENCENT_API}?_var=kline_dayqfq&param={prefix}{code},day,{start_str},{end_str},{limit},qfq"
    
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        text = resp.text
        
        if not text or '=' not in text:
            return None, "返回数据异常"
        
        json_str = text[text.index('=') + 1:]
        data = json.loads(json_str)
        
        key = f"{prefix}{code}"
        if key not in data.get('data', {}):
            return None, f"未找到{key}"
        
        if stock_type == "ETF":
            if 'day' in data['data'][key]:
                day_data = data['data'][key]['day']
            else:
                return None, "ETF无day数据"
        else:
            if 'qfqday' in data['data'][key]:
                day_data = data['data'][key]['qfqday']
            else:
                return None, "股票无qfqday数据"
        
        df = pd.DataFrame(day_data, columns=['date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'unused'])
        df = df[['date', 'open', 'close', 'high', 'low', 'volume']]
        df['date'] = pd.to_datetime(df['date'])
        for col in ['open', 'close', 'high', 'low', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()
        df = df.sort_values('date').reset_index(drop=True)
        
        return df, "成功"
        
    except Exception as e:
        return None, str(e)

def fetch_tencent_multi_chunks(code, start_date, end_date, stock_type="stock", chunk_size=800):
    """分块获取腾讯API数据并拼接（测试用）"""
    prefix = get_prefix(code, stock_type)
    
    # 处理start_date - 支持datetime对象或字符串
    if isinstance(start_date, datetime):
        start_dt = start_date
    else:
        start_str_clean = str(start_date).replace('-', '').split()[0]  # 去掉时间部分
        start_dt = datetime.strptime(start_str_clean, '%Y%m%d')
    
    if isinstance(end_date, datetime):
        end_dt = end_date
    else:
        end_str_clean = str(end_date).replace('-', '').split()[0]
        end_dt = datetime.strptime(end_str_clean, '%Y%m%d')
    
    all_dfs = []
    current_start = start_dt
    
    max_chunks = 10  # 最多10次请求
    chunks_tested = 0
    
    while current_start < end_dt and chunks_tested < max_chunks:
        chunks_tested += 1
        start_str = current_start.strftime('%Y%m%d')
        end_str = end_dt.strftime('%Y%m%d')
        
        df, msg = fetch_tencent_single(code, start_str, end_str, stock_type, chunk_size)
        
        if df is None or len(df) == 0:
            break
        
        all_dfs.append(df)
        
        # 更新下一次查询的开始日期（从最后一条数据的下一天开始）
        last_date = df['date'].max()
        current_start = last_date + timedelta(days=1)
        
        # 如果获取的数据少于请求的limit，说明已经到头了
        if len(df) < chunk_size:
            break
        
        time.sleep(0.3)  # 避免请求太快
    
    if not all_dfs:
        return None, "未获取到任何数据"
    
    # 合并所有数据块
    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.drop_duplicates(subset=['date'], keep='last')
    combined = combined.sort_values('date').reset_index(drop=True)
    
    return combined, f"分{chunks_tested}块获取"

def test_symbol(code, name, stock_type, years=7):
    """测试单个标的"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    
    results = {
        "code": code,
        "name": name,
        "type": stock_type,
        "test_years": years,
        "prefix": get_prefix(code, stock_type),
        "status": "未知",
        "total_records": 0,
        "start_date": None,
        "end_date": None,
        "days_covered": 0,
        "error": None,
        "data_quality": "未验证",
    }
    
    # 测试1: 单次获取（当前代码的行为，320条）
    df_single, msg = fetch_tencent_single(code, start_date, end_date, stock_type, 320)
    
    # 测试2: 分块获取（测试能获取多少年）
    df_multi, msg_multi = fetch_tencent_multi_chunks(code, start_date, end_date, stock_type, 800)
    
    if df_multi is not None and len(df_multi) > 0:
        results["total_records"] = len(df_multi)
        results["start_date"] = df_multi['date'].min().strftime('%Y-%m-%d')
        results["end_date"] = df_multi['date'].max().strftime('%Y-%m-%d')
        
        # 计算覆盖天数
        days = (df_multi['date'].max() - df_multi['date'].min()).days
        results["days_covered"] = days
        results["years_covered"] = round(days / 365, 1)
        
        # 数据质量检查
        if len(df_multi) > 1000:
            results["data_quality"] = "✅ 优秀（5年+）"
            results["status"] = "通过"
        elif len(df_multi) > 500:
            results["data_quality"] = "✅ 良好（2-5年）"
            results["status"] = "通过"
        elif len(df_multi) > 200:
            results["data_quality"] = "⚠️ 一般（1-2年）"
            results["status"] = "部分通过"
        else:
            results["data_quality"] = "❌ 不足（<1年）"
            results["status"] = "失败"
        
        # 数据真实性检查
        latest = df_multi.iloc[-1]
        if latest['close'] > 0 and latest['volume'] >= 0:
            results["data_quality"] += " | 数据真实"
        else:
            results["data_quality"] += " | ⚠️ 数据可疑"
            results["status"] = "数据可疑"
    else:
        results["error"] = msg_multi
        results["status"] = "失败"
    
    results["single_fetch_records"] = len(df_single) if df_single is not None else 0
    results["multi_fetch_info"] = msg_multi
    
    return results

def main():
    print("=" * 80)
    print("量化回测网站全面测试 - 数据获取能力验证")
    print("=" * 80)
    print()
    
    all_results = []
    
    for item in TEST_SYMBOLS:
        print(f"\n测试: {item['name']}({item['code']}) [{item['type']}]...")
        result = test_symbol(item['code'], item['name'], item['type'], years=7)
        all_results.append(result)
        
        print(f"  前缀: {result['prefix']}")
        print(f"  单次获取(320条): {result['single_fetch_records']}条")
        print(f"  分块获取: {result['multi_fetch_info']}")
        print(f"  总记录数: {result['total_records']}条")
        print(f"  日期范围: {result['start_date']} ~ {result['end_date']}")
        print(f"  覆盖天数: {result['days_covered']}天 ({result.get('years_covered', 0)}年)")
        print(f"  数据质量: {result['data_quality']}")
        print(f"  状态: {result['status']}")
        
        if result['error']:
            print(f"  错误: {result['error']}")
        
        time.sleep(0.5)  # 避免请求太快
    
    # 汇总统计
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)
    
    passed = [r for r in all_results if r['status'] == '通过']
    partial = [r for r in all_results if r['status'] == '部分通过']
    failed = [r for r in all_results if r['status'] == '失败']
    
    print(f"\n总计: {len(all_results)}个标的")
    print(f"  ✅ 通过: {len(passed)}个")
    print(f"  ⚠️ 部分通过: {len(partial)}个")
    print(f"  ❌ 失败: {len(failed)}个")
    
    print("\n失败标的:")
    for r in failed:
        print(f"  - {r['name']}({r['code']}): {r['error']}")
    
    print("\n部分通过标的（数据不足5年）:")
    for r in partial:
        print(f"  - {r['name']}({r['code']}): {r['total_records']}条 ({r.get('years_covered', 0)}年)")
    
    # 检查关键问题
    print("\n" + "=" * 80)
    print("关键问题检查")
    print("=" * 80)
    
    single_fetch_issues = [r for r in all_results if r['single_fetch_records'] < 500]
    if single_fetch_issues:
        print(f"\n⚠️ 单次获取(320条)数据不足的标的: {len(single_fetch_issues)}个")
        print("   这意味着当前代码只能获取约1-2年数据，不够5年回测需求")
    
    prefix_issues = []
    for r in all_results:
        expected_prefix = get_prefix(r['code'], r['type'])
        if r['prefix'] != expected_prefix:
            prefix_issues.append(f"{r['name']}({r['code']}): 实际{r['prefix']} vs 预期{expected_prefix}")
    
    if prefix_issues:
        print(f"\n⚠️ 前缀判断问题:")
        for issue in prefix_issues:
            print(f"   {issue}")
    else:
        print("\n✅ 前缀判断全部正确")
    
    # 返回结果用于生成报告
    return all_results

if __name__ == "__main__":
    results = main()
