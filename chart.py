#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
圖表視覺化層：將股價歷史資料轉換為 K 線圖片
"""
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import mplfinance as mpf

CHART_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_charts")

def draw_kline(symbol, name, bars):
    """
    根據 bars [{date, o, h, l, c, vol/vol_lots}] 產生 K 線圖並存入 tmp_charts。
    回傳圖片的絕對路徑，若失敗回傳 None。
    """
    if not bars or len(bars) < 5:
        return None
        
    try:
        os.makedirs(CHART_DIR, exist_ok=True)
        
        # 轉換資料成 DataFrame
        df = pd.DataFrame(bars)
        
        # 把 date 轉為 DatetimeIndex
        df['Date'] = pd.to_datetime(df['date'])
        df.set_index('Date', inplace=True)
        
        # 統一欄位名稱給 mplfinance
        df.rename(columns={'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close'}, inplace=True)
        
        # 台股的 volume 是 vol_lots，美股是 vol
        if 'vol' in df.columns:
            df['Volume'] = df['vol']
        elif 'vol_lots' in df.columns:
            df['Volume'] = df['vol_lots']
        else:
            df['Volume'] = 0
            
        # 移除含有 NaN 的行
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        
        # 只取最近 120 天來畫圖，避免圖太擠
        df = df.tail(120)
        
        if df.empty:
            return None
            
        # 準備存檔路徑
        import datetime
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_symbol = str(symbol).replace('/', '_').replace('.', '_').replace('^', '_')
        filepath = os.path.join(CHART_DIR, f"{safe_symbol}_{now_str}.png")
        
        # 設定自訂風格 (台灣習慣：紅漲綠跌)
        mc = mpf.make_marketcolors(up='r', down='g', edge='inherit', wick='inherit', volume='inherit')
        s  = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=False)
        
        title = f"{symbol} {name}"
        
        # 畫圖 (帶 MA5, 10, 20)
        mpf.plot(df, type='candle', volume=True, mav=(5, 10, 20),
                 style=s, title=title, savefig=filepath, 
                 figsize=(10, 6), tight_layout=True)
                 
        return filepath
    except Exception as e:
        print(f"[Chart] Error drawing {symbol}: {e}")
        return None
