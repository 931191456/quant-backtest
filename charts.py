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
    # 子图配置
    row_configs = [(1, 1, 0.6)]
    row_heights = [0.5]
    
    if show_macd:
        row_configs.append((2, 2, 0.2))
        row_heights.append(0.2)
    
    if show_rsi:
        row_configs.append((3, 3, 0.2) if show_macd else (2, 2, 0.25))
        row_heights.append(0.2)
    
    fig = make_subplots(
        rows=len(row_configs), cols=1,
        row_heights=row_heights,
        vertical_spacing=0.05,
        shared_xaxes=True
    )
    
    # K线图
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
                marker=dict(symbol='triangle-up', size=15, color='red', line=dict(width=1, color='darkred'))
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
                marker=dict(symbol='triangle-down', size=15, color='green', line=dict(width=1, color='darkgreen'))
            ),
            row=row, col=col
        )
    
    # MACD
    if show_macd and 'macd' in df.columns:
        idx = 1 if show_rsi else 0
        row, col, _ = row_configs[idx + 1]
        
        colors = ['red' if val >= 0 else 'green' for val in df['macd_hist'].fillna(0)]
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
    
    # RSI
    if show_rsi and 'rsi' in df.columns:
        row, col, _ = row_configs[-1]
        fig.add_trace(
            go.Scatter(x=df['date'], y=df['rsi'], mode='lines', name='RSI', line=dict(color='purple', width=1.5)),
            row=row, col=col
        )
        # 超买超卖线
        fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=row, col=col)
        fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=row, col=col)
    
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
            line=dict(color='red', width=1)
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
    colors = ['green' if p > 0 else 'red' for p in profits]
    
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
    
    html = f"""
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0;">
        <div style="background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border: 1px solid #374151; border-radius: 12px; padding: 20px; text-align: center;">
            <div style="font-size: 14px; color: #9CA3AF; margin-bottom: 8px;">总收益率</div>
            <div style="font-size: 28px; font-weight: bold; color: {'#10B981' if total_return >= 0 else '#EF4444'};">{total_return:+.2f}%</div>
        </div>
        <div style="background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border: 1px solid #374151; border-radius: 12px; padding: 20px; text-align: center;">
            <div style="font-size: 14px; color: #9CA3AF; margin-bottom: 8px;">年化收益率</div>
            <div style="font-size: 28px; font-weight: bold; color: {'#10B981' if annual_return >= 0 else '#EF4444'};">{annual_return:+.2f}%</div>
        </div>
        <div style="background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border: 1px solid #374151; border-radius: 12px; padding: 20px; text-align: center;">
            <div style="font-size: 14px; color: #9CA3AF; margin-bottom: 8px;">最大回撤</div>
            <div style="font-size: 28px; font-weight: bold; color: #EF4444;">-{max_drawdown:.2f}%</div>
        </div>
        <div style="background: linear-gradient(135deg, #1f2937 0%, #111827 100%); border: 1px solid #374151; border-radius: 12px; padding: 20px; text-align: center;">
            <div style="font-size: 14px; color: #9CA3AF; margin-bottom: 8px;">夏普比率</div>
            <div style="font-size: 28px; font-weight: bold; color: {'#10B981' if sharpe >= 0 else '#EF4444'};">{sharpe:.2f}</div>
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
    img_bytes = fig.to_image(format="png", scale=2)
    return img_bytes


def export_to_pdf_report(results, df, symbol, strategies, params):
    """生成HTML报告（可打印为PDF）"""
    total_return = results.get('总收益率', 0)
    annual_return = results.get('年化收益率', 0)
    max_drawdown = results.get('最大回撤', 0)
    sharpe = results.get('夏普比率', 0)
    win_rate = results.get('胜率', 0)
    total_trades = results.get('总交易次数', 0)
    final_equity = results.get('最终资产', 0)
    profit = results.get('利润总额', 0)
    
    strategy_text = " + ".join(strategies) if isinstance(strategies, list) else str(strategies)
    params_text = ", ".join([f"{k}={v}" for k, v in params.items()]) if params else ""
    
    trades_html = ""
    if results.get('交易记录'):
        for i, trade in enumerate(results['交易记录'][:20], 1):
            profit_color = '#10B981' if trade['盈亏金额'] > 0 else '#EF4444'
            trades_html += f"""
            <tr>
                <td>{i}</td>
                <td>{trade['买入日期']}</td>
                <td>{trade['买入价格']:.2f}</td>
                <td>{trade['卖出日期']}</td>
                <td>{trade['卖出价格']:.2f}</td>
                <td>{trade['持仓天数']}天</td>
                <td style="color: {profit_color};">{trade['盈亏金额']:+,.2f}</td>
                <td style="color: {profit_color};">{trade['盈亏比例']:+.2f}%</td>
            </tr>
            """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>量化回测报告 - {symbol}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #0e1117; color: #F9FAFB; }}
            h1 {{ color: #60A5FA; border-bottom: 2px solid #374151; padding-bottom: 10px; }}
            h2 {{ color: #FCD34D; margin-top: 30px; }}
            .metric-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
            .metric-card {{ background: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 15px; text-align: center; }}
            .metric-label {{ font-size: 12px; color: #9CA3AF; }}
            .metric-value {{ font-size: 24px; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 10px; text-align: center; border: 1px solid #374151; }}
            th {{ background: #374151; color: #F9FAFB; }}
            tr:nth-child(even) {{ background: #1f2937; }}
            .positive {{ color: #10B981; }}
            .negative {{ color: #EF4444; }}
        </style>
    </head>
    <body>
        <h1>📈 量化回测报告</h1>
        <p><strong>标的代码：</strong>{symbol}</p>
        <p><strong>策略组合：</strong>{strategy_text}</p>
        <p><strong>策略参数：</strong>{params_text}</p>
        <p><strong>回测时间：</strong>{df['date'].min().strftime('%Y-%m-%d')} 至 {df['date'].max().strftime('%Y-%m-%d')}</p>
        
        <h2>📊 核心指标</h2>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">总收益率</div>
                <div class="metric-value {'positive' if total_return >= 0 else 'negative'}">{total_return:+.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">年化收益率</div>
                <div class="metric-value {'positive' if annual_return >= 0 else 'negative'}">{annual_return:+.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">最大回撤</div>
                <div class="metric-value negative">-{max_drawdown:.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">夏普比率</div>
                <div class="metric-value">{sharpe:.2f}</div>
            </div>
        </div>
        
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">胜率</div>
                <div class="metric-value">{win_rate:.1f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">交易次数</div>
                <div class="metric-value">{total_trades}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">最终资产</div>
                <div class="metric-value">¥{final_equity:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">利润总额</div>
                <div class="metric-value {'positive' if profit >= 0 else 'negative'}">¥{profit:+,.2f}</div>
            </div>
        </div>
        
        <h2>📋 交易明细</h2>
        <table>
            <tr>
                <th>序号</th>
                <th>买入日期</th>
                <th>买入价格</th>
                <th>卖出日期</th>
                <th>卖出价格</th>
                <th>持仓天数</th>
                <th>盈亏金额</th>
                <th>盈亏比例</th>
            </tr>
            {trades_html if trades_html else '<tr><td colspan="8">暂无交易记录</td></tr>'}
        </table>
        
        <p style="text-align: center; margin-top: 50px; color: #9CA3AF;">
            报告生成时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </body>
    </html>
    """
    return html
