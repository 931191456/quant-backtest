# -*- coding: utf-8 -*-
"""
量化回测网站 v3.2 - Streamlit主应用
性能优化：本地parquet秒开 + 统一搜索 + 更新按钮 + 完善的异常处理
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import traceback
import os

# 导入自定义模块
from data_fetcher import (
    fetch_data, get_stock_name, fetch_index_data,
    search_all, ALL_ITEMS, BUILTIN_STOCKS, BUILTIN_ETFS, BUILTIN_INDICES,
    DataFetchError, DataNotFoundError, DataSuspendedError, DATA_DIR
)
from strategies import STRATEGIES, apply_multi_strategy
from backtest import BacktestEngine
from utils import format_money, format_percent, INDEX_MAP


# ==================== 页面配置 ====================
st.set_page_config(
    page_title="量化回测系统 v3.2",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .metric-card {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        text-align: center;
    }
    .metric-value { font-size: 28px; font-weight: bold; color: #F9FAFB; }
    .metric-value.positive { color: #10B981; }
    .metric-value.negative { color: #EF4444; }
    .main-title { font-size: 32px; font-weight: bold; color: #F9FAFB; text-align: center; padding: 20px 0; }
    .info-box {
        background: #1f2937;
        border-left: 4px solid #3b82f6;
        padding: 15px;
        margin: 10px 0;
        border-radius: 8px;
    }
    .update-box {
        background: linear-gradient(135deg, #064e3b 0%, #065f46 100%);
        border: 1px solid #10b981;
        border-radius: 8px;
        padding: 10px;
        margin: 10px 0;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)


# ==================== 初始化会话状态 ====================
if 'results' not in st.session_state:
    st.session_state.results = None
if 'data' not in st.session_state:
    st.session_state.data = None
if 'selected_code' not in st.session_state:
    st.session_state.selected_code = "000001"
if 'selected_name' not in st.session_state:
    st.session_state.selected_name = "平安银行"
if 'selected_type' not in st.session_state:
    st.session_state.selected_type = "股票"
if 'data_updated' not in st.session_state:
    st.session_state.data_updated = False
if 'update_message' not in st.session_state:
    st.session_state.update_message = None


# ==================== 数据更新函数 ====================
def update_stock_data(code, item_type):
    """在线更新单个标的的数据"""
    import akshare as ak
    
    parquet_path = os.path.join(DATA_DIR, f"{code}.parquet")
    START_DATE = "20240501"
    END_DATE = datetime.now().strftime("%Y%m%d")
    
    try:
        if item_type == "ETF":
            df = ak.fund_etf_hist_em(
                symbol=code, period="daily",
                start_date=START_DATE, end_date=END_DATE, adjust="qfq"
            )
        elif item_type == "指数":
            df = ak.index_zh_a_hist(
                symbol=code, period="daily",
                start_date=START_DATE, end_date=END_DATE
            )
        else:
            df = ak.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date=START_DATE, end_date=END_DATE, adjust="qfq"
            )
        
        # 统一列名
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume',
            '成交额': 'amount', '涨跌幅': 'pct_change',
            '涨跌额': 'change', '换手率': 'turnover'
        })
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        # 保存到本地
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_parquet(parquet_path)
        
        return True, f"✅ 更新成功！最新数据: {df['date'].max().strftime('%Y-%m-%d')}, 共 {len(df)} 条"
        
    except DataNotFoundError:
        return False, f"❌ 未找到 {code}，请检查代码是否正确"
    except DataSuspendedError:
        return False, f"⚠️ {code} 当前停牌或无数据"
    except Exception as e:
        return False, f"❌ 更新失败: {str(e)[:50]}"


# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown("## 📊 量化回测系统 v3.2")
    st.markdown("---")
    
    # ==================== 热门快速入口 ====================
    st.markdown("### ⚡ 快速入口")
    
    hot_items = [
        ("600519", "贵州茅台"),
        ("000858", "五粮液"),
        ("600036", "招商银行"),
        ("601318", "中国平安"),
        ("300750", "宁德时代"),
        ("000001", "平安银行"),
        ("510300", "沪深300ETF"),
        ("159915", "创业板ETF"),
        ("000001", "上证指数"),
    ]
    
    cols = st.columns(3)
    for i, (code, name) in enumerate(hot_items[:9]):
        with cols[i % 3]:
            info = ALL_ITEMS.get(code, {"name": name, "type": "股票"})
            display_name = info.get("name", name)
            item_type = info.get("type", "股票")
            
            if st.button(
                f"{display_name[:4]}", 
                key=f"hot_{code}_{i}",
                help=f"{display_name}({code})"
            ):
                st.session_state.selected_code = code
                st.session_state.selected_name = display_name
                st.session_state.selected_type = item_type
                st.session_state.update_message = None
                st.rerun(scope="fragment")
    
    st.markdown("---")
    
    # ==================== 统一搜索框 ====================
    st.markdown("### 🔍 搜索标的")
    
    search_keyword = st.text_input(
        "输入代码或名称",
        placeholder="如：平安、000001、茅台",
        label_visibility="collapsed",
        key="search_input"
    )
    
    if search_keyword and len(search_keyword) >= 1:
        results = search_all(search_keyword, limit=10)
        if results:
            options = [f"{r['name']}({r['code']}) [{r['type']}]" for r in results]
            selected_option = st.selectbox(
                "选择",
                options,
                label_visibility="collapsed",
                key="search_result_select"
            )
            
            for r in results:
                if f"{r['name']}({r['code']}) [{r['type']}]" == selected_option:
                    st.session_state.selected_code = r['code']
                    st.session_state.selected_name = r['name']
                    st.session_state.selected_type = r['type']
                    st.session_state.update_message = None
                    break
    
    # 显示当前选中
    code = st.session_state.selected_code
    name = st.session_state.selected_name
    item_type = st.session_state.selected_type
    
    # 数据状态检查
    parquet_path = os.path.join(DATA_DIR, f"{code}.parquet")
    has_local = os.path.exists(parquet_path)
    if has_local:
        try:
            local_df = pd.read_parquet(parquet_path)
            last_date = pd.to_datetime(local_df['date']).max().strftime('%Y-%m-%d')
            days_ago = (datetime.now() - pd.to_datetime(local_df['date']).max()).days
            if days_ago == 0:
                date_hint = "📅 今天"
            elif days_ago == 1:
                date_hint = f"📅 昨天({last_date})"
            else:
                date_hint = f"📅 {last_date}({days_ago}天前)"
        except:
            date_hint = "📁 本地数据"
    else:
        date_hint = "🌐 在线获取"
    
    # 数据显示状态
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 14px; color: #10B981;">📌 {name}({code})</span>
        <span style="font-size: 12px; color: #9CA3AF;">{date_hint}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # ==================== 更新数据按钮 ====================
    st.markdown("### 🔄 数据更新")
    
    # 更新提示信息
    if st.session_state.update_message:
        msg = st.session_state.update_message
        if msg.startswith("✅"):
            st.success(msg)
        elif msg.startswith("❌") or msg.startswith("⚠️"):
            st.error(msg)
        else:
            st.info(msg)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        update_clicked = st.button("🔄 更新数据", use_container_width=True, key="update_btn")
    with col2:
        st.caption("获取最新行情")
    
    # 处理更新逻辑
    if update_clicked:
        with st.spinner("正在更新数据..."):
            success, message = update_stock_data(code, item_type)
            st.session_state.update_message = message
            if success:
                st.session_state.data_updated = True
                st.rerun(scope="fragment")
            else:
                st.rerun(scope="fragment")
    
    st.markdown("---")
    
    # ==================== 回测参数 ====================
    st.markdown("### 💰 回测参数")
    
    initial_capital = st.number_input(
        "初始资金（元）",
        min_value=10000, max_value=100000000,
        value=100000, step=10000, format="%d"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始", value=datetime.now() - timedelta(days=365))
    with col2:
        end_date = st.date_input("结束", value=datetime.now())
    
    col3, col4 = st.columns(2)
    with col3:
        buy_fee = st.number_input("买费(%)", min_value=0.0, max_value=1.0, value=0.025, step=0.005, format="%.3f") / 100
    with col4:
        sell_fee = st.number_input("卖费(%)", min_value=0.0, max_value=5.0, value=0.1525, step=0.005, format="%.3f") / 100
    
    st.markdown("---")
    
    # ==================== 策略选择 ====================
    st.markdown("### 🎯 策略")
    
    available_strategies = list(STRATEGIES.keys())
    selected_strategies = st.multiselect(
        "选择策略",
        available_strategies,
        default=["MACD金叉/死叉"],
        label_visibility="collapsed"
    )
    
    strategy_params = {}
    for strat_name in selected_strategies:
        strat_info = STRATEGIES[strat_name]
        with st.expander(f"⚙️ {strat_name}", expanded=False):
            for param_key, param_info in strat_info["params"].items():
                default = param_info.get("default", 10)
                min_val = param_info.get("min", 1)
                max_val = param_info.get("max", 100)
                
                value = st.number_input(
                    param_info.get("label", param_key),
                    min_value=min_val,
                    max_value=max_val,
                    value=int(default) if isinstance(default, int) else default,
                    step=1 if isinstance(default, int) else 0.1,
                    format="%d" if isinstance(default, int) else "%.2f",
                    key=f"param_{strat_name}_{param_key}"
                )
                if strat_name not in strategy_params:
                    strategy_params[strat_name] = {}
                strategy_params[strat_name][param_key] = value
    
    st.markdown("---")
    
    # ==================== 基准和风控 ====================
    st.markdown("### 📈 基准")
    
    benchmark_option = st.selectbox(
        "选择基准",
        ["无基准", "沪深300", "上证50", "创业板指", "中证500"],
        index=0
    )
    
    if benchmark_option == "无基准":
        benchmark_symbol = None
    else:
        benchmark_symbol = INDEX_MAP.get(benchmark_option, "000300")
    
    st.markdown("---")
    st.markdown("### 🛡️ 风控")
    
    col1, col2 = st.columns(2)
    with col1:
        stop_loss = st.number_input("止损(%)", min_value=0.0, max_value=50.0, value=0.0, step=0.5, format="%.1f")
    with col2:
        take_profit = st.number_input("止盈(%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, format="%.1f")
    
    st.markdown("---")
    
    run_backtest = st.button(
        "🚀 开始回测",
        type="primary",
        use_container_width=True,
        key="run_backtest_btn"
    )


# ==================== 主内容区 ====================
st.markdown('<div class="main-title">📈 量化回测系统 v3.2</div>', unsafe_allow_html=True)

# 当前标的信息
code = st.session_state.selected_code
name = st.session_state.selected_name
item_type = st.session_state.selected_type

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("当前标的", name)
with col2:
    st.metric("代码", code)
with col3:
    st.metric("类型", item_type)

# 提示信息
st.info("💡 **使用提示**：热门股票秒开体验！如需最新行情，先点侧边栏「🔄 更新数据」按钮")


# ==================== 回测执行 ====================
if run_backtest:
    if not selected_strategies:
        st.error("⚠️ 请至少选择一个策略！")
    else:
        progress_container = st.container()
        
        with progress_container:
            status_text = st.empty()
            progress_bar = st.progress(0)
        
        try:
            # 步骤1：获取数据
            status_text.text("📥 正在获取数据...")
            progress_bar.progress(10)
            
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
            
            # 确定标的类型
            if item_type == "ETF":
                stock_type_en = "ETF"
            elif item_type == "指数":
                stock_type_en = "指数"
            else:
                stock_type_en = "stock"
            
            # 获取数据
            try:
                df = fetch_data(code, start_str, end_str, stock_type_en)
            except DataNotFoundError as e:
                st.error(f"❌ {e.message}")
                st.stop()
            except DataSuspendedError as e:
                st.error(f"⚠️ {e.message}")
                st.stop()
            except DataFetchError as e:
                st.error(f"❌ 数据获取失败: {e.message}")
                st.stop()
            except Exception as e:
                st.error(f"❌ 数据获取失败: {str(e)}")
                st.stop()
            
            if df is None or len(df) == 0:
                st.error("❌ 未获取到数据！可能原因：股票停牌、代码错误或网络问题")
                st.stop()
            
            progress_bar.progress(30)
            
            # 判断数据来源
            is_local = os.path.exists(os.path.join(DATA_DIR, f"{code}.parquet"))
            source_text = "📁 本地缓存" if is_local else "🌐 在线获取"
            status_text.text(f"✅ 获取 {len(df)} 条数据 ({source_text})")
            
            # 步骤2：获取基准数据
            benchmark_df = None
            if benchmark_symbol:
                status_text.text("📊 获取基准数据...")
                try:
                    benchmark_df = fetch_index_data(benchmark_symbol, start_str, end_str)
                except:
                    st.warning("⚠️ 基准数据获取失败，将不显示超额收益")
                    benchmark_symbol = None
            
            progress_bar.progress(50)
            
            # 步骤3：应用策略
            status_text.text("🎯 计算策略信号...")
            try:
                df = apply_multi_strategy(df, selected_strategies, strategy_params)
            except Exception as e:
                st.error(f"❌ 策略计算失败: {str(e)}")
                st.stop()
            
            progress_bar.progress(70)
            
            # 步骤4：运行回测
            status_text.text("📈 运行回测...")
            try:
                engine = BacktestEngine(initial_capital, buy_fee, sell_fee)
                results = engine.run(
                    df,
                    stop_loss=stop_loss if stop_loss > 0 else 0,
                    take_profit=take_profit if take_profit > 0 else 0,
                    max_holding_days=0
                )
            except Exception as e:
                st.error(f"❌ 回测引擎错误: {str(e)}")
                st.stop()
            
            # 计算超额收益
            if benchmark_df is not None and len(benchmark_df) > 1:
                try:
                    strategy_return = results.get('总收益率', 0)
                    benchmark_start = benchmark_df.iloc[0]['close']
                    benchmark_end = benchmark_df.iloc[-1]['close']
                    benchmark_return = (benchmark_end - benchmark_start) / benchmark_start * 100
                    results['基准收益率'] = benchmark_return
                    results['超额收益'] = strategy_return - benchmark_return
                except:
                    pass
            
            st.session_state.results = results
            st.session_state.data = df
            
            progress_bar.progress(100)
            status_text.text("✅ 回测完成！")
            
            st.success(f"✅ 回测完成！{len(df)} 个交易日，{results.get('总交易次数', 0)} 次交易 ({source_text})")
            
        except Exception as e:
            progress_bar.progress(0)
            st.error(f"❌ 发生错误: {str(e)}")
            with st.expander("错误详情"):
                st.code(traceback.format_exc())


# ==================== 显示回测结果 ====================
if st.session_state.results is not None:
    results = st.session_state.results
    df = st.session_state.data
    
    st.markdown("---")
    st.markdown("## 📊 回测结果")
    
    # 核心指标
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_return = results.get('总收益率', 0)
        color = "positive" if total_return >= 0 else "negative"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">总收益率</div>
            <div class="metric-value {color}">{total_return:+.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        annual_return = results.get('年化收益率', 0)
        color = "positive" if annual_return >= 0 else "negative"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">年化收益率</div>
            <div class="metric-value {color}">{annual_return:+.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        sharpe = results.get('夏普比率', 0)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">夏普比率</div>
            <div class="metric-value">{sharpe:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        max_drawdown = results.get('最大回撤', 0)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">最大回撤</div>
            <div class="metric-value negative">{max_drawdown:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 超额收益
    if '超额收益' in results:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("基准收益率", f"{results.get('基准收益率', 0):+.2f}%")
        with col2:
            color = "normal" if results['超额收益'] >= 0 else "inverse"
            st.metric("超额收益", f"{results['超额收益']:+.2f}%", delta_color=color)
    
    # 详细指标
    with st.expander("📋 详细指标", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("初始资金", f"¥{results['初始资金']:,.0f}")
        with col2:
            st.metric("最终资产", f"¥{results['最终资产']:,.2f}")
        with col3:
            st.metric("利润总额", f"¥{results['利润总额']:+,.2f}")
        with col4:
            st.metric("盈亏比", f"{results.get('盈亏比', 0):.2f}")
        
        col5, col6, col7, col8 = st.columns(4)
        with col5:
            st.metric("盈利次数", results.get('盈利次数', 0))
        with col6:
            st.metric("亏损次数", results.get('亏损次数', 0))
        with col7:
            st.metric("胜率", f"{results.get('胜率', 0)*100:.1f}%")
        with col8:
            st.metric("总交易次数", results.get('总交易次数', 0))
    
    # ==================== 图表展示 ====================
    st.markdown("---")
    st.markdown("## 📈 图表分析")
    
    from charts import create_kline_chart, create_equity_curve, create_drawdown_chart
    
    tab1, tab2, tab3 = st.tabs(["📊 行情+信号", "💰 资金曲线", "📉 回撤分析"])
    
    with tab1:
        try:
            buy_sigs = results.get('买入信号', [])
            sell_sigs = results.get('卖出信号', [])
            chart = create_kline_chart(df, buy_signals=buy_sigs, sell_signals=sell_sigs)
            st.plotly_chart(chart, use_container_width=True)
        except Exception as e:
            st.warning(f"K线图渲染失败: {e}")
    
    with tab2:
        try:
            equity_df = results.get('每日资产', None)
            if equity_df is not None and len(equity_df) > 0:
                equity_chart = create_equity_curve(equity_df, initial_capital=results.get('初始资金', 100000))
                st.plotly_chart(equity_chart, use_container_width=True)
            else:
                st.info("暂无资金曲线数据")
        except Exception as e:
            st.warning(f"资金曲线渲染失败: {e}")
    
    with tab3:
        try:
            equity_df = results.get('每日资产', None)
            if equity_df is not None and len(equity_df) > 0:
                dd_chart = create_drawdown_chart(equity_df)
                st.plotly_chart(dd_chart, use_container_width=True)
            else:
                st.info("暂无回撤数据")
        except Exception as e:
            st.warning(f"回撤图渲染失败: {e}")
    
    # 交易记录
    st.markdown("---")
    with st.expander("📜 交易记录", expanded=False):
        trade_records = results.get('交易记录', [])
        if trade_records and len(trade_records) > 0:
            trades_df = pd.DataFrame(trade_records)
            st.dataframe(trades_df, use_container_width=True)
        else:
            st.info("暂无交易记录")
