"""금리 · 환율 보드 → docs/rates.json (네이버페이 증권 시장지표, 달러인덱스는 Yahoo)"""
import os, json, time, datetime as dt, urllib.request, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "rates.json")
KST = dt.timezone(dt.timedelta(hours=9))
ITEMS = [("bond", "KR3YT=RR", "국고채 3년", "%"), ("bond", "KR10YT=RR", "국고채 10년", "%"),
         ("bond", "US2YT=RR", "미 국채 2년", "%"), ("bond", "US10YT=RR", "미 국채 10년", "%"),
         ("exchange", "FX_USDKRW", "원/달러", "원"), ("exchange", "FX_JPYKRW", "원/엔(100엔)", "원"),
         ("exchange", "FX_EURKRW", "원/유로", "원"), ("exchange", "FX_CNYKRW", "원/위안", "원")]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for i in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            err = e; time.sleep(1)
    print("[RATE] 실패", url[:90], err); return None

f = lambda v: float(str(v).replace(",", "")) if v not in (None, "", "N/A") else None

def run():
    out = {"generated": dt.datetime.now(KST).isoformat(timespec="minutes"), "items": []}
    for cat, code, name, unit in ITEMS:
        q = urllib.parse.quote(code)
        d = (get(f"https://m.stock.naver.com/front-api/marketIndex/productDetail?category={cat}&reutersCode={q}") or {}).get("result") or {}
        h = (get(f"https://m.stock.naver.com/front-api/marketIndex/prices?category={cat}&reutersCode={q}&page=1&pageSize=60") or {}).get("result") or []
        hist = [[x["localTradedAt"][:10], f(x.get("closePrice"))] for x in h if x.get("closePrice")][::-1]
        out["items"].append({"code": code, "name": name, "unit": unit, "cat": cat, "price": f(d.get("closePrice")) or (hist[-1][1] if hist else None),
                             "chg": f(d.get("fluctuations")), "pct": f(d.get("fluctuationsRatio")), "at": d.get("localTradedAt", ""), "hist": hist})
        time.sleep(0.2)
    y = get("https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?range=3mo&interval=1d")
    try:
        r = y["chart"]["result"][0]; cl = r["indicators"]["quote"][0]["close"]
        hist = [[dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), round(c, 3)] for t, c in zip(r["timestamp"], cl) if c]
        p = r["meta"].get("regularMarketPrice") or hist[-1][1]; pc = hist[-2][1] if len(hist) > 1 else None
        out["items"].append({"code": "DXY", "name": "달러인덱스", "unit": "", "cat": "exchange", "price": p,
                             "chg": round(p - pc, 3) if pc else None, "pct": round((p / pc - 1) * 100, 2) if pc else None, "hist": hist[-60:]})
    except Exception as e:
        print("[RATE] DXY 실패", e)
    by = {x["code"]: x for x in out["items"]}
    def spread(a, b, nm):
        if by.get(a, {}).get("price") is None or by.get(b, {}).get("price") is None: return
        ha, hb = dict(by[a]["hist"]), dict(by[b]["hist"])
        hist = [[d, round((ha[d] - hb[d]) * 100, 1)] for d in sorted(set(ha) & set(hb))]
        out.setdefault("spreads", []).append({"name": nm, "bp": round((by[a]["price"] - by[b]["price"]) * 100, 1), "hist": hist})
    spread("US10YT=RR", "US2YT=RR", "미 10년-2년")
    spread("KR10YT=RR", "KR3YT=RR", "한 10년-3년")
    spread("KR3YT=RR", "US2YT=RR", "한 3년-미 2년")
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[RATE] {sum(1 for x in out['items'] if x['price'] is not None)}/{len(out['items'])}개 · 스프레드 {len(out.get('spreads', []))}")

if __name__ == "__main__":
    run()
