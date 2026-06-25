#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
歸檔層：將分析結果與 AI 解讀寫入本地檔案 (JSON Lines 格式)，以供未來數據回測與策略優化使用。
"""
import os
import json
import datetime
import threading

ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archive")
_lock = threading.Lock()

def save_record(source, target, content):
    """
    將分析結果存入 JSONL 檔案中。
    :param source: 來源，例如 "bot_query" 或 "daily_push"
    :param target: 目標，例如 "TSLA"、"2330" 或 "ALL"
    :param content: 完整的分析報告純文字
    """
    try:
        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR, exist_ok=True)
            
        now = datetime.datetime.now()
        # 依據月份切分檔案，避免單一檔案過大
        filename = f"archive_{now.strftime('%Y_%m')}.jsonl"
        filepath = os.path.join(ARCHIVE_DIR, filename)
        
        record = {
            "timestamp": now.astimezone().isoformat(),
            "source": source,
            "target": target,
            "content": content
        }
        
        # 使用 lock 確保多執行緒寫入檔案時不會打架
        with _lock:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[{datetime.datetime.now()}] 儲存歸檔失敗: {e}")

if __name__ == "__main__":
    save_record("test_source", "TEST", "這是一筆測試存檔資料。")
    print(f"測試寫入完成，請檢查資料夾：{ARCHIVE_DIR}")
