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

def send_line(message):
    """使用 LINE Messaging API 傳送 Push 訊息（如果 config 有設定的話）"""
    line_token = CFG.get("line_channel_access_token")
    line_user = CFG.get("line_user_id")
    
    if not line_token or not line_user:
        return {"ok": False, "error": "LINE token or user_id not configured"}
        
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    payload = {
        "to": line_user,
        "messages": [{"type": "text", "text": message}]
    }
    
    try:
        import requests
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        if r.status_code == 200:
            return {"ok": True}
        else:
            print(f"[Notify] LINE send failed: {r.status_code} {r.text}")
            return {"ok": False, "error": r.text}
    except Exception as e:
        print(f"[Notify] LINE send exception: {e}")
        return {"ok": False, "error": str(e)}
