# -*- coding: utf-8 -*-
"""
量化回测网站 - Streamlit主应用
支持A股 ETF/个股的技术指标回测
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import base64
import io

# 导入自定义模块
from data_fetcher import fetch_data, get_stock_name, fetch_index_data
from strategies import STRATEGY_FUNCTIONS, apply_strategy
from backtest import BacktestEngine
from charts import (
    create_kline_chart, create_equity_curve, 
    create_trade_distribution, create_drawdown_chart,
    create_summary_metrics
)
from utils import format_money, format_percent


# ==================== 页面配置 ====================
st.set_page_config(
    page_title="量化回测系统",
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
    
    .metric-value.positive {
        color: #10B981;
    }
    
    .metric-value.negative {
        color: #EF4444;
    }
    
    /* 标题样式 */
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
    
    /* 侧边栏样式 */
    .css-1d391kg {
        background-color: #1f2937;
    }
    
    /* 成功/错误消息 */
    .success-box {
        background-color: rgba(16, 185, 129, 0.1);
        border: 1px solid #10B981;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    
    .error-box {
        background-color: rgba(239, 68, 68, 0.1);
        border: 1px solid #EF4444;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    
    /* 隐藏元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Plotly图表容器 */
    .js-plotly-plot .plotly, .js-plotly-plot .plotly div {
        background: transparent !important;
    }
</style>
""", unsafe_allow_html=True)


# ==================== 初始化会话状态 ====================
if 'results' not in st.session_state:
    st.session_state.results = None
if 'data' not in st.session_state:
    st.session_state.data = None
if 'name' not in st.session_state:
    st.session_state.name = None


# ==================== 侧边栏 - 参数设置 ====================
with st.sidebar:
    st.markdown("## 📊 量化回测系统")
    st.markdown("---")
    
    # 标的设置
    st.markdown("### 🏢 标的设置")
    stock_type = st.selectbox(
        "标的类型",
        ["个股", "ETF"],
        index=0,
        help="选择回测的标的类型"
    )
    
    symbol = st.text_input(
        "标的代码",
        value="000001",
        help="输入股票代码，如000001（平安银行）、600519（贵州茅台）或ETF代码如515000"
    ).strip()
    
    # 显示标的名称
    if symbol:
        with st.spinner("获取标的信息..."):
            try:
                stock_type_en = "ETF" if stock_type == "ETF" else "stock"
                name = get_stock_name(symbol, stock_type_en)
                st.session_state.name = name
                st.success(f"✅ {name}")
            except Exception as e:
                st.warning(f"⚠️ 无法获取标的信息: {str(e)}")
                st.session_state.name = symbol
    
    st.markdown("---")
    
    # 回测参数
    st.markdown("### 💰 回测参数")
    
    initial_capital = st.number_input(
        "初始资金（元）",
        min_value=10000,
        max_value=100000000,
        value=100000,
        step=10000,
        format="%d",
        help="回测起始资金"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "开始日期",
            value=datetime.now() - timedelta(days=365*5),
            help="回测开始日期"
        )
    with col2:
        end_date = st.date_input(
            "结束日期",
            value=datetime.now(),
            help="回测结束日期"
        )
    
    buy_fee = st.number_input(
        "买入费率（%）",
        min_value=0.0,
        max_value=1.0,
        value=0.025,
        step=0.005,
        format="%.3f",
        help="股票买入手续费率（默认万2.5）"
    ) / 100
    
    sell_fee = st.number_input(
        "卖出手续费（%）",
        min_value=0.0,
        max_value=5.0,
        value=0.1525,
        step=0.005,
        format="%.3f",
        help="包含印花税（默认万2.5+千1印花税）"
    ) / 100
    
    st.markdown("---")
    
    # 基准选择
    st.markdown("### 📈 基准对比")
    benchmark = st.selectbox(
        "对比基准",
        ["000300", "000016", "399006", "000001"],
        format_func=lambda x: {"000300": "沪深300", "000016": "上证50", "399006": "创业板指", "000001": "上证指数"}.get(x, x),
        index=0
    )
    
    benchmark_enabled = st.checkbox("显示基准对比", value=True)
    
    st.markdown("---")
    
    # 策略选择
    st.markdown("### 🎯 策略选择")
    
    strategy_name = st.selectbox(
        "交易策略",
        list(STRATEGY_FUNCTIONS.keys()),
        index=0,
        help="选择技术指标策略"
    )
    
    # 策略参数
    st.markdown("#### ⚙️ 策略参数")
    
    strategy_params = {}
    strategy_info = STRATEGY_FUNCTIONS[strategy_name]
    params_def = strategy_info["params"]
    
    for param_key, param_info in params_def.items():
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
            help=f"{label} (范围: {min_val}-{max_val})"
        )
        strategy_params[param_key] = value
    
    st.markdown("---")
    
    # 止盈止损
    st.markdown("### 🛡️ 风险管理")
    
    stop_loss = st.number_input(
        "止损比例（%）",
        min_value=0.0,
        max_value=50.0,
        value=0.0,
        step=0.5,
        format="%.1f",
        help="达到亏损比例自动止损，0表示不限"
    )
    
    take_profit = st.number_input(
        "止盈比例（%）",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=1.0,
        format="%.1f",
        help="达到盈利比例自动止盈，0表示不限"
    )
    
    max_holding_days = st.number_input(
        "最大持仓天数",
        min_value=0,
        max_value=365,
        value=0,
        step=5,
        format="%d",
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
st.markdown('<div class="main-title">📈 量化回测系统</div>', unsafe_allow_html=True)

# 数据加载和回测执行
if run_backtest:
    if not symbol:
        st.error("⚠️ 请输入标的代码！")
    else:
        with st.spinner("正在获取数据..."):
            try:
                # 格式化日期
                start_str = start_date.strftime("%Y%m%d")
                end_str = end_date.strftime("%Y%m%d")
                
                # 获取标的数据
                stock_type_en = "ETF" if stock_type == "ETF" else "stock"
                df = fetch_data(symbol, start_str, end_str, stock_type_en)
                
                if df is None or len(df) == 0:
                    st.error("❌ 未获取到数据，请检查代码是否正确！")
                else:
                    st.session_state.data = df
                    st.success(f"✅ 成功获取 {len(df)} 条数据")
                    
                    # 获取基准数据
                    benchmark_df = None
                    benchmark_return = None
                    
                    if benchmark_enabled:
                        with st.spinner("正在获取基准数据..."):
                            try:
                                benchmark_df = fetch_index_data(benchmark, start_str, end_str)
                                if benchmark_df is not None and len(benchmark_df) > 0:
                                    benchmark_start = benchmark_df.iloc[0]['close']
                                    benchmark_end = benchmark_df.iloc[-1]['close']
                                    benchmark_return = (benchmark_end - benchmark_start) / benchmark_start * 100
                            except Exception as e:
                                st.warning(f"⚠️ 基准数据获取失败: {str(e)}")
                    
                    # 应用策略
                    with st.spinner("正在应用策略..."):
                        df = apply_strategy(df, strategy_name, **strategy_params)
                    
                    # 运行回测
                    with st.spinner("正在运行回测..."):
                        engine = BacktestEngine(initial_capital, buy_fee, sell_fee)
                        results = engine.run(
                            df, 
                            stop_loss=stop_loss if stop_loss > 0 else 0,
                            take_profit=take_profit if take_profit > 0 else 0,
                            max_holding_days=max_holding_days
                        )
                        
                        # 添加基准收益
                        if benchmark_return is not None:
                            results['基准收益率'] = benchmark_return
                            results['超额收益'] = results['总收益率'] - benchmark_return
                        
                        st.session_state.results = results
                    
                    st.success("✅ 回测完成！")
                    
            except Exception as e:
                st.error(f"❌ 发生错误: {str(e)}")
                import traceback
                st.code(traceback.format_exc())


# ==================== 显示回测结果 ====================
if st.session_state.results is not None:
    results = st.session_state.results
    df = st.session_state.data
    
    # 核心指标展示
    st.markdown("---")
    st.markdown("## 📊 回测结果概览")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_return = results['总收益率']
        color_class = "positive" if total_return >= 0 else "negative"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">总收益率</div>
            <div class="metric-value {color_class}">{format_percent(total_return, False)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        annual_return = results['年化收益率']
        color_class = "positive" if annual_return >= 0 else "negative"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">年化收益率</div>
            <div class="metric-value {color_class}">{format_percent(annual_return, False)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        max_drawdown = results['最大回撤']
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">最大回撤</div>
            <div class="metric-value negative">-{max_drawdown:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        benchmark_return = results.get('基准收益率', 0)
        excess_return = results.get('超额收益', 0)
        color_class = "positive" if excess_return >= 0 else "negative"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">超额收益</div>
            <div class="metric-value {color_class}">{format_percent(excess_return, False)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 第二行指标
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.metric(
            "起始资金",
            format_money(results['起始资金']),
            help="回测初始资金"
        )
    
    with col6:
        final_equity = results['最终资金']
        total_profit = results['总盈亏']
        delta_color = "normal" if total_profit >= 0 else "inverse"
        st.metric(
            "最终资金",
            format_money(final_equity),
            delta=format_money(total_profit),
            delta_color=delta_color,
            help="回测结束时的总资产"
        )
    
    with col7:
        trade_count = results['交易次数']
        st.metric(
            "交易次数",
            f"{trade_count} 次",
            help="总交易次数（买入算一次完整交易）"
        )
    
    with col8:
        win_rate = results['胜率']
        st.metric(
            "胜率",
            f"{win_rate:.1f}%",
            help="盈利交易占比"
        )
    
    # 第三行指标
    col9, col10, col11, col12 = st.columns(4)
    
    with col9:
        profit_loss_ratio = results['盈亏比']
        st.metric(
            "盈亏比",
            f"{profit_loss_ratio:.2f}" if profit_loss_ratio != float('inf') else "∞",
            help="平均盈利/平均亏损"
        )
    
    with col10:
        avg_days = results['平均持仓天数']
        st.metric(
            "平均持仓",
            f"{avg_days:.1f} 天" if avg_days > 0 else "-",
            help="平均持仓天数"
        )
    
    with col11:
        benchmark_return = results.get('基准收益率', 0)
        st.metric(
            "基准收益",
            format_percent(benchmark_return, False),
            help="基准指数收益率"
        )
    
    with col12:
        if benchmark_enabled and '基准收益率' in results:
            excess = results['超额收益']
            delta_color = "normal" if excess >= 0 else "inverse"
            st.metric(
                "超额收益",
                format_percent(excess),
                delta=format_percent(excess),
                delta_color=delta_color,
                help="策略收益 - 基准收益"
            )
    
    st.markdown("---")
    
    # K线图和资金曲线
    col_chart1, col_chart2 = st.columns([2, 1])
    
    with col_chart1:
        st.markdown("### 📈 K线图 + 买卖点")
        
        # 买卖信号
        buy_signals = results.get('买入信号', [])
        sell_signals = results.get('卖出信号', [])
        
        # 创建K线图
        kline_fig = create_kline_chart(
            df, 
            buy_signals=buy_signals,
            sell_signals=sell_signals,
            strategy_name=strategy_name,
            show_ma=True,
            show_macd=True,
            show_rsi=False
        )
        
        st.plotly_chart(kline_fig, use_container_width=True)
    
    with col_chart2:
        st.markdown("### 📉 资金曲线")
        
        benchmark_return_val = results.get('基准收益率', None) if benchmark_enabled else None
        
        equity_fig = create_equity_curve(results, benchmark_return_val)
        st.plotly_chart(equity_fig, use_container_width=True)
        
        # 回撤图
        st.markdown("### 🔻 回撤曲线")
        drawdown_fig = create_drawdown_chart(results.get('每日资产', []))
        st.plotly_chart(drawdown_fig, use_container_width=True)
    
    st.markdown("---")
    
    # 交易分布图
    col_dist1, col_dist2 = st.columns(2)
    
    with col_dist1:
        st.markdown("### 📊 交易盈亏分布")
        dist_fig = create_trade_distribution(results.get('交易记录', []))
        st.plotly_chart(dist_fig, use_container_width=True)
    
    with col_dist2:
        st.markdown("### 📅 月度收益统计")
        monthly_fig = create_monthly_returns_chart(results.get('每日资产', []))
        st.plotly_chart(monthly_fig, use_container_width=True)
    
    st.markdown("---")
    
    # 交易明细表
    st.markdown("### 📋 交易明细")
    
    trades = results.get('交易记录', [])
    
    if trades:
        trades_df = pd.DataFrame(trades)
        
        # 格式化显示
        display_df = trades_df.copy()
        display_df['盈亏金额'] = display_df['盈亏金额'].apply(lambda x: f"{x:.2f}")
        display_df['盈亏比例'] = display_df['盈亏比例'].apply(lambda x: f"{x:.2f}%")
        display_df['买入价格'] = display_df['买入价格'].apply(lambda x: f"{x:.2f}")
        display_df['卖出价格'] = display_df['卖出价格'].apply(lambda x: f"{x:.2f}")
        display_df['买入手续费'] = display_df['买入手续费'].apply(lambda x: f"{x:.2f}")
        display_df['卖出手续费'] = display_df['卖出手续费'].apply(lambda x: f"{x:.2f}")
        
        # 使用Streamlit表格显示
        st.dataframe(
            display_df,
            use_container_width=True,
            height=400,
            hide_index=True
        )
        
        # 导出功能
        col_export1, col_export2 = st.columns(2)
        
        with col_export1:
            # 导出交易明细
            csv = trades_df.to_csv(index=False, encoding='utf-8-sig')
            b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="交易明细_{symbol}_{datetime.now().strftime("%Y%m%d")}.csv">📥 下载交易明细 (CSV)</a>'
            st.markdown(href, unsafe_allow_html=True)
        
        with col_export2:
            # 导出回测报告
            report_data = {
                '指标': ['标的代码', '标的名称', '策略名称', '回测区间', '起始资金', '最终资金', 
                        '总收益率', '年化收益率', '最大回撤', '交易次数', '胜率', '盈亏比',
                        '基准收益率', '超额收益', '平均持仓天数'],
                '值': [
                    symbol,
                    st.session_state.name,
                    strategy_name,
                    f"{start_date} 至 {end_date}",
                    f"{results['起始资金']:.2f}",
                    f"{results['最终资金']:.2f}",
                    f"{results['总收益率']:.2f}%",
                    f"{results['年化收益率']:.2f}%",
                    f"{results['最大回撤']:.2f}%",
                    f"{results['交易次数']}",
                    f"{results['胜率']:.2f}%",
                    f"{results['盈亏比']:.2f}",
                    f"{results.get('基准收益率', 0):.2f}%",
                    f"{results.get('超额收益', 0):.2f}%",
                    f"{results['平均持仓天数']:.1f}"
                ]
            }
            report_df = pd.DataFrame(report_data)
            csv_report = report_df.to_csv(index=False, encoding='utf-8-sig')
            b64_report = base64.b64encode(csv_report.encode('utf-8-sig')).decode()
            href_report = f'<a href="data:file/csv;base64,{b64_report}" download="回测报告_{symbol}_{datetime.now().strftime("%Y%m%d")}.csv">📥 下载回测报告 (CSV)</a>'
            st.markdown(href_report, unsafe_allow_html=True)
    else:
        st.info("📭 本次回测没有完成的交易记录")
    
    st.markdown("---")
    
    # 风险提示
    st.markdown("""
    <div class="success-box">
        <strong>⚠️ 风险提示：</strong><br>
        • 本系统仅供学习和研究之用，不构成任何投资建议<br>
        • 历史业绩不代表未来表现，量化策略存在失效风险<br>
        • 实际交易需考虑滑点、流动性等因素<br>
        • 请在充分理解策略原理后谨慎使用
    </div>
    """, unsafe_allow_html=True)

else:
    # 初始页面
    st.markdown("""
    <div style="text-align: center; padding: 50px 20px; background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border-radius: 16px; margin: 20px 0;">
        <h2 style="color: #F9FAFB; margin-bottom: 20px;">🎯 欢迎使用量化回测系统</h2>
        <p style="color: #9CA3AF; font-size: 16px; line-height: 1.8;">
            在左侧边栏设置回测参数后，点击「开始回测」即可获得完整的回测分析报告
        </p>
        <div style="display: flex; justify-content: center; gap: 40px; margin-top: 40px;">
            <div style="text-align: center;">
                <div style="font-size: 36px; margin-bottom: 10px;">📊</div>
                <div style="color: #F9FAFB;">数据来源</div>
                <div style="color: #9CA3AF; font-size: 14px;">akshare东方财富</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 36px; margin-bottom: 10px;">📈</div>
                <div style="color: #F9FAFB;">技术指标</div>
                <div style="color: #9CA3AF; font-size: 14px;">MA/MACD/RSI/KDJ</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 36px; margin-bottom: 10px;">💹</div>
                <div style="color: #F9FAFB;">回测分析</div>
                <div style="color: #9CA3AF; font-size: 14px;">收益/风险/统计</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 常用标的示例
    st.markdown("### 💡 常用标的代码示例")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **ETF基金**
        - 515000 科技ETF
        - 512000 券商ETF
        - 510300 沪深300ETF
        - 159915 创业板ETF
        """)
    
    with col2:
        st.markdown("""
        **大盘蓝筹**
        - 600519 贵州茅台
        - 000001 平安银行
        - 600036 招商银行
        - 601318 中国平安
        """)
    
    with col3:
        st.markdown("""
        **热门个股**
        - 300750 宁德时代
        - 688981 中芯国际
        - 002475 立讯精密
        - 600276 恒瑞医药
        """)


# ==================== 页脚 ====================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #6B7280; padding: 20px 0;">
    <p>📈 量化回测系统 | 数据支持: akshare (东方财富)</p>
    <p style="font-size: 12px;">本工具仅供学习研究，不构成投资建议</p>
</div>
""", unsafe_allow_html=True)
