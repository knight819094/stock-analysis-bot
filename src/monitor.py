#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
監控層：即時監控股價，當觸發設定的目標區間時，透過 Telegram 與 LINE (備用) 發送警示。
"""
import yfinance as yf
import pandas as pd
import time
import datetime
import argparse
from core import CFG
import notify

def fetch_and_analyze(ticker, targets):
    """獲取數據、計算 VWAP 並判斷是否發送通知"""
    try:
        print(f"[{datetime.datetime.now()}] 正在檢查 {ticker} 即時數據...")
        tkr = yf.Ticker(ticker)
        # 取當日 1 分鐘 K 線
        df = tkr.history(period="1d", interval="1m")
        
        if df.empty:
            print(f"[{ticker}] 目前無交易數據 (可能為盤前或休市)。")
            return None

        # 動態計算當日 VWAP
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['VP'] = df['Typical_Price'] * df['Volume']
        current_vwap = df['VP'].cumsum().iloc[-1] / df['Volume'].cumsum().iloc[-1]
        
        latest_data = df.iloc[-1]
        current_price = latest_data['Close']
        time_str = latest_data.name.strftime("%H:%M:%S")
        
        low_bound = targets.get("low", 0)
        high_bound = targets.get("high", 0)
        
        should_notify = False
        alert_msg = f"📊 【{ticker} 突破監控】({time_str})\n"
        alert_msg += "-" * 20 + "\n"
        alert_msg += f"當前價格: ${current_price:.2f}\n"
        alert_msg += f"當日 VWAP: ${current_vwap:.2f}\n"

        # 核心判斷邏輯
        if low_bound <= current_price <= high_bound:
            alert_msg += f"⚠️ 進入 ${low_bound}-${high_bound} 關鍵壓力區！\n"
            if current_price > current_vwap:
                alert_msg += "📈 籌碼強勢：股價 > VWAP，買盤願意高價介入。"
            else:
                alert_msg += "📉 籌碼弱勢：股價 < VWAP，須留意假突破回檔。"
            should_notify = True
            
        elif current_price > high_bound:
            alert_msg += f"🚀 【強勢突破】股價已正式站上 ${high_bound}！"
            should_notify = True

        # 觸發推播
        if should_notify:
            print(f"[{ticker}] 觸發警示條件，發送通知中...")
            # 預設發送至 Telegram
            notify.send(alert_msg)
            # 備用發送至 LINE
            notify.send_line(alert_msg)
            return True
        
        print(f"[{ticker}] 目前價格 ${current_price:.2f} 不在監控區間內，持續觀察。")
        return False

    except Exception as e:
        print(f"[{ticker}] 監控時發生錯誤: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Stock Monitor")
    parser.add_argument("--test", action="store_true", help="執行單次測試")
    args = parser.parse_args()

    targets_dict = CFG.get("monitor_targets", {})
    if not targets_dict:
        print("未在 config.json 設定 monitor_targets，結束監控。")
        return

    if args.test:
        print("=== 執行單次監控測試 ===")
        for ticker, targets in targets_dict.items():
            fetch_and_analyze(ticker, targets)
        return

    print("=== 開始持續監控 ===")
    while True:
        for ticker, targets in targets_dict.items():
            fetch_and_analyze(ticker, targets)
        
        # 每 3 分鐘輪詢一次
        time.sleep(180)

if __name__ == "__main__":
    main()
