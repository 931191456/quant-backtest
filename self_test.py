# -*- coding: utf-8 -*-
"""
量化回测系统自测脚本 v5.0
测试搜索、数据获取、策略计算、回测引擎、图表生成

运行方法: python self_test.py
"""

import sys
import os
from datetime import datetime, timedelta
import traceback

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("量化回测系统 v5.0 自测")
print("=" * 60)

# 测试计数器
tests_passed = 0
tests_failed = 0


def test_result(name, passed, error_msg=None):
    """记录测试结果"""
    global tests_passed, tests_failed
    if passed:
        print(f"✅ {name}")
        tests_passed += 1
    else:
        print(f"❌ {name}: {error_msg}")
        tests_failed += 1


# ==================== 测试1: 搜索功能 ====================
print("\n【测试1: 搜索功能】")

try:
    from data_fetcher import search_all
    
    # 中文名搜索
    results = search_all('寒武纪')
    assert len(results) > 0, "寒武纪搜索为空"
    test_result("中文名搜索(寒武纪)", True)
    
    # 代码精确搜索
    results = search_all('688256')
    assert len(results) > 0, "688256搜索为空"
    assert results[0]['code'] == '688256', "688256代码不匹配"
    test_result("代码精确搜索(688256)", True)
    
    # 茅台搜索
    results = search_all('茅台')
    assert len(results) > 0, "茅台搜索为空"
    test_result("中文名搜索(茅台)", True)
    
    # ETF搜索
    results = search_all('512690')
    assert len(results) > 0, "512690搜索为空"
    test_result("ETF代码搜索(512690)", True)
    
    # 空搜索
    results = search_all('')
    test_result("空字符串搜索", len(results) == 0)
    
except Exception as e:
    test_result("搜索功能导入", False, str(e))
    print(f"   堆栈: {traceback.format_exc()[:200]}")


# ==================== 测试2: 数据获取（6只标的） ====================
print("\n【测试2: 数据获取（6只标的）】")

test_codes = [
    ("688256", "寒武纪", "stock"),    # 科创板
    ("603259", "药明康德", "stock"),   # 上海主板
    ("000858", "五粮液", "stock"),     # 深圳主板
    ("300750", "宁德时代", "stock"),   # 创业板
    ("002594", "比亚迪", "stock"),     # 中小板
    ("512690", "酒ETF", "etf"),        # ETF
]

try:
    from data_fetcher import fetch_data, DataFetchError
    
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
    
    for code, name, stock_type in test_codes:
        try:
            type_en = "ETF" if stock_type == "etf" else "stock"
            df = fetch_data(code, start_date, end_date, type_en)
            
            if df is None or len(df) == 0:
                test_result(f"{name}({code})数据获取", False, "数据为空")
                continue
            
            if 'date' not in df.columns:
                test_result(f"{name}({code})数据获取", False, "缺少date列")
                continue
                
            if 'close' not in df.columns:
                test_result(f"{name}({code})数据获取", False, "缺少close列")
                continue
            
            test_result(f"{name}({code})", True)
            print(f"   → {len(df)}条数据, 日期范围: {df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')}")
            
        except DataFetchError as e:
            test_result(f"{name}({code})数据获取", False, f"获取失败: {e.message}")
        except Exception as e:
            test_result(f"{name}({code})数据获取", False, str(e))
            print(f"   堆栈: {traceback.format_exc()[:200]}")

except ImportError as e:
    test_result("数据获取模块导入", False, str(e))


# ==================== 测试3: 策略计算 ====================
print("\n【测试3: 策略计算】")

try:
    from data_fetcher import fetch_data
    from strategies import STRATEGIES, apply_multi_strategy
    
    # 使用第一只股票测试
    code, name, stock_type = test_codes[0]
    type_en = "ETF" if stock_type == "etf" else "stock"
    df = fetch_data(code, start_date, end_date, type_en)
    
    # 应用MACD策略
    df_with_strategy = apply_multi_strategy(df, ['MACD金叉/死叉'], {})
    
    if 'buy_signal' not in df_with_strategy.columns:
        test_result("策略计算(buy_signal列)", False, "缺少buy_signal列")
    elif 'sell_signal' not in df_with_strategy.columns:
        test_result("策略计算(sell_signal列)", False, "缺少sell_signal列")
    else:
        test_result("策略计算(MACD金叉/死叉)", True)
        buy_count = df_with_strategy['buy_signal'].sum()
        sell_count = df_with_strategy['sell_signal'].sum()
        print(f"   → 买入信号: {buy_count}个, 卖出信号: {sell_count}个")
    
    # 测试多策略组合
    df_multi = apply_multi_strategy(df, ['MACD金叉/死叉', 'KDJ金叉/死叉'], {
        'MACD金叉/死叉': {},
        'KDJ金叉/死叉': {}
    })
    test_result("多策略组合计算", True)
    
except ImportError as e:
    test_result("策略模块导入", False, str(e))
except Exception as e:
    test_result("策略计算", False, str(e))
    print(f"   堆栈: {traceback.format_exc()[:200]}")


# ==================== 测试4: 回测引擎 ====================
print("\n【测试4: 回测引擎】")

try:
    from data_fetcher import fetch_data
    from strategies import apply_multi_strategy
    from backtest import BacktestEngine
    
    # 使用第一只股票测试
    code, name, stock_type = test_codes[0]
    type_en = "ETF" if stock_type == "etf" else "stock"
    df = fetch_data(code, start_date, end_date, type_en)
    df = apply_multi_strategy(df, ['MACD金叉/死叉'], {})
    
    # 运行回测
    engine = BacktestEngine(100000)
    results = engine.run(df)
    
    # 验证结果结构
    required_keys = ['总交易次数', '总收益率', '年化收益率', '最大回撤', '夏普比率']
    missing_keys = [k for k in required_keys if k not in results]
    
    if missing_keys:
        test_result("回测结果结构", False, f"缺少字段: {missing_keys}")
    else:
        test_result("回测引擎运行", True)
        print(f"   → 总交易次数: {results['总交易次数']}")
        print(f"   → 总收益率: {results['总收益率']:.2f}%")
        print(f"   → 年化收益率: {results['年化收益率']:.2f}%")
        print(f"   → 最大回撤: {results['最大回撤']:.2f}%")
        print(f"   → 夏普比率: {results['夏普比率']:.2f}")
    
    # 测试买入信号
    if '买入信号' in results:
        test_result("回测买入信号", True)
        print(f"   → 买入信号数量: {len(results['买入信号'])}")
    
    # 测试卖出信号
    if '卖出信号' in results:
        test_result("回测卖出信号", True)
        print(f"   → 卖出信号数量: {len(results['卖出信号'])}")
    
    # 测试每日资产
    equity_df = results.get('每日资产', None)
    if equity_df is not None and len(equity_df) > 0:
        test_result("每日资产计算", True)
        print(f"   → 资产记录天数: {len(equity_df)}")
    else:
        test_result("每日资产计算", False, "资产数据为空")

except ImportError as e:
    test_result("回测模块导入", False, str(e))
except Exception as e:
    test_result("回测引擎", False, str(e))
    print(f"   堆栈: {traceback.format_exc()[:200]}")


# ==================== 测试5: 图表生成 ====================
print("\n【测试5: 图表生成】")

try:
    from data_fetcher import fetch_data
    from strategies import apply_multi_strategy
    from backtest import BacktestEngine
    from charts import create_kline_chart, create_equity_curve, create_drawdown_chart
    
    # 使用第一只股票测试
    code, name, stock_type = test_codes[0]
    type_en = "ETF" if stock_type == "etf" else "stock"
    df = fetch_data(code, start_date, end_date, type_en)
    df = apply_multi_strategy(df, ['MACD金叉/死叉'], {})
    
    engine = BacktestEngine(100000)
    results = engine.run(df)
    
    buy_signals = results.get('买入信号', [])
    sell_signals = results.get('卖出信号', [])
    
    # 测试K线图
    try:
        chart = create_kline_chart(df, buy_signals=buy_signals, sell_signals=sell_signals)
        test_result("K线图生成", True)
    except Exception as e:
        test_result("K线图生成", False, str(e))
    
    # 测试资金曲线图
    equity_df = results.get('每日资产', None)
    if equity_df is not None and len(equity_df) > 0:
        try:
            eq_chart = create_equity_curve(equity_df)
            test_result("资金曲线图生成", True)
        except Exception as e:
            test_result("资金曲线图生成", False, str(e))
        
        # 测试回撤图
        try:
            dd_chart = create_drawdown_chart(equity_df)
            test_result("回撤图生成", True)
        except Exception as e:
            test_result("回撤图生成", False, str(e))
    else:
        test_result("资金曲线图生成", False, "无资产数据")
        test_result("回撤图生成", False, "无资产数据")

except ImportError as e:
    test_result("图表模块导入", False, str(e))
except Exception as e:
    test_result("图表生成", False, str(e))
    print(f"   堆栈: {traceback.format_exc()[:200]}")


# ==================== 测试6: 全流程测试（随机抽取测试） ====================
print("\n【测试6: 全流程测试（6只标的完整回测）】")

try:
    from data_fetcher import fetch_data
    from strategies import apply_multi_strategy
    from backtest import BacktestEngine
    from charts import create_kline_chart
    
    for code, name, stock_type in test_codes:
        try:
            type_en = "ETF" if stock_type == "etf" else "stock"
            
            # 获取数据
            df = fetch_data(code, start_date, end_date, type_en)
            
            # 应用策略
            df = apply_multi_strategy(df, ['MACD金叉/死叉'], {})
            
            # 回测
            engine = BacktestEngine(100000)
            results = engine.run(df)
            
            # 生成图表
            buy_signals = results.get('买入信号', [])
            sell_signals = results.get('卖出信号', [])
            chart = create_kline_chart(df, buy_signals=buy_signals, sell_signals=sell_signals)
            
            print(f"✅ {name}({code}) 全流程完成")
            print(f"   → 数据: {len(df)}条, 交易: {results['总交易次数']}次, 收益率: {results['总收益率']:.2f}%")
            
        except Exception as e:
            print(f"❌ {name}({code}) 全流程失败: {e}")
            print(f"   堆栈: {traceback.format_exc()[:200]}")

except ImportError as e:
    print(f"全流程测试模块导入失败: {e}")


# ==================== 测试结果汇总 ====================
print("\n" + "=" * 60)
print("测试结果汇总")
print("=" * 60)
print(f"通过: {tests_passed}")
print(f"失败: {tests_failed}")
print(f"总计: {tests_passed + tests_failed}")

if tests_failed == 0:
    print("\n🎉 全部测试通过！系统可以正常交付。")
    sys.exit(0)
else:
    print(f"\n⚠️  有 {tests_failed} 项测试失败，请修复后重新测试。")
    sys.exit(1)
