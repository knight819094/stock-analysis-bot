#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
進入點②：Telegram 互動查詢 bot（常駐長輪詢）。
傳台股代號/名稱、美股代號、或「加權」「金融」→ 回傳該檔分析（含 AI 解讀）。
僅回應 config 內的本人 chat_id。
"""
import re, time, json, datetime, urllib.request
from core import CFG, SSL_CTX, UA
import sources as S
import analysis as A
import ai
import notify

TOKEN = CFG["telegram_bot_token"]
OWNER = str(CFG["telegram_chat_id"])
API = f"https://api.telegram.org/bot{TOKEN}"

TAIEX_KEYS = {"加權", "加權指數", "大盤", "台股指數", "taiex", "TAIEX"}
FIN_KEYS = {"金融", "金融指數", "金融類", "金融類指數", "金融保險", "金融保險類指數"}

HELP = (
    "📈 股票查詢 bot\n"
    "直接傳「股票代號」或「名稱」即可，例如：\n"
    "  台股：2330　台積電　0050　聯發科\n"
    "  美股：AAPL　NVDA　TSLA\n"
    "查指數：加權　金融\n"
    "回傳：技術面(均線/KD/壓撐)、籌碼面(量能)、基本面(PE/殖利率/合理價)、進出場建議 ＋ AI 解讀。"
)

# ---------- 代號↔名稱對照 ----------
CODE2NAME, NAME2CODE, _MAP_TS = {}, {}, 0
def refresh_map(force=False):
    global CODE2NAME, NAME2CODE, _MAP_TS
    if not force and CODE2NAME and time.time() - _MAP_TS < 12 * 3600:
        return
    lst = S.fetch_stock_list()
    if not lst:
        return
    CODE2NAME = {c: n for c, n in lst}
    NAME2CODE = {n: c for c, n in lst}
    _MAP_TS = time.time()

# ---------- 解析使用者輸入 ----------
def resolve(text):
    t = text.strip()
    if t in TAIEX_KEYS:
        return ("INDEX_TAIEX", None)
    if t in FIN_KEYS:
        return ("INDEX_FIN", None)
    m = re.search(r"(\d{4,6}[A-Z]?)", t)
    if m:
        code = m.group(1)
        return (code, CODE2NAME.get(code, code))
    if t in NAME2CODE:
        return (NAME2CODE[t], t)
    # 美股代號或指數（例如 AAPL, ^VIX, .VIX）
    if re.fullmatch(r"[\^\.]?[A-Za-z0-9]{1,8}(\.[A-Za-z]{1,2})?", t):
        code = t.upper()
        if code.startswith("."):
            code = "^" + code[1:]
        return ("US", code)
    # 模糊比對（名稱包含輸入字串）
    seen = {}
    for name, code in NAME2CODE.items():
        if t and t in name:
            seen.setdefault(code, name)
    if len(seen) == 1:
        code = next(iter(seen))
        return (code, seen[code])
    if len(seen) > 1:
        return ("MULTI", seen)
    return (None, None)

# ---------- Telegram ----------
def get_updates(offset):
    url = f"{API}/getUpdates?timeout=30"
    if offset:
        url += f"&offset={offset}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40, context=SSL_CTX) as r:
        return json.loads(r.read().decode())

def reply(chat, text):
    notify.send(text, chat=chat)

# ---------- 處理訊息 ----------
def handle(chat, text):
    if OWNER and str(chat) != OWNER:
        return  # 僅限本人
    t = text.strip()
    if t in ("/start", "/help", "help", "說明", "?"):
        reply(chat, HELP); return
    kind, info = resolve(t)
    if kind is None:
        reply(chat, f"查無「{t}」。請輸入正確代號或名稱，或傳「說明」。"); return
    if kind == "MULTI":
        lines = "\n".join(f"  {c} {n}" for c, n in list(info.items())[:8])
        reply(chat, f"「{t}」符合多檔，請指定代號：\n{lines}"); return
    try:
        import chart
        photo = None
        
        if kind == "INDEX_TAIEX":
            reply(chat, "🔍 查詢 加權指數 中…")
            bars = S.fetch_taiex_ohlc(CFG["history_months"])
            rep = A.analyze_taiex(bars)
            photo = chart.draw_kline("TAIEX", "加權指數", bars)
        elif kind == "INDEX_FIN":
            reply(chat, "🔍 查詢 金融指數 中…")
            rep = A.analyze_fin_index()
        elif kind == "US":
            reply(chat, f"🔍 查詢美股 {info} 中…")
            bars = S.yahoo_chart(info)
            rep = A.analyze_us_stock(info, bars=bars)
            photo = chart.draw_kline(info, info, bars)
        else:
            reply(chat, f"🔍 查詢 {kind} {info} 中…（約 10-30 秒）")
            bars = S.fetch_stock_ohlcv(kind, CFG["history_months"])
            rep = A.analyze_stock(kind, info, bars=bars)
            photo = chart.draw_kline(kind, info, bars)
        
        final_text = ai.with_ai(rep)
        
        # 先發送圖片
        if photo:
            notify.send_photo(photo, chat=chat)
            
        reply(chat, final_text)
        
        # 進行歸檔
        import archive
        target_name = info if info else kind
        archive.save_record("bot_query", target_name, final_text)
        
    except Exception as e:
        reply(chat, f"⚠️ 分析失敗：{e}")

# ---------- 主迴圈 ----------
def main():
    refresh_map(force=True)
    print(f"[{datetime.datetime.now()}] bot started, {len(CODE2NAME)} 檔對照載入")
    offset = None
    while True:
        try:
            data = get_updates(offset)
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                text = msg.get("text")
                if not text:
                    continue
                refresh_map()
                import threading
                threading.Thread(target=handle, args=(msg["chat"]["id"], text)).start()
        except Exception as e:
            print(f"[{datetime.datetime.now()}] loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
