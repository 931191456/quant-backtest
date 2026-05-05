# -*- coding: utf-8 -*-
"""
量化回测网站 v2.0 - Streamlit主应用
支持多策略组合、基准对比、报告导出的高性能回测系统
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import base64
import io
import hashlib

# 导入自定义模块
from data_fetcher import (
    fetch_data, get_stock_name, fetch_index_data,
    search_stocks, get_hot_stocks, get_stock_name_cached
)
from strategies import STRATEGIES, apply_single_strategy, apply_multi_strategy
from backtest import BacktestEngine
from charts import (
    create_kline_chart, create_equity_curve, create_drawdown_chart,
    create_trade_distribution, create_summary_metrics,
    export_to_pdf_report, export_chart_to_image
)
from utils import format_money, format_percent, INDEX_MAP


# ==================== 页面配置 ====================
st.set_page_config(
    page_title="量化回测系统 v2.0",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    /* 主背景 */
    .stApp {
        background-color: #0e1117;
    }
    
    /* 指标卡片 */
    .metric-card {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        text-align: center;
    }
    
    .metric-label {
        font-size: 14px;
        color: #9CA3AF;
        margin-bottom: 8px;
    }
    
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #F9FAFB;
    }
    
    .metric-value.positive { color: #10B981; }
    .metric-value.negative { color: #EF4444; }
    
    .main-title {
        font-size: 32px;
        font-weight: bold;
        color: #F9FAFB;
        text-align: center;
        padding: 20px 0;
    }
    
    .section-header {
        font-size: 18px;
        font-weight: bold;
        color: #F9FAFB;
        padding: 15px 0;
        border-bottom: 2px solid #374151;
        margin-bottom: 20px;
    }
    
    /* 股票搜索结果 */
    .stock-item {
        padding: 8px 12px;
        cursor: pointer;
        border-radius: 6px;
        transition: background 0.2s;
    }
    .stock-item:hover {
        background: #374151;
    }
    
    /* 隐藏元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Plotly图表 */
    .js-plotly-plot .plotly, .js-plotly-plot .plotly div {
        background: transparent !important;
    }
    
    /* Streamlit覆盖 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 8px;
    }
    
    /* 加载动画 */
    .loading-spinner {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 2px solid #374151;
        border-radius: 50%;
        border-top-color: #60A5FA;
        animation: spin 1s ease-in-out infinite;
    }
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
</style>
""", unsafe_allow_html=True)


# ==================== 初始化会话状态 ====================
if 'results' not in st.session_state:
    st.session_state.results = None
if 'data' not in st.session_state:
    st.session_state.data = None
if 'benchmark_data' not in st.session_state:
    st.session_state.benchmark_data = None
if 'strategy_params' not in st.session_state:
    st.session_state.strategy_params = {}
if 'search_cache' not in st.session_state:
    st.session_state.search_cache = {}


# ==================== 侧边栏 - 参数设置 ====================
with st.sidebar:
    st.markdown("## 📊 量化回测系统 v2.0")
    st.markdown("---")
    
    # ==================== 标的设置 ====================
    st.markdown("### 🏢 标的设置")
    
    stock_type = st.selectbox(
        "标的类型",
        ["个股", "ETF"],
        index=0,
        help="选择回测的标的类型"
    )
    
    # 热门股票快捷选择
    st.markdown("**快捷选择：**")
    hot_cols = st.columns(3)
    hot_stocks = get_hot_stocks()[:6]
    
    for i, (code, name) in enumerate(hot_stocks[:3]):
        with hot_cols[i]:
            if st.button(f"{code[:3]}...", key=f"hot_{i}", help=f"{code} {name}"):
                st.session_state.selected_symbol = code
                st.session_state.selected_name = name
    
    # 股票搜索输入
    search_key = st.text_input(
        "搜索股票代码/名称",
        value=st.session_state.get('search_input', ''),
        placeholder="输入代码或名称搜索...",
        help="输入股票代码或名称，按回车搜索"
    )
    
    # 搜索防抖
    if search_key and len(search_key) >= 2:
        cache_key = hashlib.md5(f"{search_key}_{stock_type}".encode()).hexdigest()[:8]
        
        if cache_key not in st.session_state.search_cache:
            with st.spinner("搜索中..."):
                results = search_stocks(search_key, "ETF" if stock_type == "ETF" else "stock", limit=5)
                st.session_state.search_cache[cache_key] = results
        else:
            results = st.session_state.search_cache[cache_key]
        
        if results:
            st.markdown("**搜索结果：**")
            for code, name in results:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"`{code}` {name}")
                with col2:
                    if st.button("选择", key=f"sel_{code}"):
                        st.session_state.selected_symbol = code
                        st.session_state.selected_name = name
                        st.session_state.search_input = ''
    
    # 标的代码输入
    symbol = st.text_input(
        "标的代码",
        value=st.session_state.get('selected_symbol', '000001'),
        help="输入股票代码，如000001（平安银行）、600519（贵州茅台）"
    ).strip()
    
    # 显示标的名称（带缓存）
    if symbol:
        with st.spinner(""):
            try:
                stock_type_en = "ETF" if stock_type == "ETF" else "stock"
                name = get_stock_name_cached(symbol, stock_type_en)
                st.success(f"✅ {name}")
            except Exception as e:
                st.warning(f"⚠️ {symbol}")
    
    st.markdown("---")
    
    # ==================== 回测参数 ====================
    st.markdown("### 💰 回测参数")
    
    initial_capital = st.number_input(
        "初始资金（元）",
        min_value=10000,
        max_value=100000000,
        value=100000,
        step=10000,
        format="%d"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=datetime.now() - timedelta(days=365*3))
    with col2:
        end_date = st.date_input("结束日期", value=datetime.now())
    
    col3, col4 = st.columns(2)
    with col3:
        buy_fee = st.number_input("买入费率（%）", min_value=0.0, max_value=1.0, value=0.025, step=0.005, format="%.3f") / 100
    with col4:
        sell_fee = st.number_input("卖出手续费（%）", min_value=0.0, max_value=5.0, value=0.1525, step=0.005, format="%.3f") / 100
    
    st.markdown("---")
    
    # ==================== 策略组合 ====================
    st.markdown("### 🎯 策略组合")
    
    # 策略模式选择
    strategy_mode = st.radio(
        "策略组合模式",
        ["任一满足即可买入", "全部满足才买入"],
        index=0,
        horizontal=True,
        help="任一满足：任一策略发出信号就买入；全部满足：所有策略都发出信号才买入"
    )
    mode = "any" if "任一" in strategy_mode else "all"
    
    # 多策略选择
    available_strategies = list(STRATEGIES.keys())
    selected_strategies = st.multiselect(
        "选择策略（可多选）",
        available_strategies,
        default=["MACD金叉/死叉"],
        help="选择多个策略进行组合"
    )
    
    # 各策略参数
    strategy_params = {}
    for strat_name in selected_strategies:
        strat_info = STRATEGIES[strat_name]
        with st.expander(f"⚙️ {strat_name}参数", expanded=False):
            for param_key, param_info in strat_info["params"].items():
                label = param_info.get("label", param_key)
                default = param_info.get("default", 10)
                min_val = param_info.get("min", 1)
                max_val = param_info.get("max", 100)
                
                value = st.number_input(
                    label,
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
    
    # ==================== 基准对比 ====================
    st.markdown("### 📈 基准对比")
    
    benchmark_option = st.selectbox(
        "选择基准",
        ["无基准", "沪深300", "上证50", "创业板指", "中证500", "上证指数", "自定义"],
        index=0
    )
    
    if benchmark_option == "自定义":
        benchmark_symbol = st.text_input("基准代码", value="000300", help="输入指数或股票代码")
    elif benchmark_option == "无基准":
        benchmark_symbol = None
    else:
        benchmark_symbol = INDEX_MAP.get(benchmark_option, "000300")
    
    st.markdown("---")
    
    # ==================== 风控参数 ====================
    st.markdown("### 🛡️ 风险管理")
    
    stop_loss = st.number_input(
        "止损比例（%）",
        min_value=0.0, max_value=50.0, value=0.0,
        step=0.5, format="%.1f",
        help="达到亏损比例自动止损，0表示不限"
    )
    
    take_profit = st.number_input(
        "止盈比例（%）",
        min_value=0.0, max_value=100.0, value=0.0,
        step=1.0, format="%.1f",
        help="达到盈利比例自动止盈，0表示不限"
    )
    
    max_holding_days = st.number_input(
        "最大持仓天数",
        min_value=0, max_value=365, value=0,
        step=5, format="%d",
        help="持仓超过此天数自动平仓，0表示不限"
    )
    
    st.markdown("---")
    
    # 回测按钮
    run_backtest = st.button(
        "🚀 开始回测",
        type="primary",
        use_container_width=True
    )


# ==================== 主内容区 ====================
st.markdown('<div class="main-title">📈 量化回测系统 v2.0</div>', unsafe_allow_html=True)

# 策略说明
if selected_strategies:
    with st.expander("📖 策略说明", expanded=False):
        for strat in selected_strategies:
            info = STRATEGIES[strat]
            st.markdown(f"**{strat}**：{info['description']}")


# ==================== 回测执行 ====================
if run_backtest:
    if not symbol:
        st.error("⚠️ 请输入标的代码！")
    elif not selected_strategies:
        st.error("⚠️ 请至少选择一个策略！")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 步骤1：获取数据
            status_text.text("📥 正在获取标的数据...")
            progress_bar.progress(10)
            
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
            stock_type_en = "ETF" if stock_type == "ETF" else "stock"
            
            df = fetch_data(symbol, start_str, end_str, stock_type_en)
            
            if df is None or len(df) == 0:
                st.error("❌ 未获取到数据，请检查代码是否正确！")
                st.stop()
            
            progress_bar.progress(30)
            status_text.text(f"✅ 成功获取 {len(df)} 条数据")
            
            # 步骤2：获取基准数据
            benchmark_df = None
            if benchmark_symbol:
                status_text.text("📊 正在获取基准数据...")
                try:
                    benchmark_df = fetch_index_data(benchmark_symbol, start_str, end_str)
                    st.session_state.benchmark_data = benchmark_df
                except Exception as e:
                    st.warning(f"⚠️ 基准数据获取失败: {e}")
            
            progress_bar.progress(50)
            
            # 步骤3：应用策略
            status_text.text("🎯 正在计算策略信号...")
            df = apply_multi_strategy(df, selected_strategies, strategy_params, mode)
            
            progress_bar.progress(70)
            status_text.text("⚙️ 策略计算完成")
            
            # 步骤4：运行回测
            status_text.text("📈 正在运行回测...")
            engine = BacktestEngine(initial_capital, buy_fee, sell_fee)
            results = engine.run(
                df,
                stop_loss=stop_loss if stop_loss > 0 else 0,
                take_profit=take_profit if take_profit > 0 else 0,
                max_holding_days=max_holding_days
            )
            
            # 计算超额收益
            if benchmark_df is not None and len(benchmark_df) > 1:
                strategy_return = results['总收益率']
                benchmark_start = benchmark_df.iloc[0]['close']
                benchmark_end = benchmark_df.iloc[-1]['close']
                benchmark_return = (benchmark_end - benchmark_start) / benchmark_start * 100
                results['基准收益率'] = benchmark_return
                results['超额收益'] = strategy_return - benchmark_return
            
            st.session_state.results = results
            st.session_state.data = df
            
            progress_bar.progress(100)
            status_text.text("✅ 回测完成！")
            st.success(f"✅ 回测完成！共 {len(df)} 个交易日，{results['总交易次数']} 次交易")
            
        except Exception as e:
            st.error(f"❌ 发生错误: {str(e)}")
            import traceback
            with st.expander("错误详情"):
                st.code(traceback.format_exc())


# ==================== 显示回测结果 ====================
if st.session_state.results is not None:
    results = st.session_state.results
    df = st.session_state.data
    
    # 核心指标
    st.markdown("---")
    st.markdown("## 📊 回测结果概览")
    
    # 指标卡片
    st.markdown(create_summary_metrics(results), unsafe_allow_html=True)
    
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
            st.metric("平均盈利", f"¥{results.get('平均盈利', 0):,.2f}")
        with col8:
            st.metric("平均亏损", f"¥{results.get('平均亏损', 0):,.2f}")
    
    # ==================== 图表展示 ====================
    st.markdown("---")
    st.markdown("## 📈 图表分析")
    
    tab1, tab2, tab3, tab4 = st.tabs(["K线图", "资金曲线", "回撤分析", "盈亏分布"])
    
    with tab1:
        # K线图
        kline_fig = create_kline_chart(
            df,
            buy_signals=results.get('买入信号', []),
            sell_signals=results.get('卖出信号', []),
            show_ma=True,
            show_macd=True,
            show_rsi=True
        )
        st.plotly_chart(kline_fig, use_container_width=True)
    
    with tab2:
        # 资金曲线
        equity_df = results.get('每日资产')
        benchmark_df = st.session_state.get('benchmark_data')
        
        if equity_df is not None and len(equity_df) > 0:
            equity_fig = create_equity_curve(equity_df, benchmark_df, initial_capital)
            st.plotly_chart(equity_fig, use_container_width=True)
        else:
            st.info("暂无资金曲线数据")
    
    with tab3:
        # 回撤图
        if equity_df is not None and len(equity_df) > 0:
            dd_fig = create_drawdown_chart(equity_df)
            st.plotly_chart(dd_fig, use_container_width=True)
        else:
            st.info("暂无回撤数据")
    
    with tab4:
        # 盈亏分布
        trades = results.get('交易记录', [])
        if trades:
            dist_fig = create_trade_distribution(trades)
            if dist_fig:
                st.plotly_chart(dist_fig, use_container_width=True)
        else:
            st.info("暂无交易记录")
    
    # ==================== 交易明细 ====================
    st.markdown("---")
    st.markdown("## 📋 交易明细")
    
    if results.get('交易记录'):
        trades_df = pd.DataFrame(results['交易记录'])
        trades_df['盈亏金额'] = trades_df['盈亏金额'].apply(lambda x: f"¥{x:+,.2f}")
        trades_df['盈亏比例'] = trades_df['盈亏比例'].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(trades_df, use_container_width=True, hide_index=True)
        
        # 导出交易记录
        csv = trades_df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="交易记录_{symbol}.csv">📥 下载交易记录CSV</a>'
        st.markdown(href, unsafe_allow_html=True)
    else:
        st.info("暂无交易记录")
    
    # ==================== 导出报告 ====================
    st.markdown("---")
    st.markdown("## 📤 导出报告")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 导出HTML报告
        strategy_list = selected_strategies
        all_params = {}
        for s in strategy_list:
            all_params.update(strategy_params.get(s, {}))
        
        report_html = export_to_pdf_report(results, df, symbol, strategy_list, all_params)
        
        b64_html = base64.b64encode(report_html.encode()).decode()
        href_html = f'<a href="data:file/html;base64,{b64_html}" download="回测报告_{symbol}.html">📄 下载HTML报告</a>'
        st.markdown(href_html, unsafe_allow_html=True)
    
    with col2:
        # 导出K线图
        kline_bytes = export_chart_to_image(kline_fig, "kline")
        b64_img = base64.b64encode(kline_bytes).decode()
        href_img = f'<a href="data:file/png;base64,{b64_img}" download="K线图_{symbol}.png">📊 下载K线图</a>'
        st.markdown(href_img, unsafe_allow_html=True)
    
    with col3:
        st.info("💡 提示：HTML报告可用浏览器打印为PDF")

else:
    # 初始提示
    st.markdown("---")
    st.markdown("""
    ### 🚀 欢迎使用量化回测系统 v2.0
    
    **新功能亮点：**
    - ⚡ **速度优化**：数据缓存+搜索防抖，响应更快
    - 🎯 **多策略组合**：支持RSI、KDJ、MACD等8种策略任意组合
    - 📈 **基准对比**：支持沪深300、创业板指等指数对比
    - 📤 **一键导出**：HTML报告、K线图批量导出
    - 📊 **更多指标**：夏普比率、超额收益详细分析
    
    **使用步骤：**
    1. 在左侧选择标的代码
    2. 选择一个或多个策略
    3. 设置回测参数和风控条件
    4. 点击"开始回测"
    """)


# ==================== 底部信息 ====================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #6B7280; padding: 20px;'>"
    "📈 量化回测系统 v2.0 | 数据来源：东方财富(akshare) | "
    "投资有风险，策略仅供参考"
    "</div>",
    unsafe_allow_html=True
)
