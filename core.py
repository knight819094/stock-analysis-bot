#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心層：設定載入、SSL/HTTP（含退避重試）、數值/日期工具、技術指標。
此層不依賴專案內其他模組（最底層）。
"""
import json, os, ssl, time, urllib.request, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# ---------- SSL（python.org 版 macOS 不吃系統憑證，改用 certifi/系統 bundle）----------
def _certifi_path():
    try:
        import certifi; return certifi.where()
    except Exception:
        return None

def _make_ssl_context():
    for cafile in (_certifi_path(), "/etc/ssl/cert.pem"):
        if cafile and os.path.exists(cafile):
            try: return ssl.create_default_context(cafile=cafile)
            except Exception: pass
    return ssl.create_default_context()

SSL_CTX = _make_ssl_context()

# ---------- HTTP ----------
def http_json(url, retries=3, timeout=20, headers=None):
    """通用 GET → 解析 JSON。最後一次仍失敗會 raise。"""
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(1.5)
    return None

def twse_json(url, retries=5):
    """TWSE 專用：stat 非 OK（多半被限流）就退避重試，成功後稍歇避免爆量。"""
    for i in range(retries):
        try:
            d = http_json(url, retries=2)
        except Exception:
            d = None
        if d and d.get("stat") == "OK":
            time.sleep(0.7)
            return d
        time.sleep(1.2 * (i + 1))  # 退避：1.2,2.4,3.6...
    return None

# ---------- 數值 / 日期 ----------
def num(s):
    if s is None: return None
    s = str(s).replace(",", "").replace("+", "").strip()
    if s in ("", "-", "--", "X0.00", "null"): return None
    try: return float(s)
    except ValueError: return None

def roc_to_date(s):
    """'115/06/15' 或 '115年06月15日' → date"""
    s = s.replace("年", "/").replace("月", "/").replace("日", "")
    p = [x for x in s.split("/") if x]
    return datetime.date(int(p[0]) + 1911, int(p[1]), int(p[2]))

# ---------- 技術指標 ----------
def sma(vals, n):
    if len(vals) < n: return None
    return sum(vals[-n:]) / n

def compute_kd(highs, lows, closes, n=9):
    k, d = 50.0, 50.0
    ks, ds = [], []
    for i in range(len(closes)):
        if i < n - 1:
            ks.append(None); ds.append(None); continue
        hh = max(highs[i - n + 1:i + 1]); ll = min(lows[i - n + 1:i + 1])
        rsv = 50.0 if hh == ll else (closes[i] - ll) / (hh - ll) * 100
        k = 2/3 * k + 1/3 * rsv
        d = 2/3 * d + 1/3 * k
        ks.append(k); ds.append(d)
    return ks, ds

def trend_arrow(cur, ref):
    if cur is None or ref is None: return "➡️"
    if cur > ref * 1.001: return "🔺"
    if cur < ref * 0.999: return "🔻"
    return "➡️"
