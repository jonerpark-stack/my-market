"""미국 공포·탐욕 지수 (CNN과 같은 7개 구성을 공개 데이터로 직접 계산) → docs/usfg.json
각 요소를 최근 1년 분포 안 백분위(0 공포 ~ 100 탐욕)로 바꿔 평균. 데이터: Yahoo Finance 일봉.
  1 주가 모멘텀    S&P500이 125일 이동평균보다 얼마나 위에 있나
  2 주가 강도      11개 섹터 ETF의 52주 고가-저가 범위 내 평균 위치 (CNN: 52주 신고가-신저가 수 → 대체 지표)
  3 시장 폭        동일가중(RSP) - 시총가중(SPY) 20일 수익률 (CNN: 거래량 맥클렐런 → 대체 지표)
  4 풋/콜 비율     CBOE 풋/콜 5일 평균 (데이터를 못 받으면 제외)
  5 변동성         VIX가 50일 평균보다 얼마나 높은가 (높을수록 공포)
  6 정크본드 수요  하이일드(HYG) - 국채(IEF) 20일 수익률 차 (CNN: 정크-투자등급 스프레드 → 대체 지표)
  7 안전자산 수요  주식(SPY) - 장기국채(TLT) 20일 수익률 차
"""
import os, json, time, datetime as dt, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "usfg.json")
KST = dt.timezone(dt.timedelta(hours=9))
SECT = ["XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC"]

def yahoo(t):
    try:
        req = urllib.request.Request(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(t)}?range=2y&interval=1d", headers={"User-Agent": "Mozilla/5.0"})
        r = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))["chart"]["result"][0]
        q = r["indicators"]["quote"][0]
        return {dt.datetime.utcfromtimestamp(ts).strftime("%Y%m%d"): (h, l, c) for ts, h, l, c in zip(r["timestamp"], q["high"], q["low"], q["close"]) if c}
    except Exception as e:
        print("[USFG] 실패", t, e); return {}

def pct(ser, v):
    xs = [x for x in ser if x is not None]
    return None if len(xs) < 60 or v is None else round(100 * sum(1 for x in xs if x <= v) / len(xs))

def run():
    data = {t: yahoo(t) for t in ["^GSPC", "^VIX", "SPY", "TLT", "HYG", "IEF", "RSP", "^CPC"] + SECT}
    days = sorted(data["^GSPC"])
    if len(days) < 300: print("[USFG] 데이터 부족"); return
    c = lambda t, d: (data[t].get(d) or (None, None, None))[2]
    def ret(t, i, n=20):
        a, b = c(t, days[i]), c(t, days[i - n])
        return a / b - 1 if a and b else None
    def f_mom(i):
        xs = [c("^GSPC", d) for d in days[i - 124:i + 1]]
        return None if None in xs else xs[-1] / (sum(xs) / 125) - 1
    def f_str(i):
        ps = []
        for t in SECT:
            w = [data[t].get(d) for d in days[i - 251:i + 1]]
            w = [x for x in w if x]
            if len(w) < 200: continue
            hi, lo = max(x[0] for x in w), min(x[1] for x in w); ps.append((w[-1][2] - lo) / (hi - lo) if hi > lo else 0.5)
        return sum(ps) / len(ps) if ps else None
    def f_br(i):
        a, b = ret("RSP", i), ret("SPY", i); return a - b if a is not None and b is not None else None
    def f_pc(i):
        xs = [c("^CPC", d) for d in days[i - 4:i + 1]]
        return None if None in xs else sum(xs) / 5
    def f_vix(i):
        xs = [c("^VIX", d) for d in days[i - 49:i + 1]]
        return None if None in xs else xs[-1] / (sum(xs) / 50) - 1
    def f_junk(i):
        a, b = ret("HYG", i), ret("IEF", i); return a - b if a is not None and b is not None else None
    def f_safe(i):
        a, b = ret("SPY", i), ret("TLT", i); return a - b if a is not None and b is not None else None
    comps = [("주가 모멘텀", f_mom, False, "S&P500이 125일 이동평균보다 얼마나 위에 있나", "%"),
             ("주가 강도", f_str, False, "11개 섹터 ETF의 52주 고가·저가 범위 내 평균 위치 (CNN의 신고가-신저가 수 대체)", "pos"),
             ("시장 폭", f_br, False, "동일가중(RSP) − 시총가중(SPY) 20일 수익률. 종목 전반이 오르면 탐욕 (CNN의 거래량 지표 대체)", "%p"),
             ("풋/콜 비율", f_pc, True, "CBOE 풋/콜 5일 평균. 풋이 많을수록 공포", "x"),
             ("변동성", f_vix, True, "VIX가 50일 평균보다 얼마나 높은가. 높을수록 공포", "%"),
             ("정크본드 수요", f_junk, False, "하이일드(HYG) − 국채(IEF) 20일 수익률 차. 정크본드가 앞서면 탐욕 (CNN의 신용 스프레드 대체)", "%p"),
             ("안전자산 수요", f_safe, False, "주식(SPY) − 장기국채(TLT) 20일 수익률 차. 채권이 앞서면 공포", "%p")]
    start = 260; idx = range(start, len(days))
    sers = {}
    for name, fn, inv, desc, u in comps:
        sers[name] = [fn(i) for i in idx]
    fmt = lambda v, u: "-" if v is None else f"{v*100:+.1f}%" if u == "%" else f"{v*100:+.1f}%p" if u == "%p" else f"{v*100:.0f}%" if u == "pos" else f"{v:.2f}"
    parts = []
    for name, fn, inv, desc, u in comps:
        s = sers[name]; p = pct(s[-252:], s[-1])
        if p is None: continue
        parts.append({"name": name, "val": fmt(s[-1], u), "score": 100 - p if inv else p, "desc": desc})
    if not parts: print("[USFG] 계산 불가"); return
    sc = round(sum(x["score"] for x in parts) / len(parts))
    lab = "극단적 공포" if sc < 25 else "공포" if sc < 45 else "중립" if sc < 55 else "탐욕" if sc < 75 else "극단적 탐욕"
    hs = []
    names = [x["name"] for x in parts]; inv = {n: i for n, _, i, _, _ in comps}
    for k in range(max(252, len(idx) - 130), len(idx)):
        v = []
        for n in names:
            s = sers[n][k - 251:k + 1]; p = pct(s, s[-1])
            if p is not None: v.append(100 - p if inv[n] else p)
        if v: hs.append([days[start + k], round(sum(v) / len(v))])
    json.dump({"generated": dt.datetime.now(KST).isoformat(timespec="minutes"), "asof": days[-1], "score": sc, "label": lab, "parts": parts, "hist": hs},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[USFG] {sc} {lab} · 요소 {len(parts)}개")

if __name__ == "__main__":
    run()
