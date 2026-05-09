# -*- coding: utf-8 -*-
"""
量化回测网站 v4.4
- 搜索：本地 all_stocks.json（6971条数据），不联网
- K线行情：腾讯API分段拉取（5-7年数据，Streamlit Cloud稳定）+ 东方财富 + akshare fallback
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import traceback
import os

# 导入自定义模块（带详细错误报告）
try:
    from data_fetcher import (
        fetch_data, get_stock_name, fetch_index_data,
        search_all, ALL_ITEMS, BUILTIN_STOCKS, BUILTIN_ETFS, BUILTIN_INDICES,
        DataFetchError, DataNotFoundError, DataSuspendedError, DATA_DIR
    )
except ImportError as e:
    st.error(f"data_fetcher导入失败: {e}")
    st.stop()

try:
    from strategies import STRATEGIES, apply_multi_strategy
except ImportError as e:
    st.error(f"strategies基础导入失败: {e}")
    st.stop()

try:
    from strategies import get_strategy_description
except ImportError:
    get_strategy_description = None

try:
    from backtest import BacktestEngine
except ImportError as e:
    st.error(f"backtest导入失败: {e}")
    st.stop()

try:
    from utils import format_money, format_percent, INDEX_MAP, get_benchmark_options_with_industry, match_industry_etf
except ImportError as e:
    from utils import format_money, format_percent, INDEX_MAP
    get_benchmark_options_with_industry = None
    match_industry_etf = None


# ==================== 页面配置 ====================
st.set_page_config(
    page_title="量化回测系统 v4.4",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS - A股颜色规范
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
    /* A股颜色规范：正收益红色，负收益绿色 */
    .metric-value { font-size: 28px; font-weight: bold; color: #F9FAFB; }
    .metric-value.positive { color: #EF4444; }  /* 正收益红色 */
    .metric-value.negative { color: #10B981; }  /* 负收益绿色 */
    .metric-value.drawdown { color: #10B981; }   /* 回撤用绿色（亏损概念） */
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
    .strategy-card {
        background: #1f2937;
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 15px;
        margin: 8px 0;
    }
    .strategy-name {
        font-size: 16px;
        font-weight: bold;
        color: #60A5FA;
        margin-bottom: 8px;
    }
    .strategy-desc {
        font-size: 13px;
        color: #D1D5DB;
        margin-bottom: 5px;
    }
    .strategy-param {
        font-size: 12px;
        color: #9CA3AF;
        margin: 3px 0;
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
# 不设置默认标的，用户搜索后才会选中
if 'selected_code' not in st.session_state:
    st.session_state.selected_code = None
if 'selected_name' not in st.session_state:
    st.session_state.selected_name = None
if 'selected_type' not in st.session_state:
    st.session_state.selected_type = "股票"
if 'data_updated' not in st.session_state:
    st.session_state.data_updated = False
if 'update_message' not in st.session_state:
    st.session_state.update_message = None


# ==================== 数据更新函数 ====================
def update_stock_data(code, item_type):
    """在线更新单个标的的数据，使用data_fetcher的fetch_data（已有东方财富API fallback）"""
    parquet_path = os.path.join(DATA_DIR, f"{code}.parquet")
    START_DATE = "20240501"
    END_DATE = datetime.now().strftime("%Y%m%d")
    
    try:
        # 确定标的类型
        if item_type == "ETF":
            stock_type_en = "ETF"
        elif item_type == "指数":
            stock_type_en = "指数"
        else:
            stock_type_en = "stock"
        
        # 使用data_fetcher的fetch_data，自动有东方财富API fallback
        df = fetch_data(code, START_DATE, END_DATE, stock_type_en)
        
        if df is None or len(df) == 0:
            return False, f"❌ 未获取到 {code} 的数据"
        
        # 保存到本地
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_parquet(parquet_path)
        
        return True, f"✅ 更新成功！最新数据: {df['date'].max().strftime('%Y-%m-%d')}, 共 {len(df)} 条"
        
    except DataNotFoundError:
        return False, f"❌ 未找到 {code}，请检查代码是否正确"
    except DataSuspendedError:
        return False, f"⚠️ {code} 当前停牌或无数据"
    except DataFetchError as e:
        return False, f"❌ 更新失败: {e.message}"
    except Exception as e:
        return False, f"❌ 更新失败: {str(e)[:50]}"


# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown("## 📊 量化回测系统 v4.4")
    st.markdown("---")
    
    # ==================== 搜索标的（支持中文和代码搜索）====================
    st.markdown("### 🔍 搜索标的")
    
    # 搜索输入框
    search_keyword = st.text_input(
        "输入代码或名称",
        placeholder="输入代码或名称搜索，如：茅台、512690",
        label_visibility="collapsed",
        key="search_input"
    )
    
    # 初始化搜索结果session_state
    if 'search_results' not in st.session_state:
        st.session_state.search_results = []
    
    # 搜索逻辑（当有输入时实时搜索）
    if search_keyword and len(search_keyword) >= 1:
        results = search_all(search_keyword, limit=10)
        st.session_state.search_results = results
    else:
        st.session_state.search_results = []
    
    # 构建选项列表
    all_options = []
    all_options_map = {}
    
    if st.session_state.search_results:
        # 有搜索结果时，只显示搜索结果
        for r in st.session_state.search_results:
            label = f"{r['name']}({r['code']}) [{r['type']}]"
            all_options.append(label)
            all_options_map[label] = r
    else:
        # 无搜索结果时，显示当前选中项或空提示
        _name = st.session_state.get('selected_name')
        _code = st.session_state.get('selected_code')
        _type = st.session_state.get('selected_type', '股票')
        if _name and _code:
            current_label = f"{_name}({_code}) [{_type}]"
            all_options.append(current_label)
            all_options_map[current_label] = {"code": _code, "name": _name, "type": _type}
        else:
            empty_label = "请搜索选择标的..."
            all_options.append(empty_label)
            all_options_map[empty_label] = None
    
    # 选择框（始终显示）
    selected_option = st.selectbox(
        "选择标的",
        options=all_options,
        index=0,
        label_visibility="collapsed",
        key="search_result_select"
    )
    
    # 更新选中的标的
    if selected_option and selected_option in all_options_map:
        selected_info = all_options_map[selected_option]
        if selected_info is not None:
            st.session_state.selected_code = selected_info['code']
            st.session_state.selected_name = selected_info['name']
            st.session_state.selected_type = selected_info['type']
            st.session_state.update_message = None
    
    # 检查是否已选择标的
    code = st.session_state.selected_code
    name = st.session_state.selected_name
    item_type = st.session_state.selected_type
    has_selection = code is not None and name is not None
    
    # 行业ETF匹配（用于基准选择，不在首页显示）
    industry_etf = match_industry_etf(name) if (match_industry_etf and has_selection) else None
    
    # 只有选择了标的才显示以下内容
    if has_selection:
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
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <span style="font-size: 14px; color: #10B981;">📌 {name}({code})</span>
            <span style="font-size: 12px; color: #9CA3AF;">{date_hint}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        # 未选择标的时的提示
        st.info("🔍 请在上方搜索框输入代码或名称，选择标的后即可进行回测")
    
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
        start_date = st.date_input("开始", value=datetime.now() - timedelta(days=365*3), min_value=datetime(2005,1,1))
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
    
    # ==================== 基准选择（带行业ETF）====================
    st.markdown("### 📈 基准")
    
    # 获取基准选项（自动包含行业ETF）
    if get_benchmark_options_with_industry:
        benchmark_options = get_benchmark_options_with_industry(name, code)
    else:
        benchmark_options = [{"label": f"{v} ({k})", "value": k} for k, v in INDEX_MAP.items()]
    benchmark_labels = [opt["label"] for opt in benchmark_options]
    benchmark_values = [opt["value"] for opt in benchmark_options]
    
    # 默认选择（行业ETF优先）
    default_benchmark_idx = 0
    benchmark_option = st.selectbox(
        "选择基准",
        benchmark_labels,
        index=default_benchmark_idx
    )
    
    # 获取选中的基准代码
    selected_idx = benchmark_labels.index(benchmark_option)
    benchmark_symbol = benchmark_values[selected_idx]
    
    st.markdown("---")
    st.markdown("### 🛡️ 风控")
    
    col1, col2 = st.columns(2)
    with col1:
        stop_loss = st.number_input("止损(%)", min_value=0.0, max_value=50.0, value=0.0, step=0.5, format="%.1f")
    with col2:
        take_profit = st.number_input("止盈(%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, format="%.1f")
    
    st.markdown("---")
    
    # ==================== 策略说明 ====================
    st.markdown("### 📖 策略说明")
    
    with st.expander("查看所有策略说明", expanded=False):
        for strat_name in available_strategies:
            strat_info = STRATEGIES[strat_name]
            detail = get_strategy_description(strat_name) if get_strategy_description else strat_info.get('detail', None)
            
            st.markdown(f"""
            <div class="strategy-card">
                <div class="strategy-name">📊 {strat_name}</div>
                <div class="strategy-desc">💡 <b>原理：</b>{detail.get('原理', strat_info.get('description', '暂无说明')) if detail else strat_info.get('description', '暂无说明')}</div>
                <div class="strategy-desc">🎯 <b>适用：</b>{detail.get('适用场景', '通用') if detail else '通用'}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # 参数说明
            if detail and '参数说明' in detail:
                params_html = "<div style='margin-top:8px;'>"
                for pname, pdesc in detail['参数说明'].items():
                    params_html += f"<div class='strategy-param'>• {pname}：{pdesc}</div>"
                params_html += "</div>"
                st.markdown(params_html, unsafe_allow_html=True)
            
            st.markdown("---")
    
    st.markdown("---")
    
    run_backtest = st.button(
        "🚀 开始回测",
        type="primary",
        use_container_width=True,
        key="run_backtest_btn"
    )


# ==================== 主内容区 ====================
st.markdown('<div class="main-title">📈 量化回测系统 v4.4</div>', unsafe_allow_html=True)

# 当前标的信息（只有选择了标的才显示）
code = st.session_state.selected_code
name = st.session_state.selected_name
item_type = st.session_state.selected_type
has_selection = code is not None and name is not None

if has_selection:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("当前标的", name)
    with col2:
        st.metric("代码", code)
    with col3:
        st.metric("类型", item_type)
    
    # 提示信息
    st.info("💡 **使用提示**：热门股票秒开体验！如需最新行情，先点侧边栏「🔄 更新数据」按钮")
else:
    # 未选择标的时显示欢迎提示
    st.info("👋 **欢迎使用量化回测系统**！请在左侧搜索框输入股票代码或名称开始回测")


# ==================== 回测执行 ====================
if run_backtest:
    # 检查是否已选择标的
    if not has_selection:
        st.error("⚠️ 请先搜索并选择标的！")
    elif not selected_strategies:
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
    
    # 核心指标 - A股颜色规范
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_return = results.get('总收益率', 0)
        # A股惯例：正收益红色，负收益绿色
        color_class = "positive" if total_return >= 0 else "negative"
        color_hex = "#EF4444" if total_return >= 0 else "#10B981"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">总收益率</div>
            <div class="metric-value {color_class}" style="color: {color_hex};">{total_return:+.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        annual_return = results.get('年化收益率', 0)
        color_class = "positive" if annual_return >= 0 else "negative"
        color_hex = "#EF4444" if annual_return >= 0 else "#10B981"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">年化收益率</div>
            <div class="metric-value {color_class}" style="color: {color_hex};">{annual_return:+.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        sharpe = results.get('夏普比率', 0)
        # 夏普比率：负数用红色，正数用绿色
        sharpe_color = "#EF4444" if sharpe < 0 else "#10B981"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">夏普比率</div>
            <div class="metric-value" style="color: {sharpe_color};">{sharpe:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        max_drawdown = results.get('最大回撤', 0)
        # 回撤用绿色（亏损概念）
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">最大回撤</div>
            <div class="metric-value drawdown">-{max_drawdown:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 超额收益 - A股颜色规范
    if '超额收益' in results:
        col1, col2 = st.columns(2)
        with col1:
            benchmark_return = results.get('基准收益率', 0)
            bench_color = "#EF4444" if benchmark_return >= 0 else "#10B981"
            st.metric("基准收益率", f"{benchmark_return:+.2f}%", delta_color="off")
            # 用HTML覆盖默认颜色
            st.markdown(f"<div style='text-align:center; color:{bench_color}; font-size:20px; font-weight:bold;'>{benchmark_return:+.2f}%</div>", unsafe_allow_html=True)
        with col2:
            excess_return = results['超额收益']
            excess_color = "#EF4444" if excess_return >= 0 else "#10B981"
            st.metric("超额收益", f"{excess_return:+.2f}%", delta_color="normal" if excess_return >= 0 else "inverse")
    
    # ==================== 最终结果（默认展开）====================
    with st.expander("📋 最终结果", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("初始资金", f"¥{results['初始资金']:,.0f}")
        with col2:
            st.metric("最终资产", f"¥{results['最终资产']:,.2f}")
        with col3:
            st.metric("利润总额", f"¥{results['利润总额']:+,.2f}")
        with col4:
            profit_loss_ratio = results.get('盈亏比', 0)
            # 盈亏比<1用绿色
            pl_color = "normal" if profit_loss_ratio >= 1 else "inverse"
            st.metric("盈亏比", f"{profit_loss_ratio:.2f}", delta_color=pl_color)
        
        col5, col6, col7, col8 = st.columns(4)
        with col5:
            st.metric("盈利次数", results.get('盈利次数', 0))
        with col6:
            st.metric("亏损次数", results.get('亏损次数', 0))
        with col7:
            st.metric("胜率", f"{results.get('胜率', 0):.1f}%")
        with col8:
            st.metric("总交易次数", results.get('总交易次数', 0))
        
        # 交易明细表
        trades = results.get('交易记录', [])
        if trades and len(trades) > 0:
            st.markdown("---")
            st.markdown("#### 📜 交易明细")
            trades_df = pd.DataFrame(trades)
            # 格式化显示
            display_df = trades_df.copy()
            if '买入日期' in display_df.columns:
                display_df['买入日期'] = display_df['买入日期'].astype(str)
            if '卖出日期' in display_df.columns:
                display_df['卖出日期'] = display_df['卖出日期'].astype(str)
            if '买入价格' in display_df.columns:
                display_df['买入价格'] = display_df['买入价格'].apply(lambda x: f"{x:.2f}")
            if '卖出价格' in display_df.columns:
                display_df['卖出价格'] = display_df['卖出价格'].apply(lambda x: f"{x:.2f}")
            if '买入数量' in display_df.columns:
                display_df['买入数量'] = display_df['买入数量'].apply(lambda x: f"{int(x)}")
            if '盈亏金额' in display_df.columns:
                display_df['盈亏金额'] = display_df['盈亏金额'].apply(lambda x: f"{x:+,.2f}")
            if '盈亏比例' in display_df.columns:
                display_df['盈亏比例'] = display_df['盈亏比例'].apply(lambda x: f"{x:+.2f}%")
            if '买入手续费' in display_df.columns:
                display_df['买入手续费'] = display_df['买入手续费'].apply(lambda x: f"{x:.2f}")
            if '卖出手续费' in display_df.columns:
                display_df['卖出手续费'] = display_df['卖出手续费'].apply(lambda x: f"{x:.2f}")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # ==================== 图表展示 ====================
    st.markdown("---")
    st.markdown("## 📈 图表分析")
    
    from charts import create_kline_chart, create_equity_curve, create_drawdown_chart, create_trade_distribution
    
    tab1, tab2, tab3 = st.tabs(["📊 行情+信号", "💰 资金曲线", "📉 回撤分析"])
    
    with tab1:
        try:
            buy_sigs = results.get('买入信号', [])
            sell_sigs = results.get('卖出信号', [])
            chart = create_kline_chart(df, buy_signals=buy_sigs, sell_signals=sell_sigs)
            st.plotly_chart(chart, use_container_width=True)
        except Exception as e:
            st.warning(f"K线图渲染失败: {e}")
            import traceback
            with st.expander("错误详情"):
                st.code(traceback.format_exc())
    
    with tab2:
        try:
            equity_df = results.get('每日资产', None)
            if equity_df is not None and len(equity_df) > 0:
                equity_df_indexed = equity_df.copy()
                equity_df_indexed.index = pd.to_datetime(equity_df_indexed.index)
                
                benchmark_for_chart = None
                if benchmark_df is not None:
                    benchmark_for_chart = benchmark_df
                
                chart = create_equity_curve(equity_df_indexed, benchmark_df=benchmark_for_chart, initial_capital=initial_capital)
                st.plotly_chart(chart, use_container_width=True)
            else:
                st.info("暂无资金曲线数据")
        except Exception as e:
            st.warning(f"资金曲线渲染失败: {e}")
    
    with tab3:
        try:
            if equity_df is not None and len(equity_df) > 0:
                equity_df_indexed = equity_df.copy()
                equity_df_indexed.index = pd.to_datetime(equity_df_indexed.index)
                chart = create_drawdown_chart(equity_df_indexed)
                st.plotly_chart(chart, use_container_width=True)
                
                # 交易分布
                trades = results.get('交易记录', [])
                if trades:
                    dist_chart = create_trade_distribution(trades)
                    if dist_chart:
                        st.plotly_chart(dist_chart, use_container_width=True)
            else:
                st.info("暂无回撤数据")
        except Exception as e:
            st.warning(f"回撤图渲染失败: {e}")
