#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 解讀層（Gemini）：把程式算好的精確數據餵給 Gemini，產生自然語言研判。
原則：數據由程式計算（保證正確），AI 只解讀、不得捏造數字。
依賴：core
"""
import json, time, urllib.request, urllib.error
from core import CFG, SSL_CTX

KEY = CFG.get("gemini_api_key", "")
MODEL = CFG.get("gemini_model", "gemini-2.5-flash")
ENABLED = bool(CFG.get("ai_commentary"))
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

SYS_SINGLE = (
    "你是專業證券分析師。下方是系統已計算好的個股/指數數據（價格、均線、KD、量能、"
    "基本面、評等等）。請用繁體中文做簡潔的綜合解讀，務必符合：\n"
    "1. 只依據提供的數據推論，絕對不可捏造或臆測任何數字。\n"
    "2. 涵蓋：① 趨勢研判（多/空/盤整）② 技術＋籌碼＋基本面綜合重點 ③ 操作策略與風險提醒。\n"
    "3. 邏輯防撞車：若研判為「偏空」，操作策略禁給追價買點，只能寫「等待站穩均線」或「左側低接」；若均線型態為「均線糾結」，禁止稱為多頭排列，必須提醒「觀望等待帶量突破」。\n"
    "4. 條列式、總長 180 字以內、口吻客觀。\n"
    "5. 結尾加一句『僅供參考，非投資建議』。"
)

SYS_DAILY = (
    "你是專業證券分析師。下方是今日台股盤後的多項數據（加權指數、權值股、ETF、金融類股等）。"
    "請用繁體中文寫一段『盤後綜合研判』，整合大盤方向與個股表現，務必符合：\n"
    "1. 只依據提供的數據，絕對不可捏造任何數字。\n"
    "2. 條列涵蓋：① 今日盤勢總結（多空強弱）② 焦點觀察（強弱勢、量能、估值是否偏高）"
    "③ 明日操作方向與風險。\n"
    "3. 總長 200 字以內、口吻客觀。\n"
    "4. 結尾加一句『僅供參考，非投資建議』。"
)

def _generate(system_text, report_text):
    if not ENABLED or not KEY:
        return None
    body = {
        "system_instruction": {"parts": [{"text": system_text}]},
        "contents": [{"parts": [{"text": "===數據===\n" + report_text}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2048,
            # 開啟 thinking（分析品質優先）；budget -1 = 動態，由模型決定思考量
            "thinkingConfig": {"thinkingBudget": CFG.get("gemini_thinking_budget", -1)},
        },
    }
    payload = json.dumps(body).encode("utf-8")
    last_err = None
    for i in range(5):  # 429/500/503 忙線時退避重試
        try:
            req = urllib.request.Request(
                URL, data=payload,
                headers={"Content-Type": "application/json", "x-goog-api-key": KEY},
            )
            with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as r:
                d = json.loads(r.read().decode())
            parts = d["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            return text or None
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 503) and i < 4:
                time.sleep(5 * (2 ** i))  # 退避 5, 10, 20, 40s
                continue
            break
        except Exception as e:
            last_err = e
            break
    return f"（AI 解讀暫時無法取得：{last_err}）"

def comment(report_text):
    """單檔/單一標的的綜合解讀。"""
    return _generate(SYS_SINGLE, report_text)

def daily_comment(report_text):
    """整份盤後報告的綜合研判。"""
    return _generate(SYS_DAILY, report_text)

def with_ai(report_text):
    """在報告後附加單檔 AI 解讀區塊；失敗或關閉則原樣回傳。"""
    c = comment(report_text)
    if not c:
        return report_text
    return report_text + "\n\n🤖 AI 綜合解讀（" + MODEL + "）\n" + c

if __name__ == "__main__":
    print(comment("📈 2330 台積電 收盤 2375 +2.81% MA20 2305 站上 KD K47/D44 黃金交叉 本益比31.9 偏高 量能正常"))
