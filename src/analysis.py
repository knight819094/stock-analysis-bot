#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析層：把資料源的數據組裝成報告文字（純文字，不負責發送）。
- 台股：analyze_stock / analyze_taiex / analyze_fin_index
- 美股：analyze_us_stock
依賴：core（指標）、sources（資料）
"""
import datetime
from core import CFG, sma, compute_kd, trend_arrow
import sources as S

# ===================== 共用 =====================
def check_ma_status(ma_dict):
    ma_vals = [ma_dict.get(p) for p in [5, 10, 20, 60] if ma_dict.get(p) is not None]
    if len(ma_vals) >= 4:
        max_ma, min_ma = max(ma_vals), min(ma_vals)
        if (max_ma - min_ma) / min_ma <= 0.025:
            return "均線嚴重糾結 (面臨表態轉折)"
        m200 = ma_dict.get(200)
        m5, m10, m20, m60 = ma_dict.get(5), ma_dict.get(10), ma_dict.get(20), ma_dict.get(60)
        if m200 is not None:
            if m5 > m10 > m20 > m60 > m200: return "標準多頭排列"
            if m5 < m10 < m20 < m60 < m200: return "標準空頭排列"
        else:
            if m5 > m10 > m20 > m60: return "短期多頭排列"
            if m5 < m10 < m20 < m60: return "短期空頭排列"
    return "均線交錯"

def is_trading_today(taiex_bars):
    return bool(taiex_bars) and taiex_bars[-1]["date"] == datetime.date.today()

def price_header(mis_code, fb_price, fb_chg, fb_chgp):
    """台股價格行：盤中回即時價（含時間），盤後回收盤。回傳 (箭頭, 文字行)。"""
    is_open, hhmm = S.tw_market_open()
    if is_open:
        rt = S.tw_realtime(mis_code)
        if rt and rt["price"]:
            arrow = "🔺" if rt["chg"] >= 0 else "🔻"
            t = rt["t"] or hhmm
            return arrow, f"💰 現價 {rt['price']:.2f}　{rt['chg']:+.2f} ({rt['chgp']:+.2f}%)　⏱ {t}（盤中）"
    arrow = "🔺" if fb_chg >= 0 else "🔻"
    return arrow, f"💰 收盤 {fb_price:.2f}　{fb_chg:+.2f} ({fb_chgp:+.2f}%)"

def _f(v, fmt="{:.2f}", default="—"):
    try:
        return fmt.format(v) if v is not None else default
    except Exception:
        return default

# ===================== 台股 =====================
def analyze_stock(code, name, bars=None):
    bars = bars if bars is not None else S.fetch_stock_ohlcv(code, CFG["history_months"])
    if len(bars) < 20:
        return f"⚠️ {code} {name}：資料不足，略過"
    closes = [b["c"] for b in bars if b["c"]]
    highs = [b["h"] for b in bars]; lows = [b["l"] for b in bars]
    vols = [b["vol_lots"] for b in bars]
    last = bars[-1]; prev_c = bars[-2]["c"]
    chg = last["c"] - prev_c
    chg_pct = chg / prev_c * 100 if prev_c else 0

    ma = {p: sma(closes, p) for p in CFG["ma_periods"]}
    ks, ds = compute_kd(highs, lows, closes, CFG["kd_period"])
    k, d = ks[-1], ds[-1]; k_prev, d_prev = ks[-2], ds[-2]

    win = bars[-20:]
    resistance = max(b["h"] for b in win); support = min(b["l"] for b in win)

    # 籌碼面：量能
    avg20_vol = sma(vols, 20)
    vol_ratio = last["vol_lots"] / avg20_vol if avg20_vol else None
    if vol_ratio is None: vol_desc = "—"
    elif vol_ratio >= 2.0: vol_desc = f"爆量 {vol_ratio:.1f}倍 ⚠️"
    elif vol_ratio >= 1.5: vol_desc = f"放量 {vol_ratio:.1f}倍"
    elif vol_ratio <= 0.6: vol_desc = f"量縮 {vol_ratio:.1f}倍"
    else: vol_desc = f"正常 {vol_ratio:.1f}倍"

    # 基本面（本益比區間用較短窗即可，不必跟著 MA200 拉長）
    fund = S.fetch_valuation(code, CFG.get("valuation_months", 5))

    # 進出場（規則式）
    entry_lo = support
    entry_hi = max([v for v in [support, ma.get(20)] if v]) if ma.get(20) else support
    if entry_hi < entry_lo: entry_lo, entry_hi = entry_hi, entry_lo
    target = resistance
    stop = round(support * 0.97, 2)

    kd_cross = ""
    if None not in (k, d, k_prev, d_prev):
        if k_prev <= d_prev and k > d: kd_cross = "KD 黃金交叉（偏多）"
        elif k_prev >= d_prev and k < d: kd_cross = "KD 死亡交叉（偏空）"
        elif k > 80: kd_cross = "KD 高檔鈍化，注意過熱回檔"
        elif k < 20: kd_cross = "KD 低檔，留意超賣反彈"
        else: kd_cross = "KD 中性"
    above_ma = "站上" if (ma.get(20) and last["c"] >= ma[20]) else "跌破"
    bias = "偏多" if (ma.get(20) and last["c"] >= ma[20] and k and k >= d) else \
           ("偏空" if (ma.get(20) and last["c"] < ma[20]) else "中性")

    arrow, pline = price_header(f"tse_{code}.tw", last["c"], chg, chg_pct)
    L = [f"📈 {code} {name}　{arrow}", pline, "",
         "【技術面】"]
    ma_str = "　".join(f"MA{p} {ma[p]:.1f}{trend_arrow(last['c'], ma[p])}" for p in CFG["ma_periods"] if ma.get(p))
    L.append(f"📊 均線 {ma_str}")
    L.append(f"📊 股價{above_ma} MA20")
    L.append(f"📊 均線型態：{check_ma_status(ma)}")
    if k is not None:
        L.append(f"📊 KD：K {k:.1f} / D {d:.1f}　{kd_cross}")
    L.append(f"📊 壓力 {resistance:.2f}　支撐 {support:.2f}（近20日）")
    L += ["", "【籌碼面】",
          f"📦 今量 {last['vol_lots']:.0f} 張　20日均量 {avg20_vol:.0f} 張",
          f"📦 量能：{vol_desc}", "", "【基本面】"]
    if fund:
        pe = f"{fund['pe']:.1f}" if fund.get("pe") else "—(ETF/無)"
        pb = f"{fund['pb']:.2f}" if fund.get("pb") else "—"
        yd = f"{fund['yield']:.2f}%" if fund.get("yield") else "—"
        L.append(f"🏢 本益比 {pe}　淨值比 {pb}　殖利率 {yd}")
        if fund.get("pe") and fund.get("pe_band"):
            eps = last["c"] / fund["pe"]; b = fund["pe_band"]
            cheap, fair, expensive = eps * b["low"], eps * b["mid"], eps * b["high"]
            if last["c"] <= cheap: pos = "偏低 🟢"
            elif last["c"] >= expensive: pos = "偏高 🔴"
            else: pos = "合理區 🟡"
            L.append(f"💲 預估合理價：便宜 {cheap:.1f}｜合理 {fair:.1f}｜昂貴 {expensive:.1f}")
            L.append(f"💲 現價位階：{pos}（本益比河流，近{CFG['history_months']}月）")
        else:
            L.append("💲 預估合理價：—（ETF/無本益比，不適用）")
    else:
        L.append("🏢 —（查無，ETF/指數不適用）")
    L += ["", "【操作建議｜僅供參考】", f"🎯 研判：{bias}"]
    if bias == "偏空":
        lo = round(support * 0.98, 2)
        hi = round(support * 1.02, 2)
        if hi > last["c"]: hi = min(hi, last["c"])
        L.append(f"🟢 進場參考：{lo:.2f} ~ {hi:.2f} (左側低接) 或等站穩 MA20")
    else:
        L.append(f"🟢 進場參考：{entry_lo:.2f} ~ {entry_hi:.2f}")
    
    L += [f"🔴 目標(壓力)：{target:.2f}",
          f"🛑 停損參考：{stop:.2f}"]
    return "\n".join(L)

def analyze_taiex(bars):
    if not bars or len(bars) < 20:
        return "⚠️ 加權指數：資料不足"
    closes = [b["c"] for b in bars]; highs = [b["h"] for b in bars]; lows = [b["l"] for b in bars]
    last = bars[-1]; prev = bars[-2]["c"]
    chg = last["c"] - prev; chg_pct = chg / prev * 100 if prev else 0
    ma = {p: sma(closes, p) for p in CFG["ma_periods"]}
    ks, ds = compute_kd(highs, lows, closes, CFG["kd_period"])
    k, d = ks[-1], ds[-1]
    win = bars[-20:]
    res = max(b["h"] for b in win); sup = min(b["l"] for b in win)
    bias = "偏多" if (ma.get(20) and last["c"] >= ma[20]) else "偏空"
    arrow, pline = price_header("tse_t00.tw", last["c"], chg, chg_pct)
    L = [f"📊 加權指數　{arrow}", pline,
         "　".join(f"MA{p} {ma[p]:.0f}" for p in CFG['ma_periods'] if ma.get(p))]
    if k is not None:
        L.append(f"KD：K {k:.1f}/D {d:.1f}　研判 {bias}")
    L.append(f"壓力 {res:.0f}　支撐 {sup:.0f}")
    return "\n".join(L)

def analyze_fin_index():
    data = S.fetch_fin_index_closes(12)
    if not data:
        return "📊 金融指數：查無資料"
    closes = [c for _, c, _ in data if c]
    _, last_c, last_pct = data[-1]
    ma5 = sma(closes, 5); ma10 = sma(closes, 10)
    trend = "多頭" if (ma5 and ma10 and ma5 >= ma10) else "空頭"
    prev_fin = last_c / (1 + last_pct / 100) if last_pct is not None else last_c
    arrow, pline = price_header("tse_t17.tw", last_c, last_c - prev_fin, last_pct or 0)
    L = [f"📊 金融保險類指數　{arrow}", pline]
    if ma5:
        L.append(f"MA5 {ma5:.2f}" + (f"　MA10 {ma10:.2f}　{trend}" if ma10 else ""))
    L.append("（指數無逐日高低，KD 略）")
    return "\n".join(L)

# ===================== 美股 =====================
def _fmt_et(ts):
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.fromtimestamp(ts, ZoneInfo("America/New_York")).strftime("%H:%M ET")
    except Exception:
        return ""

def analyze_us_stock(symbol, bars=None):
    sym = symbol.upper().strip()
    if sym == "BRK":
        sym = "BRK.B"
    bars = bars if bars is not None else S.yahoo_chart(sym)
    quote = S.finnhub(f"/quote?symbol={sym}")
    
    if (not quote or quote.get("c") in (None, 0)) and bars:
        # Fallback to Yahoo if Finnhub fails (e.g., indices like ^VIX)
        last = bars[-1]
        prev = bars[-2]["c"] if len(bars) >= 2 else last["c"]
        quote = {
            "c": last["c"],
            "d": last["c"] - prev,
            "dp": (last["c"] - prev) / prev * 100 if prev else 0,
            "t": None
        }
    elif not quote or quote.get("c") in (None, 0):
        return f"查無美股「{sym}」或目前無報價。"
        
    profile = S.finnhub(f"/stock/profile2?symbol={sym}") or {}
    metric = (S.finnhub(f"/stock/metric?symbol={sym}&metric=all") or {}).get("metric", {})
    recs = S.finnhub(f"/stock/recommendation?symbol={sym}") or []

    name = profile.get("name") or sym
    price = quote["c"]; chg = quote.get("d") or 0; chgp = quote.get("dp") or 0
    arrow = "🔺" if chg >= 0 else "🔻"

    # 盤中即時價＋時間，盤後收盤
    ms = S.us_market_status()
    if ms and ms.get("isOpen"):
        sess = {"regular": "盤中", "pre-market": "盤前", "post-market": "盤後延長"}.get(ms.get("session"), "盤中")
        pline = f"💰 現價 {price:.2f}　{chg:+.2f} ({chgp:+.2f}%) USD　⏱ {_fmt_et(quote.get('t'))}（{sess}）"
    else:
        pline = f"💰 收盤 {price:.2f}　{chg:+.2f} ({chgp:+.2f}%) USD"
    L = [f"🇺🇸 {sym} {name}　{arrow}", pline, "", "【技術面】"]

    sup = res = None
    if len(bars) >= 20:
        closes = [b["c"] for b in bars]; highs = [b["h"] for b in bars]
        lows = [b["l"] for b in bars]; vols = [b["vol"] for b in bars]
        ma = {p: sma(closes, p) for p in CFG["ma_periods"]}
        ks, ds = compute_kd(highs, lows, closes, CFG["kd_period"])
        k, d = ks[-1], ds[-1]; k0, d0 = ks[-2], ds[-2]
        win = bars[-20:]
        res = max(b["h"] for b in win); sup = min(b["l"] for b in win)
        ma_str = "　".join(f"MA{p} {ma[p]:.1f}{trend_arrow(price, ma[p])}" for p in CFG["ma_periods"] if ma.get(p))
        L.append(f"📊 均線 {ma_str}")
        L.append(f"📊 股價{'站上' if (ma.get(20) and price >= ma[20]) else '跌破'} MA20")
        L.append(f"📊 均線型態：{check_ma_status(ma)}")
        if k is not None:
            if k0 <= d0 and k > d: cross = "KD 黃金交叉（偏多）"
            elif k0 >= d0 and k < d: cross = "KD 死亡交叉（偏空）"
            elif k > 80: cross = "KD 高檔，注意回檔"
            elif k < 20: cross = "KD 低檔，留意反彈"
            else: cross = "KD 中性"
            L.append(f"📊 KD：K {k:.1f} / D {d:.1f}　{cross}")
        L.append(f"📊 壓力 {res:.2f}　支撐 {sup:.2f}（近20日）")
        avg20v = sma(vols, 20)
        if avg20v:
            vr = vols[-1] / avg20v
            vd = ("爆量" if vr >= 2 else "放量" if vr >= 1.5 else "量縮" if vr <= 0.6 else "正常")
            L.append(f"📦 今量 {vols[-1]/1e6:.1f}M股　20日均量 {avg20v/1e6:.1f}M　{vd} {vr:.1f}倍")
    else:
        L.append("📊 歷史資料不足，技術指標略")

    # 基本面
    L += ["", "【基本面】"]
    pe = metric.get("peTTM"); pb = metric.get("pbAnnual")
    dy = metric.get("dividendYieldIndicatedAnnual"); mc = metric.get("marketCapitalization")
    # EPS 用 現價÷本益比 推算（避免 Finnhub 對 BRK.B 等回傳 A 股 EPS 的股別錯誤）
    eps = price / pe if pe else metric.get("epsTTM")
    L.append(f"🏢 本益比 {_f(pe)}　淨值比 {_f(pb)}　EPS {_f(eps)}　殖利率 {_f(dy,'{:.2f}%')}")
    if mc:
        L.append(f"🏢 市值 {mc/1e6:.2f} 兆美元")
    # 52週優先用 Yahoo 歷史（股別正確），不用 Finnhub metric（BRK.B 會給 A 股區間）
    if len(bars) >= 200:
        w52h = max(b["h"] for b in bars); w52l = min(b["l"] for b in bars)
    else:
        w52h = metric.get("52WeekHigh"); w52l = metric.get("52WeekLow")
    if w52h and w52l and w52l <= price <= w52h * 1.5:
        pos = (price - w52l) / (w52h - w52l) * 100 if w52h != w52l else 0
        L.append(f"🏢 52週 {w52l:.2f} ~ {w52h:.2f}　現價位階 {pos:.0f}%")

    if recs:
        r0 = recs[0]
        sb, b, h, s, ss = (r0.get("strongBuy", 0), r0.get("buy", 0), r0.get("hold", 0),
                           r0.get("sell", 0), r0.get("strongSell", 0))
        bull = sb + b; bear = s + ss
        view = "偏多" if bull > h + bear else "偏空" if bear > bull else "中性"
        L.append(f"👨‍💼 分析師({r0.get('period','')[:7]})：買進{bull} 持有{h} 賣出{bear} → {view}")

    L += ["", "【操作建議｜僅供參考】"]
    if sup and res:
        ma20 = sma([b["c"] for b in bars], 20)
        entry_lo, entry_hi = sup, max(sup, ma20 or sup)
        if entry_hi < entry_lo: entry_lo, entry_hi = entry_hi, entry_lo
        bias = "偏多" if (ma20 and price >= ma20) else "偏空"
        L.append(f"🎯 研判：{bias}")
        if bias == "偏空":
            lo = round(sup * 0.98, 2)
            hi = round(sup * 1.02, 2)
            if hi > price: hi = min(hi, price)
            L.append(f"🟢 進場參考：{lo:.2f} ~ {hi:.2f} (左側低接) 或等站穩 MA20")
        else:
            L.append(f"🟢 進場參考區：{entry_lo:.2f} ~ {entry_hi:.2f}")
            
        L += [f"🔴 目標(壓力)：{res:.2f}",
              f"🛑 停損參考：{sup*0.97:.2f}"]
    else:
        L.append("🎯 資料不足，暫無進出場參考")
    return "\n".join(L)
