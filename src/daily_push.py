#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
進入點①：台股每日收盤分析推播（由 launchd 14:00 觸發）。
用法：python3 daily_push.py [--dry]   (--dry 只印出不推播)
"""
import sys, datetime
from core import CFG
import sources as S
import analysis as A
import ai
import notify

DRY = "--dry" in sys.argv

def main():
    today = datetime.date.today()
    header = f"📅 台股收盤分析　{today.strftime('%Y/%m/%d')} ({'一二三四五六日'[today.weekday()]})"

    # 先抓加權判斷今天是否有開盤
    taiex_bars = S.fetch_taiex_ohlc(CFG["history_months"])
    if CFG.get("skip_if_not_trading_day") and not A.is_trading_today(taiex_bars):
        print(f"{header}\n\n今日非交易日或收盤資料未更新，略過推播。")
        return

    parts = [header, "─" * 18]
    for code, name in [("2330", "台積電"), ("0050", "元大台灣50")]:
        if code in CFG["stocks"]:
            try: parts.append(A.analyze_stock(code, name))
            except Exception as e: parts.append(f"⚠️ {code} {name} 分析失敗：{e}")
            parts.append("─" * 18)
    if CFG["indices"].get("taiex"):
        try: parts.append(A.analyze_taiex(taiex_bars))
        except Exception as e: parts.append(f"⚠️ 加權指數失敗：{e}")
        parts.append("─" * 18)
    if CFG["indices"].get("financial"):
        try: parts.append(A.analyze_fin_index())
        except Exception as e: parts.append(f"⚠️ 金融指數失敗：{e}")
    parts.append("\n※ 數據來自 TWSE，操作建議為規則式計算，僅供參考非投資建議。")

    msg = "\n".join(parts)

    # AI 盤後綜合研判（整份報告）
    try:
        ai_text = ai.daily_comment(msg)
        if ai_text:
            msg += "\n\n🤖 AI 盤後綜合研判（" + ai.MODEL + "）\n" + ai_text
    except Exception as e:
        print("[AI] skip:", e)

    print(msg)
    if not DRY:
        res = notify.send(msg)
        print("\n[Telegram]", "OK" if res.get("ok") else res)
        
        # 進行歸檔
        import archive
        archive.save_record("daily_push", "ALL", msg)

if __name__ == "__main__":
    main()
