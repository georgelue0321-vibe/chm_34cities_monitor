"""
China Housing Monitor (CHM) - 全国核心34城楼市"真底信号"智能监测终端

A single-file Python data pipeline that:
1. Manages a local SQLite DB with Chinese housing market data for 18 cities
2. Scrapes Lianjia for real-time listing counts and prices
3. Computes a multi-factor "True Bottom Score" per city per month
4. Compiles everything into a standalone single-file HTML SPA
"""

__version__ = "2.0.0"
