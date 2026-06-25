#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知層：Telegram 訊息發送。
依賴：core
"""
import json, urllib.request, urllib.parse
from core import CFG, SSL_CTX, UA

TOKEN = CFG["telegram_bot_token"]

def send(text, chat=None):
    """送訊息給指定 chat（預設 config 內本人）。回傳 Telegram API 結果 dict。"""
    chat = chat or CFG["telegram_chat_id"]
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as r:
        return json.loads(r.read().decode())

def send_photo(photo_path, caption="", chat=None):
    """傳送圖片給指定 chat。回傳 Telegram API 結果 dict。"""
    chat = chat or CFG["telegram_chat_id"]
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        import requests
        with open(photo_path, 'rb') as f:
            files = {'photo': f}
            data = {'chat_id': chat}
            if caption:
                data['caption'] = caption[:1024]
            r = requests.post(url, data=data, files=files, timeout=30)
            return r.json()
    except Exception as e:
        print(f"[Notify] send_photo failed: {e}")
        return {"ok": False, "error": str(e)}
