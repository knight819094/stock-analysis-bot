#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資料源層：負責「抓資料」，不做分析。
- TWSE：盤後日線、本益比、加權/金融指數、全上市清單、盤中即時（MIS）
- Finnhub：美股報價/基本面/評等/市場狀態
- Yahoo：美股歷史 K 線
依賴：core
"""
import datetime, statistics
from core import CFG, http_json, twse_json, num, roc_to_date

# ===================== TWSE 盤後 =====================
def _month_starts(months):
    today = datetime.date.today()
    for back in range(months):
        ym = (today.replace(day=1) - datetime.timedelta(days=back * 28)).replace(day=1)
        yield ym.strftime("%Y%m01")

def fetch_stock_ohlcv(code, months):
    """個股日線，由舊到新 [{date,o,h,l,c,vol_lots,amount}]"""
    rows = {}
    for ds in _month_starts(months):
        d = twse_json(f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={ds}&stockNo={code}")
        if not d:
            continue
        for r in d.get("data", []):
            try:
                dt = roc_to_date(r[0])
                rows[dt] = {"date": dt, "vol_lots": (num(r[1]) or 0) / 1000.0, "amount": num(r[2]),
                            "o": num(r[3]), "h": num(r[4]), "l": num(r[5]), "c": num(r[6])}
            except Exception:
                continue
    return [rows[k] for k in sorted(rows)]

def fetch_valuation(code, months):
    """本益比/殖利率/淨值比最新值 + 本益比歷史區間（估合理價）。指數無此資料回 None。"""
    rows = {}
    for ds in _month_starts(months):
        d = twse_json(f"https://www.twse.com.tw/exchangeReport/BWIBBU?response=json&date={ds}&stockNo={code}")
        if not d:
            continue
        for r in d.get("data", []):
            try:
                rows[roc_to_date(r[0])] = {"yield": num(r[1]), "pe": num(r[3]), "pb": num(r[4])}
            except Exception:
                continue
    if not rows:
        return None
    keys = sorted(rows)
    last = rows[keys[-1]]
    pe_series = [rows[k]["pe"] for k in keys if rows[k]["pe"]]
    band = None
    if len(pe_series) >= 8:
        q = statistics.quantiles(pe_series, n=4)  # [Q1, 中位數, Q3]
        band = {"low": q[0], "mid": statistics.median(pe_series), "high": q[2]}
    elif pe_series:
        band = {"low": min(pe_series), "mid": statistics.mean(pe_series), "high": max(pe_series)}
    return {"yield": last["yield"], "pe": last["pe"], "pb": last["pb"], "pe_band": band}

def fetch_taiex_ohlc(months):
    """加權指數日線 OHLC，由舊到新。"""
    rows = {}
    for ds in _month_starts(months):
        d = twse_json(f"https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={ds}")
        if not d:
            continue
        for r in d.get("data", []):
            try:
                dt = roc_to_date(r[0])
                rows[dt] = {"date": dt, "o": num(r[1]), "h": num(r[2]), "l": num(r[3]), "c": num(r[4])}
            except Exception:
                continue
    return [rows[k] for k in sorted(rows)]

def fetch_fin_index_closes(days=12):
    """金融保險類指數每日收盤（無高低），由舊到新 [(date, close, chg_pct)]"""
    out = {}
    d0 = datetime.date.today()
    got = probe = 0
    while got < days and probe < days * 2 + 6:
        if d0.weekday() < 5:  # 只查平日
            ds = d0.strftime("%Y%m%d")
            d = twse_json(f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date={ds}&type=IND", retries=2)
            if d:
                for t in d.get("tables", []):
                    for r in (t.get("data") or []):
                        if isinstance(r, list) and r and r[0] == "金融保險類指數":
                            out[d0] = (num(r[1]), num(r[4])); got += 1
                            break
        d0 -= datetime.timedelta(days=1)
        probe += 1
    return [(k, out[k][0], out[k][1]) for k in sorted(out)]

def fetch_stock_list():
    """全上市 [(code, name)]，給 bot 做名稱↔代號對照。"""
    d = twse_json("https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json", retries=3)
    if not d:
        return []
    data = d.get("data") or (d.get("tables", [{}])[0].get("data"))
    out = []
    for r in (data or []):
        try:
            out.append((r[0].strip(), r[1].strip()))
        except Exception:
            continue
    return out

# ===================== TWSE 盤中即時（MIS）=====================
def tw_market_open(now=None):
    """台股盤中：平日 09:00–13:30。回傳 (是否盤中, 'HH:MM')"""
    now = now or datetime.datetime.now()
    if now.weekday() >= 5:
        return False, now.strftime("%H:%M")
    t = now.time()
    return (datetime.time(9, 0) <= t <= datetime.time(13, 30)), now.strftime("%H:%M")

def tw_realtime(mis_code):
    """mis_code 如 tse_2330.tw / tse_t00.tw（加權）/ tse_t17.tw（金融）。
    回傳 {price,prev,chg,chgp,t} 或 None。"""
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={mis_code}&json=1&delay=0"
    try:
        d = http_json(url, retries=2, timeout=12)
        a = d.get("msgArray", [])
        if not a:
            return None
        s = a[0]
        price = num(s.get("z"))
        if price is None:  # 無成交價，取最佳買價或開盤
            bid = (s.get("b") or "").split("_")[0]
            price = num(bid) or num(s.get("o"))
        prev = num(s.get("y"))
        if price is None or prev is None:
            return None
        chg = price - prev
        return {"price": price, "prev": prev, "chg": chg,
                "chgp": chg / prev * 100 if prev else 0, "t": s.get("t", "")}
    except Exception:
        return None

# ===================== Finnhub（美股）=====================
FINNHUB = "https://finnhub.io/api/v1"

def finnhub(path):
    """回傳 JSON 或 None（失敗不丟例外）。"""
    sep = "&" if "?" in path else "?"
    try:
        return http_json(f"{FINNHUB}{path}{sep}token={CFG.get('finnhub_api_key', '')}")
    except Exception:
        return None

def us_market_status():
    """{isOpen, session, holiday}（含夏令時間與假日）。"""
    return finnhub("/stock/market-status?exchange=US")

# ===================== Yahoo（美股歷史）=====================
def yahoo_chart(symbol, rng="1y"):
    """美股日線，由舊到新 [{o,h,l,c,vol}]。Yahoo 特別股用 '-'（BRK.B→BRK-B）。"""
    symbol = symbol.replace(".", "-")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval=1d"
    try:
        d = http_json(url, retries=2)
        res = d["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        bars = []
        for o, h, l, c, v in zip(q["open"], q["high"], q["low"], q["close"], q["volume"]):
            if None in (o, h, l, c):
                continue
            bars.append({"o": o, "h": h, "l": l, "c": c, "vol": v or 0})
        return bars
    except Exception:
        return []
