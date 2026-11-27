"""한국 종목 스크리너 → docs/screener.json
판정 (매 실행 일부 종목씩 채움, 가격은 하루 1회 + 장중 후보 1시간마다 갱신):
  1) 실적 관문: 최근 분기 영업이익이 3분기 연속 증가(4개 분기 비교) 또는 적자→흑자 전환
  2) 주봉 RSI(14)가 시그널선(RSI의 9주 단순이동평균)을 최근 2주 안에 상향 돌파
  가점: 돌파 시 RSI ≤ 50, 거래량 20주 평균의 1.2배 이상, 주봉 상승 다이버전스, 상승 캔들 패턴
  경고: 하락 캔들 패턴(주봉·일봉)
"""
import os, json, time, datetime as dt, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "screener.json")
CACHE = os.path.join(ROOT, "data", "scr")
KST = dt.timezone(dt.timedelta(hours=9))
MIN_MV = 1000          # 시총 1000억 이상
BUDGET = 260           # 실행당 종목 수 (종목당 2~3회 호출)
PX_FRESH_H = 18        # 가격 캐시 유효 시간
FIN_FRESH_D = 7        # 실적 캐시 유효 일수

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for i in range(2):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            time.sleep(0.5)
    return None

num = lambda v: None if v in (None, "", "-") else float(str(v).replace(",", ""))

def fetch_px(code, now):
    end = now.strftime("%Y%m%d") + "2359"
    w = get(f"https://api.stock.naver.com/chart/domestic/item/{code}/week?startDateTime={(now - dt.timedelta(days=1100)).strftime('%Y%m%d')}0000&endDateTime={end}")
    d = get(f"https://api.stock.naver.com/chart/domestic/item/{code}/day?startDateTime={(now - dt.timedelta(days=60)).strftime('%Y%m%d')}0000&endDateTime={end}")
    conv = lambda xs: [[x["localDate"], x["openPrice"], x["highPrice"], x["lowPrice"], x["closePrice"], x.get("accumulatedTradingVolume") or 0] for x in (xs or []) if x.get("closePrice")]
    if not w: return None
    return {"at": now.isoformat(), "w": conv(w), "d": conv(d)}

def fetch_fin(code, now):
    j = get(f"https://m.stock.naver.com/api/stock/{code}/finance/quarter")
    fi = (j or {}).get("financeInfo") or {}
    keys = [t["key"] for t in fi.get("trTitleList", []) if t.get("isConsensus") == "N"]
    rows = {r["title"]: r["columns"] for r in fi.get("rowList", [])}
    pick = lambda t: [num((rows.get(t, {}).get(k) or {}).get("value")) for k in keys]
    return {"at": now.isoformat(), "q": keys, "sales": pick("매출액"), "op": pick("영업이익"), "opm": pick("영업이익률")}

def rsi(cl, n=14):
    if len(cl) < n + 2: return []
    out = [None] * len(cl); g = l = 0.0
    for i in range(1, n + 1):
        ch = cl[i] - cl[i - 1]; g += max(ch, 0); l += max(-ch, 0)
    g /= n; l /= n; out[n] = 100 - 100 / (1 + g / l) if l else 100
    for i in range(n + 1, len(cl)):
        ch = cl[i] - cl[i - 1]; g = (g * (n - 1) + max(ch, 0)) / n; l = (l * (n - 1) + max(-ch, 0)) / n
        out[i] = 100 - 100 / (1 + g / l) if l else 100
    return out

def sma(xs, n):
    return [None if i < n - 1 or any(v is None for v in xs[i - n + 1:i + 1]) else sum(xs[i - n + 1:i + 1]) / n for i in range(len(xs))]

def candles(b):
    """b: [date,o,h,l,c,v] 목록 → (상승 패턴, 하락 패턴) 이름 목록. 교과서 정의 기준."""
    up, dn = [], []
    if len(b) < 8: return up, dn
    o, h, l, c = [x[1] for x in b], [x[2] for x in b], [x[3] for x in b], [x[4] for x in b]
    body = lambda i: abs(c[i] - o[i]); rng = lambda i: (h[i] - l[i]) or 1e-9
    upper = lambda i: h[i] - max(o[i], c[i]); lower = lambda i: min(o[i], c[i]) - l[i]
    bull = lambda i: c[i] > o[i]; bear = lambda i: c[i] < o[i]
    def trend(i):   # i 직전 5개 봉 추세: 종가가 5봉 평균보다 낮으면 하락
        p = c[i - 5:i]; return -1 if c[i - 1] < sum(p) / 5 and c[i - 1] < c[i - 5] else 1 if c[i - 1] > sum(p) / 5 and c[i - 1] > c[i - 5] else 0
    i = len(b) - 1; t = trend(i)
    small = body(i) <= rng(i) * 0.35
    if small and lower(i) >= 2 * max(body(i), rng(i) * 0.05) and upper(i) <= rng(i) * 0.15:
        (up if t < 0 else dn if t > 0 else []).append("망치형" if t < 0 else "교수형")
    if small and upper(i) >= 2 * max(body(i), rng(i) * 0.05) and lower(i) <= rng(i) * 0.15:
        (up if t < 0 else dn if t > 0 else []).append("역망치형" if t < 0 else "유성형")
    if bear(i - 1) and bull(i) and o[i] <= c[i - 1] and c[i] >= o[i - 1] and body(i) > body(i - 1) and t <= 0: up.append("상승장악형")
    if bull(i - 1) and bear(i) and o[i] >= c[i - 1] and c[i] <= o[i - 1] and body(i) > body(i - 1) and t >= 0: dn.append("하락장악형")
    tol = lambda a, x: abs(a - x) <= max(a, x) * 0.003
    if t < 0 and bear(i - 1) and bull(i) and tol(l[i], l[i - 1]): up.append("상승집게형")
    if t > 0 and bull(i - 1) and bear(i) and tol(h[i], h[i - 1]): dn.append("하락집게형")
    if bear(i - 1) and bull(i) and o[i] < l[i - 1] and c[i] > (o[i - 1] + c[i - 1]) / 2 and c[i] < o[i - 1] and t <= 0: up.append("관통형")
    if bull(i - 1) and bear(i) and o[i] > h[i - 1] and c[i] < (o[i - 1] + c[i - 1]) / 2 and c[i] > o[i - 1] and t >= 0: dn.append("먹구름형")
    j = i - 1; tt = trend(i - 1)
    if tt < 0 and bear(i - 2) and body(i - 2) > rng(i - 2) * 0.5 and body(j) <= rng(j) * 0.3 and max(o[j], c[j]) < c[i - 2] and bull(i) and c[i] > (o[i - 2] + c[i - 2]) / 2: up.append("샛별형")
    if tt > 0 and bull(i - 2) and body(i - 2) > rng(i - 2) * 0.5 and body(j) <= rng(j) * 0.3 and min(o[j], c[j]) > c[i - 2] and bear(i) and c[i] < (o[i - 2] + c[i - 2]) / 2: dn.append("석별형")
    return up, dn

def divergence(w, r):
    """최근 26주 안의 두 저점: 주가는 더 낮은데 RSI는 더 높으면 상승 다이버전스"""
    lows = [i for i in range(max(2, len(w) - 26), len(w) - 1) if w[i][3] <= w[i - 1][3] and w[i][3] <= w[i + 1][3] and w[i][3] <= w[i - 2][3] and r[i] is not None]
    if len(lows) < 2: return False
    a, b = lows[-2], lows[-1]
    return b - a >= 3 and w[b][3] < w[a][3] and r[b] > r[a] and r[b] < 45

def judge(code, px, fin):
    w = px["w"]
    if len(w) < 40: return None
    cl = [x[4] for x in w]; r = rsi(cl); sig = sma(r, 9)
    if r[-1] is None or sig[-1] is None: return None
    cross = None
    for k in (1, 2):
        if r[-k] is not None and sig[-k] is not None and r[-k - 1] is not None and sig[-k - 1] is not None and r[-k] > sig[-k] and r[-k - 1] <= sig[-k - 1]:
            cross = k; break
    near = cross is None and r[-1] <= sig[-1] and sig[-1] - r[-1] <= 2 and r[-1] > r[-2]
    op = [x for x in (fin or {}).get("op", [])]
    ops = [x for x in op if x is not None][-4:]
    improve = len(ops) == 4 and ops[1] < ops[2] < ops[3] and ops[0] < ops[1]
    turn = len(ops) >= 2 and ops[-1] > 0 and any(x <= 0 for x in ops[-3:-1])
    fund = improve or turn
    vol20 = sum(x[5] for x in w[-21:-1]) / 20 if len(w) > 21 else 0
    volx = (w[-1][5] / vol20) if vol20 else 0
    cu, cdn = candles(w)
    du, ddn = candles(px.get("d") or [])
    div = divergence(w, r)
    pts, why = 0, []
    if cross:
        why.append(f"주봉 RSI 시그널 상향 돌파({'이번 주' if cross == 1 else '지난주'})")
        rc = r[-cross]
        if rc <= 50: pts += 1; why.append(f"돌파 시 RSI {rc:.0f} ≤ 50")
    if volx >= 1.2: pts += 1; why.append(f"거래량 20주 평균의 {volx:.1f}배")
    if div: pts += 1; why.append("주봉 상승 다이버전스")
    if cu or du: pts += 1
    return {"c": code, "rsi": round(r[-1], 1), "sig": round(sig[-1], 1), "cross": cross, "near": near,
            "fund": fund, "fund_t": "3분기 연속 영업이익 증가" if improve else "영업이익 흑자 전환" if turn else "",
            "op": ops, "q": (fin or {}).get("q", [])[-4:], "volx": round(volx, 2), "div": div,
            "cu": cu, "cd": cdn, "du": du, "dd": ddn, "pts": pts, "why": why,
            "close": cl[-1], "wk": w[-1][0], "rs": [round(x, 1) if x is not None else None for x in r[-26:]], "sg": [round(x, 1) if x is not None else None for x in sig[-26:]]}

def run():
    now = dt.datetime.now(KST)
    try: kr = json.load(open(os.path.join(ROOT, "docs", "krmkt.json"), encoding="utf-8"))
    except Exception: print("[SCR] krmkt.json 없음"); return
    names = {y[0]: y for y in kr.get("stocks", [])}
    uni = [y[0] for y in kr.get("stocks", []) if (y[3] or 0) >= MIN_MV and not y[1].endswith(("우", "우B", "우C")) and "스팩" not in y[1]]
    os.makedirs(os.path.join(CACHE, "px"), exist_ok=True); os.makedirs(os.path.join(CACHE, "fin"), exist_ok=True)
    old = {}
    try: old = json.load(open(OUT, encoding="utf-8"))
    except Exception: pass
    prev = {x["c"]: x for x in old.get("all", [])}
    market_hours = now.weekday() < 5 and 9 <= now.hour < 16
    hot = {c for c, x in prev.items() if x.get("near") or x.get("cross")}
    def age_h(p):
        try: return (now - dt.datetime.fromisoformat(json.load(open(p, encoding="utf-8"))["at"])).total_seconds() / 3600
        except Exception: return 1e9
    todo = []
    for c in uni:
        pp = os.path.join(CACHE, "px", c + ".json")
        a = age_h(pp)
        if a > PX_FRESH_H or (market_hours and c in hot and a > 1): todo.append((0 if a > 1e8 else 1 if c in hot else 2, c))
    todo = [c for _, c in sorted(todo)][:BUDGET]
    t0 = time.time()
    for c in todo:
        if time.time() - t0 > 420: break
        px = fetch_px(c, now)
        if px: json.dump(px, open(os.path.join(CACHE, "px", c + ".json"), "w"))
        fp = os.path.join(CACHE, "fin", c + ".json")
        if age_h(fp) > FIN_FRESH_D * 24:
            fin = fetch_fin(c, now)
            if fin: json.dump(fin, open(fp, "w"))
        time.sleep(0.05)
    res = []
    for c in uni:
        try:
            px = json.load(open(os.path.join(CACHE, "px", c + ".json")))
        except Exception: continue
        try: fin = json.load(open(os.path.join(CACHE, "fin", c + ".json")))
        except Exception: fin = None
        try: j = judge(c, px, fin)
        except Exception: j = None
        if not j: continue
        y = names.get(c); j["n"] = y[1]; j["mv"] = y[3]; j["chg"] = y[2]; j["sec"] = y[5]; j["m"] = y[4]
        res.append(j)
    passed = sorted([x for x in res if x["fund"] and x["cross"]], key=lambda x: (-x["pts"], x["cross"], -x["mv"]))
    near = sorted([x for x in res if x["fund"] and x["near"]], key=lambda x: -x["mv"])[:30]
    slim = lambda x: {k: x[k] for k in ("c", "near", "cross")}
    keep = ("c", "rsi", "sig", "cross", "near", "fund", "fund_t", "op", "q", "volx", "div", "cu", "cd", "du", "dd", "pts", "why", "wk")
    json.dump({"generated": now.isoformat(timespec="minutes"), "rows": {x["c"]: {k: x[k] for k in keep} for x in res}},
              open(os.path.join(ROOT, "docs", "scr_all.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump({"generated": now.isoformat(timespec="minutes"), "universe": len(uni), "filled": len(res),
               "passed": passed, "near": near, "all": [slim(x) for x in res]}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[SCR] 대상 {len(uni)} · 판정 {len(res)} · 갱신 {len(todo)} · 통과 {len(passed)} · 근접 {len(near)} · {time.time() - t0:.0f}초")

if __name__ == "__main__":
    run()
