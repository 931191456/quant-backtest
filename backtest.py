# -*- coding: utf-8 -*-
"""
回测引擎模块
执行回测并计算各项指标
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class BacktestEngine:
    """
    回测引擎类
    """
    
    def __init__(self, initial_capital=100000, buy_fee=0.00025, sell_fee=0.001275):
        """
        初始化回测引擎
        
        Parameters:
        -----------
        initial_capital : float
            初始资金
        buy_fee : float
            买入手续费率
        sell_fee : float
            卖出手续费率（含印花税）
        """
        self.initial_capital = initial_capital
        self.buy_fee = buy_fee
        self.sell_fee = sell_fee
        
        # 回测状态
        self.cash = initial_capital  # 当前现金
        self.position = 0  # 持仓数量
        self.avg_cost = 0  # 平均成本
        self.equity = initial_capital  # 当前总资产
        
        # 交易记录
        self.trades = []  # 完成的交易
        self.current_trade = None  # 当前持仓记录
        
        # 每日资产记录
        self.daily_equity = []
        
        # 买卖信号记录
        self.buy_signals = []
        self.sell_signals = []
    
    def reset(self):
        """重置回测状态"""
        self.cash = self.initial_capital
        self.position = 0
        self.avg_cost = 0
        self.equity = self.initial_capital
        self.trades = []
        self.current_trade = None
        self.daily_equity = []
        self.buy_signals = []
        self.sell_signals = []
    
    def buy(self, date, price, signal_type="signal"):
        """
        买入操作
        
        Parameters:
        -----------
        date : datetime
            买入日期
        price : float
            买入价格
        signal_type : str
            信号来源
        """
        if self.position > 0:
            # 已有持仓，先记录信号
            self.buy_signals.append({
                'date': date,
                'price': price,
                'type': signal_type
            })
            return
        
        # 计算可买入数量（取整到百股）
        max_shares = int(self.cash / (price * (1 + self.buy_fee)) / 100) * 100
        
        if max_shares < 100:
            # 资金不足，无法买入
            return
        
        # 执行买入
        cost = max_shares * price
        fee = cost * self.buy_fee
        total_cost = cost + fee
        
        self.position = max_shares
        self.avg_cost = price
        self.cash = self.cash - total_cost
        
        # 记录买入信号
        self.buy_signals.append({
            'date': date,
            'price': price,
            'type': signal_type
        })
        
        # 开始持仓记录
        self.current_trade = {
            '买入日期': date.strftime('%Y-%m-%d'),
            '买入价格': price,
            '买入数量': max_shares,
            '买入手续费': fee,
            'start_date': date
        }
    
    def sell(self, date, price, reason="signal"):
        """
        卖出操作
        
        Parameters:
        -----------
        date : datetime
            卖出日期
        price : float
            卖出价格
        reason : str
            卖出原因
        """
        if self.position == 0 or self.current_trade is None:
            # 无持仓可卖，记录卖出信号
            self.sell_signals.append({
                'date': date,
                'price': price,
                'type': reason
            })
            return
        
        # 执行卖出
        sell_value = self.position * price
        fee = sell_value * self.sell_fee
        net_value = sell_value - fee
        
        # 计算盈亏
        cost = self.position * self.current_trade['买入价格']
        total_cost = cost + self.current_trade['买入手续费']
        profit = net_value - total_cost
        profit_pct = profit / total_cost * 100
        
        # 持仓天数
        holding_days = (date - self.current_trade['start_date']).days
        
        # 记录完成的交易
        trade_record = {
            '买入日期': self.current_trade['买入日期'],
            '买入价格': self.current_trade['买入价格'],
            '买入数量': self.current_trade['买入数量'],
            '买入手续费': self.current_trade['买入手续费'],
            '卖出日期': date.strftime('%Y-%m-%d'),
            '卖出价格': price,
            '卖出手续费': fee,
            '持仓天数': holding_days,
            '盈亏金额': profit,
            '盈亏比例': profit_pct,
            '卖出原因': reason
        }
        self.trades.append(trade_record)
        
        # 更新资金
        self.cash = self.cash + net_value
        
        # 记录卖出信号
        self.sell_signals.append({
            'date': date,
            'price': price,
            'type': reason
        })
        
        # 清空持仓
        self.position = 0
        self.current_trade = None
    
    def update_equity(self, date, price):
        """
        更新每日资产
        
        Parameters:
        -----------
        date : datetime
            日期
        price : float
            当前价格
        """
        position_value = self.position * price
        total_equity = self.cash + position_value
        
        self.daily_equity.append({
            'date': date,
            'equity': total_equity,
            'cash': self.cash,
            'position_value': position_value,
            'position': self.position,
            'price': price
        })
    
    def force_sell_all(self, date, price, reason="回测结束"):
        """
        强制平仓
        
        Parameters:
        -----------
        date : datetime
            日期
        price : float
            价格
        reason : str
            原因
        """
        if self.position > 0:
            self.sell(date, price, reason)
    
    def run(self, df, stop_loss_pct=0, take_profit_pct=0, max_holding_days=0):
        """
        运行回测
        
        Parameters:
        -----------
        df : pd.DataFrame
            包含日期、收盘价、信号等数据
        stop_loss_pct : float
            止损比例（百分比）
        take_profit_pct : float
            止盈比例（百分比）
        max_holding_days : int
            最大持仓天数（0表示不限）
        
        Returns:
        --------
        dict
            回测结果
        """
        self.reset()
        
        for idx, row in df.iterrows():
            date = row['date']
            price = row['close']
            signal = row.get('signal', 0)
            
            # 更新每日资产
            self.update_equity(date, price)
            
            # 处理交易信号
            if signal == 1:  # 买入信号
                self.buy(date, price, "策略信号")
            
            elif signal == -1:  # 卖出信号
                self.sell(date, price, "策略信号")
            
            # 止盈止损检查
            if self.position > 0 and self.current_trade is not None:
                cost = self.current_trade['买入价格']
                profit_pct = (price - cost) / cost * 100
                
                # 止损
                if stop_loss_pct > 0 and profit_pct <= -stop_loss_pct:
                    self.sell(date, price, f"止损{-stop_loss_pct}%")
                
                # 止盈
                elif take_profit_pct > 0 and profit_pct >= take_profit_pct:
                    self.sell(date, price, f"止盈{take_profit_pct}%")
                
                # 最大持仓天数
                elif max_holding_days > 0:
                    holding_days = (date - self.current_trade['start_date']).days
                    if holding_days >= max_holding_days:
                        self.sell(date, price, f"持仓满{max_holding_days}天")
            
            # 更新持仓成本（用于计算未实现盈亏）
            if self.position > 0:
                self.avg_cost = (self.avg_cost * (self.position / (self.position + 0)) + 
                                price * 0) if self.position > 0 else 0
        
        # 回测结束时强制平仓
        if len(df) > 0:
            last_row = df.iloc[-1]
            self.force_sell_all(last_row['date'], last_row['close'], "回测结束")
        
        return self.get_results()
    
    def get_results(self):
        """
        获取回测结果
        
        Returns:
        --------
        dict
            回测结果统计
        """
        if not self.daily_equity:
            return {
                '总收益率': 0,
                '年化收益率': 0,
                '最大回撤': 0,
                '起始资金': self.initial_capital,
                '最终资金': self.initial_capital,
                '总盈亏': 0,
                '交易次数': 0,
                '胜率': 0,
                '盈亏比': 0,
                '平均持仓天数': 0,
                '交易记录': [],
                '每日资产': [],
                '买入信号': [],
                '卖出信号': []
            }
        
        final_equity = self.daily_equity[-1]['equity']
        total_profit = final_equity - self.initial_capital
        total_return = total_profit / self.initial_capital * 100
        
        # 计算年化收益率
        if len(self.daily_equity) > 1:
            days = (self.daily_equity[-1]['date'] - self.daily_equity[0]['date']).days
            if days > 0:
                annual_return = ((final_equity / self.initial_capital) ** (365 / days) - 1) * 100
            else:
                annual_return = 0
        else:
            annual_return = 0
        
        # 计算最大回撤
        equity_curve = [d['equity'] for d in self.daily_equity]
        max_drawdown, _, _ = self._calculate_max_drawdown(equity_curve)
        
        # 计算胜率
        if self.trades:
            winning_trades = sum(1 for t in self.trades if t['盈亏金额'] > 0)
            win_rate = winning_trades / len(self.trades) * 100
        else:
            win_rate = 0
        
        # 计算盈亏比
        if self.trades:
            profits = [t['盈亏金额'] for t in self.trades if t['盈亏金额'] > 0]
            losses = [abs(t['盈亏金额']) for t in self.trades if t['盈亏金额'] < 0]
            avg_profit = np.mean(profits) if profits else 0
            avg_loss = np.mean(losses) if losses else 0
            profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
        else:
            profit_loss_ratio = 0
        
        # 平均持仓天数
        if self.trades:
            avg_holding_days = np.mean([t['持仓天数'] for t in self.trades])
        else:
            avg_holding_days = 0
        
        return {
            '总收益率': total_return,
            '年化收益率': annual_return,
            '最大回撤': max_drawdown,
            '起始资金': self.initial_capital,
            '最终资金': final_equity,
            '总盈亏': total_profit,
            '交易次数': len(self.trades),
            '胜率': win_rate,
            '盈亏比': profit_loss_ratio,
            '平均持仓天数': avg_holding_days,
            '交易记录': self.trades,
            '每日资产': self.daily_equity,
            '买入信号': self.buy_signals,
            '卖出信号': self.sell_signals
        }
    
    def _calculate_max_drawdown(self, equity_curve):
        """
        计算最大回撤
        
        Parameters:
        -----------
        equity_curve : list
            净值曲线
        
        Returns:
        --------
        tuple
            (最大回撤百分比, 峰值索引, 谷值索引)
        """
        if len(equity_curve) == 0:
            return 0, 0, 0
        
        peak = equity_curve[0]
        max_drawdown = 0
        peak_idx = 0
        trough_idx = 0
        
        for i, value in enumerate(equity_curve):
            if value > peak:
                peak = value
                peak_idx = i
            
            drawdown = (peak - value) / peak if peak > 0 else 0
            
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                trough_idx = i
        
        return max_drawdown * 100, peak_idx, trough_idx


def run_backtest(df, strategy_name, strategy_params, 
                 initial_capital=100000, buy_fee=0.00025, sell_fee=0.001275,
                 stop_loss=0, take_profit=0, max_holding_days=0,
                 benchmark_df=None):
    """
    运行回测的便捷函数
    
    Parameters:
    -----------
    df : pd.DataFrame
        标的资产数据
    strategy_name : str
        策略名称
    strategy_params : dict
        策略参数
    initial_capital : float
        初始资金
    buy_fee : float
        买入费率
    sell_fee : float
        卖出手续费（含印花税）
    stop_loss : float
        止损比例
    take_profit : float
        止盈比例
    max_holding_days : int
        最大持仓天数
    benchmark_df : pd.DataFrame
        基准指数数据
    
    Returns:
    --------
    dict
        回测结果
    """
    from strategies import apply_strategy
    
    # 应用策略生成信号
    df = apply_strategy(df, strategy_name, **strategy_params)
    
    # 运行回测
    engine = BacktestEngine(initial_capital, buy_fee, sell_fee)
    results = engine.run(df, stop_loss, take_profit, max_holding_days)
    
    # 计算基准收益
    if benchmark_df is not None and len(benchmark_df) > 0:
        benchmark_start = benchmark_df.iloc[0]['close']
        benchmark_end = benchmark_df.iloc[-1]['close']
        benchmark_return = (benchmark_end - benchmark_start) / benchmark_start * 100
        results['基准收益率'] = benchmark_return
        results['超额收益'] = results['总收益率'] - benchmark_return
    
    # 添加标的名称
    results['标的类型'] = 'stock'
    results['标的代码'] = ''
    
    return results
