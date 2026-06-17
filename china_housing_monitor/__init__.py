"""
China Housing Monitor (CHM) - 全国核心34城楼市底部信号智能监测终端

A modular Python data pipeline that:
1. Manages a local SQLite DB with Chinese housing market data for 34 cities
2. Scrapes Lianjia for real-time listing counts and prices
3. Computes a multi-factor "Bottom Signal Score" per city per month
4. Compiles everything into a standalone single-file HTML SPA
"""

__version__ = "0.10.0"
