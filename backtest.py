# -*- coding: utf-8 -*-
"""
回测引擎模块 v2.0
支持止盈止损和持仓管理
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class BacktestEngine:
    """回测引擎类"""
    
    def __init__(self, initial_capital=100000, buy_fee=0.00025, sell_fee=0.001275):
        self.initial_capital = initial_capital
        self.buy_fee = buy_fee
        self.sell_fee = sell_fee
        self.reset()
    
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
        """买入操作"""
        if self.position > 0:
            self.buy_signals.append({'date': date, 'price': price, 'type': signal_type})
            return
        
        # 计算每手（100股）成本（含手续费）
        cost_per_hand = 100 * price * (1 + self.buy_fee)
        max_hands = int(self.cash / cost_per_hand)
        max_shares = max_hands * 100
        
        if max_shares < 100:
            return
        
        cost = max_shares * price
        fee = cost * self.buy_fee
        total_cost = cost + fee
        
        self.position = max_shares
        self.avg_cost = price
        self.cash = self.cash - total_cost
        
        self.buy_signals.append({'date': date, 'price': price, 'type': signal_type})
        
        self.current_trade = {
            '买入日期': date.strftime('%Y-%m-%d'),
            '买入价格': price,
            '买入数量': max_shares,
            '买入手续费': fee,
            'start_date': date
        }
    
    def sell(self, date, price, reason="signal"):
        """卖出操作"""
        if self.position == 0 or self.current_trade is None:
            self.sell_signals.append({'date': date, 'price': price, 'type': reason})
            return
        
        sell_value = self.position * price
        fee = sell_value * self.sell_fee
        net_value = sell_value - fee
        
        cost = self.position * self.current_trade['买入价格']
        total_cost = cost + self.current_trade['买入手续费']
        profit = net_value - total_cost
        profit_pct = profit / total_cost * 100
        
        holding_days = (date - self.current_trade['start_date']).days
        
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
        
        self.cash = self.cash + net_value
        
        self.sell_signals.append({'date': date, 'price': price, 'type': reason})
        
        self.position = 0
        self.current_trade = None
    
    def update_equity(self, date, price):
        """更新每日资产"""
        position_value = self.position * price
        total_equity = self.cash + position_value
        
        self.daily_equity.append({
            'date': date,
            'equity': total_equity,
            'cash': self.cash,
            'position_value': position_value,
            'position': self.position
        })
    
    def run(self, df, stop_loss=0, take_profit=0, max_holding_days=0):
        """
        执行回测
        
        Parameters:
        -----------
        df : pd.DataFrame
            包含K线数据和买卖信号的DataFrame
        stop_loss : float
            止损比例（百分比）
        take_profit : float
            止盈比例（百分比）
        max_holding_days : int
            最大持仓天数
        
        Returns:
        --------
        dict : 回测结果
        """
        self.reset()
        
        for idx, row in df.iterrows():
            date = row['date']
            price = row['close']
            
            # 更新每日资产
            self.update_equity(date, price)
            
            # 检查止盈止损
            if self.position > 0 and self.current_trade:
                holding_days = (date - self.current_trade['start_date']).days
                
                # 止损检查
                if stop_loss > 0:
                    loss_pct = (price - self.current_trade['买入价格']) / self.current_trade['买入价格'] * 100
                    if loss_pct <= -stop_loss:
                        self.sell(date, price, "止损")
                        continue
                
                # 止盈检查
                if take_profit > 0:
                    profit_pct = (price - self.current_trade['买入价格']) / self.current_trade['买入价格'] * 100
                    if profit_pct >= take_profit:
                        self.sell(date, price, "止盈")
                        continue
                
                # 最大持仓天数检查
                if max_holding_days > 0 and holding_days >= max_holding_days:
                    self.sell(date, price, "到期平仓")
                    continue
            
            # 策略信号处理
            if row.get('sell_signal', False):
                self.sell(date, price, "策略卖出")
            elif row.get('buy_signal', False):
                self.buy(date, price, "策略买入")
        
        # 最终平仓
        if self.position > 0:
            last_row = df.iloc[-1]
            self.sell(last_row['date'], last_row['close'], "期末平仓")
        
        # 计算结果
        return self.calculate_results(df)
    
    def calculate_results(self, df):
        """计算回测结果"""
        if not self.daily_equity:
            return self._empty_results()
        
        equity_df = pd.DataFrame(self.daily_equity)
        equity_df.set_index('date', inplace=True)
        
        # 最终资产
        final_equity = equity_df['equity'].iloc[-1]
        
        # 总收益率
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100
        
        # 年化收益率
        if len(equity_df) > 1:
            days = (equity_df.index[-1] - equity_df.index[0]).days
            years = max(days / 365, 0.01)
            annual_return = ((final_equity / self.initial_capital) ** (1 / years) - 1) * 100
        else:
            annual_return = 0
        
        # 最大回撤
        peak = equity_df['equity'].expanding(min_periods=1).max()
        drawdown = (equity_df['equity'] - peak) / peak * 100
        max_drawdown = drawdown.min()
        
        # 交易统计
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t['盈亏金额'] > 0)
        losing_trades = sum(1 for t in self.trades if t['盈亏金额'] <= 0)
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        # 盈亏统计
        if self.trades:
            profits = [t['盈亏金额'] for t in self.trades if t['盈亏金额'] > 0]
            losses = [abs(t['盈亏金额']) for t in self.trades if t['盈亏金额'] < 0]
            avg_profit = np.mean(profits) if profits else 0
            avg_loss = np.mean(losses) if losses else 0
            profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
        else:
            avg_profit = avg_loss = profit_loss_ratio = 0
        
        # 夏普比率（简化版）
        if len(equity_df) > 1:
            returns = equity_df['equity'].pct_change().dropna()
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        return {
            '总收益率': total_return,
            '年化收益率': annual_return,
            '最大回撤': abs(max_drawdown),
            '夏普比率': sharpe_ratio,
            '总交易次数': total_trades,
            '盈利次数': winning_trades,
            '亏损次数': losing_trades,
            '胜率': win_rate,
            '盈亏比': profit_loss_ratio,
            '平均盈利': avg_profit,
            '平均亏损': avg_loss,
            '初始资金': self.initial_capital,
            '最终资产': final_equity,
            '利润总额': final_equity - self.initial_capital,
            '买入信号': self.buy_signals,
            '卖出信号': self.sell_signals,
            '交易记录': self.trades,
            '每日资产': equity_df
        }
    
    def _empty_results(self):
        """空结果"""
        return {
            '总收益率': 0,
            '年化收益率': 0,
            '最大回撤': 0,
            '夏普比率': 0,
            '总交易次数': 0,
            '盈利次数': 0,
            '亏损次数': 0,
            '胜率': 0,
            '盈亏比': 0,
            '平均盈利': 0,
            '平均亏损': 0,
            '初始资金': self.initial_capital,
            '最终资产': self.initial_capital,
            '利润总额': 0,
            '买入信号': [],
            '卖出信号': [],
            '交易记录': [],
            '每日资产': pd.DataFrame()
        }
