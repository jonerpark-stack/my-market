"""한국 시장: 업종 히트맵 · 투자자별 수급 · 상승/하락 종목 수 → docs/krmkt.json"""
import os, json, time, datetime as dt, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "krmkt.json")
HIST = os.path.join(ROOT, "data", "kr", "flows.json")
KST = dt.timezone(dt.timedelta(hours=9))
DETAIL_EVERY_MIN = 8

def get(path):
    req = urllib.request.Request("https://m.stock.naver.com" + path, headers={"User-Agent": "Mozilla/5.0"})
    for i in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            err = e; time.sleep(1)
    print("[KR] 실패", path, err); return None

def f(v):
    try: return float(str(v).replace(",", "").replace("+", ""))
    except Exception: return None

def pctrank(series, v):
    xs = [x for x in series if x is not None]
    if len(xs) < 20 or v is None: return None
    return round(100 * sum(1 for x in xs if x <= v) / len(xs))

def fear_greed(ih, out, hist):
    """구성 요소별 값을 최근 약 1년 분포에서 백분위(0~100)로 바꿔 평균. 높을수록 탐욕."""
    import statistics as st
    k = [c for _, c in ih.get("KOSPI", [])]; q = dict(ih.get("KOSDAQ", []))
    kd = [d for d, _ in ih.get("KOSPI", [])]
    if len(k) < 140: return None
    def series(fn, start):
        return [fn(i) for i in range(start, len(k))]
    mom = lambda i: k[i] / (sum(k[i - 124:i + 1]) / 125) - 1
    r20 = lambda i: k[i] / k[i - 20] - 1
    def vol(i):
        rs = [k[j] / k[j - 1] - 1 for j in range(i - 19, i + 1)]
        return st.pstdev(rs) * (252 ** 0.5)
    def rel(i):
        d, d0 = kd[i], kd[i - 20]
        if d not in q or d0 not in q: return None
        return (q[d] / q[d0]) - (k[i] / k[i - 20])
    parts = []
    def add(name, fn, start, inv, desc, fmt):
        ser = series(fn, start); v = ser[-1]; p = pctrank(ser, v)
        if p is None: return
        parts.append({"name": name, "val": fmt(v), "score": 100 - p if inv else p, "desc": desc})
    add("주가 모멘텀", mom, 124, False, "KOSPI가 125일 이동평균보다 얼마나 위에 있나", lambda v: f"{v*100:+.1f}%")
    add("단기 수익률", r20, 20, False, "KOSPI 최근 20거래일 수익률", lambda v: f"{v*100:+.1f}%")
    add("변동성", vol, 20, True, "20일 실현 변동성(연율). 높을수록 공포", lambda v: f"{v*100:.1f}%")
    add("위험 선호", rel, 20, False, "KOSDAQ 20일 수익률 − KOSPI. 소형주가 앞서면 탐욕", lambda v: f"{v*100:+.1f}%p" if v is not None else "-")
    try:
        rt = json.load(open(os.path.join(ROOT, "docs", "rates.json"), encoding="utf-8"))
        fx = [c for _, c in next(x for x in rt["items"] if x["code"] == "FX_USDKRW")["hist"] if c]
        if len(fx) > 40:
            ser = [fx[i] / fx[i - 20] - 1 for i in range(20, len(fx))]
            p = pctrank(ser, ser[-1])
            if p is not None: parts.append({"name": "환율", "val": f"{ser[-1]*100:+.1f}%", "score": 100 - p, "desc": "원/달러 20일 변화. 원화 약세일수록 공포 (약 6개월 분포 기준)"})
    except Exception: pass
    kp = out["idx"].get("KOSPI") or {}
    tot = (kp.get("up") or 0) + (kp.get("dn") or 0) + (kp.get("flat") or 0)
    if tot: parts.append({"name": "시장 폭", "val": f"상승 {kp['up']:.0f} / 하락 {kp['dn']:.0f}", "score": round(100 * kp["up"] / tot), "desc": "KOSPI 당일 상승 종목 비율 (백분위 아닌 비율 그대로)"})
    fh = [v.get("frg") for _, v in sorted((hist.get("KOSPI") or {}).items())][-5:]
    if len(fh) >= 5 and all(x is not None for x in fh):
        s5 = sum(fh); parts.append({"name": "외국인 수급", "val": f"{s5:+,.0f}억(5일)", "score": max(0, min(100, round(50 + s5 / 400))), "desc": "외국인 5거래일 순매수 합. ±2조원에서 0/100 (기록이 쌓이면 백분위로 전환)"})
    if not parts: return None
    sc = round(sum(p["score"] for p in parts) / len(parts))
    lab = "극단적 공포" if sc < 25 else "공포" if sc < 45 else "중립" if sc < 55 else "탐욕" if sc < 75 else "극단적 탐욕"
    # 과거 추이: 가격 기반 4개 요소만으로 재계산
    hs = []
    base = [(mom, 124, False), (r20, 20, False), (vol, 20, True), (rel, 20, False)]
    sers = [(series(fn, stt), stt, inv) for fn, stt, inv in base]
    for i in range(max(140, len(k) - 120), len(k)):
        sc_i = []
        for ser, stt, inv in sers:
            sub = ser[: i - stt + 1]; p = pctrank(sub, sub[-1])
            if p is not None: sc_i.append(100 - p if inv else p)
        if sc_i: hs.append([kd[i], round(sum(sc_i) / len(sc_i))])
    return {"score": sc, "label": lab, "parts": parts, "hist": hs}

def run():
    now = dt.datetime.now(KST)
    old = {}
    try: old = json.load(open(OUT, encoding="utf-8"))
    except Exception: pass
    out = {"generated": now.isoformat(timespec="minutes"), "idx": {}, "sectors": old.get("sectors", [])}
    hist = {}
    try: hist = json.load(open(HIST, encoding="utf-8"))
    except Exception: pass
    for m in ("KOSPI", "KOSDAQ"):
        b, it = get(f"/api/index/{m}/basic"), get(f"/api/index/{m}/integration")
        if not it: continue
        dtr, ud, pg = it.get("dealTrendInfo") or {}, it.get("upDownStockInfo") or {}, it.get("programTrendInfo") or {}
        row = {"price": (b or {}).get("closePrice"), "chg": (b or {}).get("fluctuationsRatio"), "date": dtr.get("bizdate"),
               "ind": f(dtr.get("personalValue")), "frg": f(dtr.get("foreignValue")), "ins": f(dtr.get("institutionalValue")),
               "prog": f(pg.get("indexTotalReal")),
               "up": f(ud.get("riseCount")), "upper": f(ud.get("upperCount")), "dn": f(ud.get("fallCount")), "lower": f(ud.get("lowerCount")), "flat": f(ud.get("steadyCount"))}
        out["idx"][m] = row
        if row["date"]:
            hist.setdefault(m, {})[row["date"]] = {k: row[k] for k in ("price", "chg", "ind", "frg", "ins", "prog", "up", "dn")}
            hist[m] = dict(sorted(hist[m].items())[-120:])
    out["hist"] = {m: [dict(d=k, **v) for k, v in sorted(h.items(), reverse=True)[:30]] for m, h in hist.items()}
    g = get("/api/stocks/industry?page=1&pageSize=100")
    if g and g.get("groups"):
        prev = {s["no"]: s for s in out["sectors"]}
        last = old.get("sector_detail_at", "")
        detail = not last or (now - dt.datetime.fromisoformat(last)).total_seconds() > DETAIL_EVERY_MIN * 60
        secs, allst = [], {}
        for x in g["groups"]:
            s = {"no": x["no"], "name": x["name"], "chg": f(x.get("changeRate")), "n": x.get("totalCount"),
                 "up": x.get("riseCount"), "dn": x.get("fallCount"), "stocks": prev.get(x["no"], {}).get("stocks", [])}
            if detail:
                st, pg = [], 1
                while pg <= 6:
                    d = get(f"/api/stocks/industry/{x['no']}?page={pg}&pageSize=100")
                    part = (d or {}).get("stocks") or []
                    st += part
                    if len(part) < 100: break
                    pg += 1; time.sleep(0.1)
                d = {"stocks": list(st)}
                for y in st:
                    allst[y.get("itemCode")] = [y.get("itemCode"), y.get("stockName"), f(y.get("fluctuationsRatio")), f(y.get("marketValue")),
                                                "Q" if str(y.get("sosok")) == "1" or (y.get("stockExchangeType") or {}).get("code") == "KQ" else "K", x["name"]]
                if st:
                    st = sorted(st, key=lambda y: -(f(y.get("marketValue")) or 0))[:12]
                    s["stocks"] = [{"c": y.get("itemCode"), "n": y.get("stockName"), "chg": f(y.get("fluctuationsRatio")), "mv": f(y.get("marketValue"))} for y in st]
                    s["mv"] = sum(f(y.get("marketValue")) or 0 for y in (d.get("stocks") or []))
                time.sleep(0.15)
            elif x["no"] in prev: s["mv"] = prev[x["no"]].get("mv")
            secs.append(s)
        out["sectors"] = secs
        for mk, tag in (("KOSPI", "K"), ("KOSDAQ", "Q")):
            for pg in (1, 2, 3):
                mv = get(f"/api/stocks/marketValue/{mk}?page={pg}&pageSize=100")
                for y in (mv or {}).get("stocks") or []:
                    if y.get("itemCode") in allst: allst[y["itemCode"]][4] = tag
        if allst: out["stocks"] = sorted(allst.values(), key=lambda y: -(y[3] or 0))
        elif old.get("stocks"): out["stocks"] = old["stocks"]
        out["sector_detail_at"] = now.isoformat(timespec="minutes") if detail else last
    # ---- 지수 일별 이력 (최근 약 1년) + 한국 공포·탐욕 지수
    ih = {}
    for m in ("KOSPI", "KOSDAQ"):
        rows = []
        for pg in range(1, 6):
            part = get(f"/api/index/{m}/price?page={pg}&pageSize=60") or []
            if isinstance(part, dict): part = part.get("result") or part.get("prices") or []
            rows += part
            if len(part) < 60: break
            time.sleep(0.1)
        ser = {}
        for r in rows:
            d0 = (r.get("localTradedAt") or r.get("bizdate") or "")[:10].replace("-", "")
            c = f(r.get("closePrice"))
            if d0 and c: ser[d0] = c
        ih[m] = sorted(ser.items())
    out["ihist"] = {m: v[-260:] for m, v in ih.items()}
    try:
        out["fg"] = fear_greed(ih, out, hist)
    except Exception as e:
        print("[KR] 공포탐욕 계산 실패", e)
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[KR] 지수 {list(out['idx'])} · 업종 {len(out['sectors'])} · 종목상세 {sum(1 for s in out['sectors'] if s.get('stocks'))}")

if __name__ == "__main__":
    run()
