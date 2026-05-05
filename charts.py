# -*- coding: utf-8 -*-
"""
图表生成模块
使用Plotly生成交互式K线图、资金曲线等
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_kline_chart(df, buy_signals=None, sell_signals=None, strategy_name="", show_ma=True, show_macd=False, show_rsi=False):
    """
    创建K线图（带买卖点）
    
    Parameters:
    -----------
    df : pd.DataFrame
        K线数据
    buy_signals : list
        买入信号列表
    sell_signals : list
        卖出信号列表
    strategy_name : str
        策略名称
    show_ma : bool
        是否显示均线
    show_macd : bool
        是否显示MACD
    show_rsi : bool
        是否显示RSI
    
    Returns:
    --------
    plotly.graph_objects.Figure
    """
    # 确定子图数量
    subplot_count = 2 if show_macd or show_rsi else 1
    if show_macd and show_rsi:
        subplot_count = 3
    
    # 创建子图
    if subplot_count == 1:
        fig = make_subplots(rows=1, cols=1)
        row_configs = [(1, 1)]
    elif subplot_count == 2:
        fig = make_subplots(rows=2, cols=1, row_heights=[0.7, 0.3], 
                           vertical_spacing=0.05)
        if show_macd:
            row_configs = [(1, 1), (2, 2)]
        else:
            row_configs = [(1, 1), (2, 3)]
    else:
        fig = make_subplots(rows=3, cols=1, row_heights=[0.5, 0.25, 0.25], 
                           vertical_spacing=0.05)
        row_configs = [(1, 1), (2, 2), (3, 3)]
    
    # K线图
    row, col = row_configs[0]
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
        for ma_period in [5, 10, 20, 60]:
            ma_col = f'ma{ma_period}'
            if ma_col in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df['date'],
                        y=df[ma_col],
                        mode='lines',
                        name=f'MA{ma_period}',
                        line=dict(width=1)
                    ),
                    row=row, col=col
                )
    
    # 布林带
    if 'bb_upper' in df.columns:
        # 上轨
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['bb_upper'],
                mode='lines',
                name='布林上轨',
                line=dict(color='rgba(156,39,176,0.5)', width=1),
                showlegend=True
            ),
            row=row, col=col
        )
        # 下轨
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['bb_lower'],
                mode='lines',
                name='布林下轨',
                line=dict(color='rgba(156,39,176,0.5)', width=1),
                fill='tonexty',
                fillcolor='rgba(156,39,176,0.1)'
            ),
            row=row, col=col
        )
    
    # 买入信号
    if buy_signals and len(buy_signals) > 0:
        buy_dates = [s['date'] for s in buy_signals]
        buy_prices = [s['price'] for s in buy_signals]
        
        fig.add_trace(
            go.Scatter(
                x=buy_dates,
                y=buy_prices,
                mode='markers',
                name='买入信号',
                marker=dict(
                    symbol='triangle-up',
                    size=15,
                    color='red',
                    line=dict(width=1, color='darkred')
                )
            ),
            row=row, col=col
        )
    
    # 卖出信号
    if sell_signals and len(sell_signals) > 0:
        sell_dates = [s['date'] for s in sell_signals]
        sell_prices = [s['price'] for s in sell_signals]
        
        fig.add_trace(
            go.Scatter(
                x=sell_dates,
                y=sell_prices,
                mode='markers',
                name='卖出信号',
                marker=dict(
                    symbol='triangle-down',
                    size=15,
                    color='green',
                    line=dict(width=1, color='darkgreen')
                )
            ),
            row=row, col=col
        )
    
    # MACD
    if show_macd and 'macd' in df.columns:
        row, col = row_configs[1]
        
        # MACD柱状图
        colors = ['red' if val >= 0 else 'green' for val in df['macd_hist']]
        fig.add_trace(
            go.Bar(
                x=df['date'],
                y=df['macd_hist'],
                name='MACD柱',
                marker_color=colors
            ),
            row=row, col=col
        )
        
        # MACD线
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['macd'],
                mode='lines',
                name='DIF',
                line=dict(color='blue', width=1)
            ),
            row=row, col=col
        )
        
        # 信号线
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['macd_signal'],
                mode='lines',
                name='DEA',
                line=dict(color='orange', width=1)
            ),
            row=row, col=col
        )
    
    # RSI
    if show_rsi and 'rsi' in df.columns:
        if show_macd:
            row, col = row_configs[2]
        else:
            row, col = row_configs[1]
        
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['rsi'],
                mode='lines',
                name='RSI',
                line=dict(color='purple', width=1)
            ),
            row=row, col=col
        )
        
        # 超买超卖线
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=row, col=col, annotation_text="超买线70")
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=row, col=col, annotation_text="超卖线30")
    
    # 更新布局
    fig.update_layout(
        title=dict(
            text=f'{strategy_name} K线图',
            font=dict(size=18, color='white')
        ),
        template='plotly_dark',
        height=600,
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor='rgba(0,0,0,0)'
        ),
        hovermode='x unified'
    )
    
    # 更新坐标轴
    fig.update_xaxes(title_text="日期", gridcolor='#1f2937', row=subplot_count, col=1)
    fig.update_yaxes(title_text="价格", gridcolor='#1f2937', row=1, col=1)
    
    if show_macd:
        fig.update_yaxes(title_text="MACD", gridcolor='#1f2937', row=2, col=1)
    
    if show_rsi:
        rsi_row = 3 if (show_macd and show_rsi) else 2
        fig.update_yaxes(title_text="RSI", gridcolor='#1f2937', row=rsi_row, col=1)
    
    return fig


def create_equity_curve(results, benchmark_return=None):
    """
    创建资金曲线图
    
    Parameters:
    -----------
    results : dict
        回测结果
    benchmark_return : float
        基准收益率（用于对比）
    
    Returns:
    --------
    plotly.graph_objects.Figure
    """
    daily_equity = results.get('每日资产', [])
    
    if not daily_equity:
        fig = go.Figure()
        fig.update_layout(
            title='资金曲线',
            template='plotly_dark'
        )
        return fig
    
    dates = [d['date'] for d in daily_equity]
    equity_values = [d['equity'] for d in daily_equity]
    
    # 计算净值曲线
    initial = results['起始资金']
    net_values = [e / initial for e in equity_values]
    
    fig = go.Figure()
    
    # 策略净值曲线
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=net_values,
            mode='lines',
            name='策略净值',
            line=dict(color='#2196F3', width=2),
            fill='tozeroy',
            fillcolor='rgba(33,150,243,0.2)'
        )
    )
    
    # 基准净值曲线
    if benchmark_return is not None:
        benchmark_values = [1 + benchmark_return / 100 * (i / (len(dates) - 1)) for i in range(len(dates))]
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=benchmark_values,
                mode='lines',
                name='基准净值',
                line=dict(color='#FFC107', width=2, dash='dash')
            )
        )
    
    # 初始资金线
    fig.add_hline(y=1, line_dash="dot", line_color="gray", annotation_text="初始净值")
    
    # 布局设置
    fig.update_layout(
        title=dict(
            text='资金净值曲线',
            font=dict(size=18, color='white')
        ),
        template='plotly_dark',
        height=400,
        xaxis=dict(
            title='日期',
            gridcolor='#1f2937'
        ),
        yaxis=dict(
            title='净值',
            gridcolor='#1f2937'
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified'
    )
    
    return fig


def create_trade_distribution(trades):
    """
    创建交易盈亏分布图
    
    Parameters:
    -----------
    trades : list
        交易记录列表
    
    Returns:
    --------
    plotly.graph_objects.Figure
    """
    if not trades:
        fig = go.Figure()
        fig.update_layout(
            title='交易盈亏分布',
            template='plotly_dark'
        )
        return fig
    
    profit_losses = [t['盈亏比例'] for t in trades]
    
    fig = go.Figure()
    
    # 直方图
    fig.add_trace(
        go.Histogram(
            x=profit_losses,
            nbinsx=20,
            name='交易次数',
            marker_color=['red' if x < 0 else 'green' for x in profit_losses],
            opacity=0.7
        )
    )
    
    # 零线
    fig.add_vline(x=0, line_dash="dash", line_color="white")
    
    fig.update_layout(
        title=dict(
            text='交易盈亏分布',
            font=dict(size=18, color='white')
        ),
        template='plotly_dark',
        height=300,
        xaxis=dict(
            title='盈亏比例 (%)',
            gridcolor='#1f2937'
        ),
        yaxis=dict(
            title='交易次数',
            gridcolor='#1f2937'
        ),
        showlegend=False,
        bargap=0.1
    )
    
    return fig


def create_drawdown_chart(daily_equity):
    """
    创建回撤图
    
    Parameters:
    -----------
    daily_equity : list
        每日资产记录
    
    Returns:
    --------
    plotly.graph_objects.Figure
    """
    if not daily_equity:
        fig = go.Figure()
        fig.update_layout(
            title='回撤曲线',
            template='plotly_dark'
        )
        return fig
    
    dates = [d['date'] for d in daily_equity]
    equity_values = [d['equity'] for d in daily_equity]
    
    # 计算回撤
    peak = equity_values[0]
    drawdowns = []
    
    for e in equity_values:
        if e > peak:
            peak = e
        drawdown = (peak - e) / peak * 100
        drawdowns.append(drawdown)
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=drawdowns,
            mode='lines',
            name='回撤',
            line=dict(color='#E91E63', width=2),
            fill='tozeroy',
            fillcolor='rgba(233,30,99,0.3)'
        )
    )
    
    fig.update_layout(
        title=dict(
            text='回撤曲线',
            font=dict(size=18, color='white')
        ),
        template='plotly_dark',
        height=250,
        xaxis=dict(
            title='日期',
            gridcolor='#1f2937'
        ),
        yaxis=dict(
            title='回撤 (%)',
            gridcolor='#1f2937'
        ),
        showlegend=False,
        hovermode='x unified'
    )
    
    return fig


def create_monthly_returns_chart(daily_equity):
    """
    创建月度收益热力图
    
    Parameters:
    -----------
    daily_equity : list
        每日资产记录
    
    Returns:
    --------
    plotly.graph_objects.Figure
    """
    if not daily_equity:
        fig = go.Figure()
        fig.update_layout(
            title='月度收益统计',
            template='plotly_dark'
        )
        return fig
    
    # 转换为DataFrame
    df = pd.DataFrame(daily_equity)
    df['month'] = df['date'].dt.to_period('M')
    df['year'] = df['date'].dt.year
    
    # 计算月度收益
    monthly_returns = df.groupby(['year', 'month']).agg({
        'equity': ['first', 'last']
    }).reset_index()
    monthly_returns.columns = ['year', 'month', 'start', 'end']
    monthly_returns['return'] = (monthly_returns['end'] - monthly_returns['start']) / monthly_returns['start'] * 100
    
    # 创建热力图数据
    years = monthly_returns['year'].unique()
    months = list(range(1, 13))
    
    z_data = []
    x_labels = []
    y_labels = []
    
    for year in years:
        y_labels.append(str(year))
        row_data = []
        for month in months:
            mask = (monthly_returns['year'] == year) & (monthly_returns['month'] == month)
            if mask.any():
                row_data.append(monthly_returns.loc[mask, 'return'].values[0])
            else:
                row_data.append(None)
        z_data.append(row_data)
    
    month_names = ['1月', '2月', '3月', '4月', '5月', '6月', 
                   '7月', '8月', '9月', '10月', '11月', '12月']
    
    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=month_names,
        y=y_labels,
        colorscale='RdYlGn',
        zmid=0,
        text=[[f'{v:.1f}%' if v is not None else '' for v in row] for row in z_data],
        texttemplate="%{text}",
        textfont={"size": 10},
        hovertemplate='%{y}年%{x}<br>收益率: %{z:.2f}%<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(
            text='月度收益热力图',
            font=dict(size=18, color='white')
        ),
        template='plotly_dark',
        height=300 + len(y_labels) * 20,
        xaxis=dict(title='月份', side='top'),
        yaxis=dict(title='年份', autorange='reversed')
    )
    
    return fig


def create_summary_metrics(results):
    """
    创建关键指标卡片数据
    
    Parameters:
    -----------
    results : dict
        回测结果
    
    Returns:
    --------
    dict
        指标数据
    """
    return {
        '总收益率': results.get('总收益率', 0),
        '年化收益率': results.get('年化收益率', 0),
        '最大回撤': results.get('最大回撤', 0),
        '起始资金': results.get('起始资金', 0),
        '最终资金': results.get('最终资金', 0),
        '总盈亏': results.get('总盈亏', 0),
        '交易次数': results.get('交易次数', 0),
        '胜率': results.get('胜率', 0),
        '盈亏比': results.get('盈亏比', 0),
        '平均持仓天数': results.get('平均持仓天数', 0),
        '基准收益率': results.get('基准收益率', 0),
        '超额收益': results.get('超额收益', 0)
    }
