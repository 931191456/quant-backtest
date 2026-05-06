# -*- coding: utf-8 -*-
"""
图表生成模块 v2.0
支持导出PDF和图片
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import io
import base64


def create_kline_chart(df, buy_signals=None, sell_signals=None, 
                       show_ma=True, show_macd=True, show_rsi=True):
    """创建K线图（带买卖点和技术指标）"""
    # 计算子图数量和配置
    # row号必须从1开始连续递增
    row_configs = []
    
    # 第1个子图：K线（固定）
    row_configs.append((1, 1, 0.5))  # row=1
    
    # 第2个子图：MACD（可选）
    if show_macd:
        row_configs.append((2, 1, 0.2))  # row=2
    
    # 第3个子图：RSI（可选）
    if show_rsi:
        # RSI的row号取决于MACD是否存在
        if show_macd:
            row_configs.append((3, 1, 0.2))  # row=3
        else:
            row_configs.append((2, 1, 0.25))  # row=2
    
    # 子图数量
    total_rows = len(row_configs)
    
    fig = make_subplots(
        rows=total_rows, cols=1,
        row_heights=[rc[2] for rc in row_configs],
        vertical_spacing=0.05,
        shared_xaxes=True
    )
    
    # ==================== K线图（固定在row=1）====================
    row, col, _ = row_configs[0]
    fig.add_trace(
        go.Candlestick(
            x=df['date'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='K线',
            increasing_line_color='#ef5350',
            decreasing_line_color='#26a69a'
        ),
        row=row, col=col
    )
    
    # 均线
    if show_ma:
        for ma_period, color in [(5, '#FF69B4'), (10, '#FFD700'), (20, '#00CED1'), (60, '#9370DB')]:
            ma_col = f'ma{ma_period}'
            if ma_col in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df['date'], y=df[ma_col],
                        mode='lines', name=f'MA{ma_period}',
                        line=dict(width=1.5, color=color)
                    ),
                    row=row, col=col
                )
    
    # 布林带
    if 'bb_upper' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['date'], y=df['bb_upper'],
                mode='lines', name='布林上轨',
                line=dict(color='rgba(156,39,176,0.5)', width=1),
                showlegend=True
            ),
            row=row, col=col
        )
        fig.add_trace(
            go.Scatter(
                x=df['date'], y=df['bb_lower'],
                mode='lines', name='布林下轨',
                line=dict(color='rgba(156,39,176,0.5)', width=1),
                fill='tonexty', fillcolor='rgba(156,39,176,0.1)'
            ),
            row=row, col=col
        )
    
    # 买入信号
    if buy_signals and len(buy_signals) > 0:
        buy_dates = [s['date'] for s in buy_signals]
        buy_prices = [s['price'] for s in buy_signals]
        fig.add_trace(
            go.Scatter(
                x=buy_dates, y=buy_prices,
                mode='markers', name='买入',
                marker=dict(symbol='triangle-up', size=15, color='#EF4444', line=dict(width=1, color='darkred'))
            ),
            row=row, col=col
        )
    
    # 卖出信号
    if sell_signals and len(sell_signals) > 0:
        sell_dates = [s['date'] for s in sell_signals]
        sell_prices = [s['price'] for s in sell_signals]
        fig.add_trace(
            go.Scatter(
                x=sell_dates, y=sell_prices,
                mode='markers', name='卖出',
                marker=dict(symbol='triangle-down', size=15, color='#10B981', line=dict(width=1, color='darkgreen'))
            ),
            row=row, col=col
        )
    
    # ==================== MACD（固定在row=2）====================
    if show_macd and 'macd' in df.columns:
        row, col, _ = row_configs[1]
        
        colors = ['#EF4444' if val >= 0 else '#10B981' for val in df['macd_hist'].fillna(0)]
        fig.add_trace(
            go.Bar(x=df['date'], y=df['macd_hist'].fillna(0), name='MACD柱', marker_color=colors),
            row=row, col=col
        )
        fig.add_trace(
            go.Scatter(x=df['date'], y=df['macd'], mode='lines', name='DIF', line=dict(color='blue', width=1)),
            row=row, col=col
        )
        fig.add_trace(
            go.Scatter(x=df['date'], y=df['macd_signal'], mode='lines', name='DEA', line=dict(color='orange', width=1)),
            row=row, col=col
        )
    
    # ==================== RSI（最后一个子图）====================
    if show_rsi and 'rsi' in df.columns:
        row, col, _ = row_configs[-1]  # RSI总是最后一个
        fig.add_trace(
            go.Scatter(x=df['date'], y=df['rsi'], mode='lines', name='RSI', line=dict(color='purple', width=1.5)),
            row=row, col=col
        )
        # 超买超卖线
        fig.add_hline(y=70, line_dash="dash", line_color="#EF4444", opacity=0.5, row=row, col=col)
        fig.add_hline(y=30, line_dash="dash", line_color="#10B981", opacity=0.5, row=row, col=col)
    
    # 布局设置
    fig.update_layout(
        template='plotly_dark',
        height=600,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_rangeslider_visible=False,
        hovermode='x unified'
    )
    
    return fig


def create_equity_curve(equity_df, benchmark_df=None, initial_capital=100000):
    """创建资金曲线图"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 策略资金曲线
    fig.add_trace(
        go.Scatter(
            x=equity_df.index,
            y=equity_df['equity'],
            mode='lines',
            name='策略资产',
            line=dict(color='#00CED1', width=2)
        ),
        secondary_y=False
    )
    
    # 买入持有基准
    if len(equity_df) > 0:
        buy_hold = equity_df['equity'].iloc[0] / initial_capital * equity_df['equity']
    
    if benchmark_df is not None and len(benchmark_df) > 0:
        # 归一化基准
        benchmark_normalized = benchmark_df['close'] / benchmark_df['close'].iloc[0] * initial_capital
        
        fig.add_trace(
            go.Scatter(
                x=benchmark_df['date'],
                y=benchmark_normalized,
                mode='lines',
                name='基准',
                line=dict(color='gray', width=1.5, dash='dash')
            ),
            secondary_y=False
        )
    
    fig.update_layout(
        template='plotly_dark',
        height=400,
        showlegend=True,
        hovermode='x unified'
    )
    fig.update_yaxes(title_text="资产价值（元）", secondary_y=False)
    
    return fig


def create_drawdown_chart(equity_df):
    """创建回撤图"""
    peak = equity_df['equity'].expanding(min_periods=1).max()
    drawdown = (equity_df['equity'] - peak) / peak * 100
    
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=equity_df.index,
            y=drawdown,
            mode='lines',
            name='回撤',
            fill='tozeroy',
            line=dict(color='#EF4444', width=1)
        )
    )
    
    fig.update_layout(
        template='plotly_dark',
        height=250,
        showlegend=True,
        hovermode='x unified'
    )
    fig.update_yaxes(title_text="回撤（%）")
    
    return fig


def create_trade_distribution(trades):
    """创建交易盈亏分布图"""
    if not trades:
        return None
    
    profits = [t['盈亏比例'] for t in trades]
    
    fig = go.Figure()
    # A股惯例：涨=red，跌=green
    colors = ['#EF4444' if p > 0 else '#10B981' for p in profits]
    
    fig.add_trace(go.Bar(
        x=list(range(1, len(profits) + 1)),
        y=profits,
        marker_color=colors,
        name='盈亏'
    ))
    
    fig.update_layout(
        template='plotly_dark',
        height=300,
        showlegend=False,
        xaxis_title="交易次数",
        yaxis_title="盈亏比例（%）"
    )
    
    return fig


def create_summary_metrics(results):
    """创建关键指标卡片HTML"""
    total_return = results.get('总收益率', 0)
    annual_return = results.get('年化收益率', 0)
    max_drawdown = results.get('最大回撤', 0)
    sharpe = results.get('夏普比率', 0)
    win_rate = results.get('胜率', 0)
    total_trades = results.get('总交易次数', 0)
    
    # A股颜色规范：正收益红色，负收益绿色
    return_color = '#EF4444' if total_return >= 0 else '#10B981'
    annual_color = '#EF4444' if annual_return >= 0 else '#10B981'
    sharpe_color = '#EF4444' if sharpe < 0 else '#10B981'  # 夏普负数用红色
    
    html = f"""
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0;">
        <div style="background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border: 1px solid #374151; border-radius: 12px; padding: 20px; text-align: center;">
            <div style="font-size: 14px; color: #9CA3AF; margin-bottom: 8px;">总收益率</div>
            <div style="font-size: 28px; font-weight: bold; color: {return_color};">{total_return:+.2f}%</div>
        </div>
        <div style="background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border: 1px solid #374151; border-radius: 12px; padding: 20px; text-align: center;">
            <div style="font-size: 14px; color: #9CA3AF; margin-bottom: 8px;">年化收益率</div>
            <div style="font-size: 28px; font-weight: bold; color: {annual_color};">{annual_return:+.2f}%</div>
        </div>
        <div style="background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border: 1px solid #374151; border-radius: 12px; padding: 20px; text-align: center;">
            <div style="font-size: 14px; color: #9CA3AF; margin-bottom: 8px;">最大回撤</div>
            <div style="font-size: 28px; font-weight: bold; color: #10B981;">-{max_drawdown:.2f}%</div>
        </div>
        <div style="background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border: 1px solid #374151; border-radius: 12px; padding: 20px; text-align: center;">
            <div style="font-size: 14px; color: #9CA3AF; margin-bottom: 8px;">夏普比率</div>
            <div style="font-size: 28px; font-weight: bold; color: {sharpe_color};">{sharpe:.2f}</div>
        </div>
        <div style="background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border: 1px solid #374151; border-radius: 12px; padding: 20px; text-align: center;">
            <div style="font-size: 14px; color: #9CA3AF; margin-bottom: 8px;">胜率</div>
            <div style="font-size: 28px; font-weight: bold; color: #60A5FA;">{win_rate:.1f}%</div>
        </div>
        <div style="background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border: 1px solid #374151; border-radius: 12px; padding: 20px; text-align: center;">
            <div style="font-size: 14px; color: #9CA3AF; margin-bottom: 8px;">交易次数</div>
            <div style="font-size: 28px; font-weight: bold; color: #FCD34D;">{total_trades}</div>
        </div>
    </div>
    """
    return html


def export_chart_to_image(fig, filename):
    """导出图表为图片"""
    img_bytes = pio.to_image(fig, format='png', width=1200, height=800)
    b64 = base64.b64encode(img_bytes).decode()
    return f"data:image/png;base64,{b64}"
