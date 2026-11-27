"""SHORT SQUEEZE 점수 백테스트 (과거 2년).

설계 (미래 정보 사용 방지):
- 관측 시점: FINRA 공매도 잔고 기준일(월 2회). 잔고는 기준일 약 8거래일 뒤 공개되므로
  '판정일' = 기준일 + 8거래일. 판정일 종가까지의 정보만 사용.
- 특징값(판정일 기준): 숏커버 일수, 잔고 증감률(직전 기준일 대비), 거래량 배수(5일/60일),
  5일 수익률, 잔고 금액. (Reddit·일별 공매도 비중은 과거 자료가 없어 제외)
- 점수: 같은 판정 시점의 종목들 안에서 각 특징의 백분위 → 가중평균(0~100). 현재 점수와 같은 방식.
- 결과: 판정일 종가 대비 이후 20거래일 최고 종가 수익률(최대 상승폭), 20거래일 뒤 수익률.
  '급등' = 최대 상승폭 +30% 이상.
- 한계: 현재 상장 종목만 사용(생존 편향), 거래비용 미반영.
"""
import bisect, json, random, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PX = ROOT / "data" / "bt" / "px"
SQH = ROOT / "docs" / "sqhist"
OUT = ROOT / "docs" / "backtest.json"
KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (JP INVESTMENT personal dashboard)"}
BUDGET = 150
W = {"dtc": .30, "sichg": .25, "surge": .20, "mom": .15, "sival": .10}
LAG, HORIZON, HIT = 8, 20, .30


def fetch_px(t):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=2y&interval=1d"
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
        j = json.loads(r.read())
    res = j["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    rows = [[datetime.fromtimestamp(ts, KST).date().isoformat(), c, v or 0]
            for ts, c, v in zip(res["timestamp"], q["close"], q["volume"]) if c]
    return rows


def collect():
    PX.mkdir(parents=True, exist_ok=True)
    tickers = sorted(f.stem for f in SQH.glob("*.json"))
    now = time.time()
    todo = [t for t in tickers if not (PX / f"{t}.json").exists()
            or now - (PX / f"{t}.json").stat().st_mtime > 7 * 86400][:BUDGET]
    for t in todo:
        try:
            (PX / f"{t}.json").write_text(json.dumps(fetch_px(t), separators=(",", ":")))
        except Exception as e:
            print(f"[BT] 가격 실패 {t}: {e}", file=sys.stderr)
        time.sleep(.12)
    have = sum(1 for t in tickers if (PX / f"{t}.json").exists())
    return have, len(tickers)


def pct(vals):
    s = sorted(v for v in vals if v is not None)
    n = len(s)
    return [None if v is None else 100 * bisect.bisect_left(s, v) / max(n - 1, 1) for v in vals]


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** .5) / d
    return [round(c - h, 4), round(c + h, 4)]


def compute():
    obs = {}  # 판정일 -> list of dict
    for f in SQH.glob("*.json"):
        t = f.stem
        pf = PX / f"{t}.json"
        if not pf.exists():
            continue
        si = json.loads(f.read_text())["si"]
        px = json.loads(pf.read_text())
        if len(px) < 120 or len(si) < 3:
            continue
        dates = [p[0] for p in px]
        for k in range(1, len(si)):
            sd, cur, dtc = si[k]
            prev = si[k - 1][1]
            i0 = bisect.bisect_right(dates, sd) - 1 + LAG       # 판정일 인덱스
            if i0 < 60 or i0 + HORIZON >= len(px):
                continue
            c0 = px[i0][1]
            v5 = sum(p[2] for p in px[i0 - 4:i0 + 1]) / 5
            v60 = (sum(p[2] for p in px[i0 - 59:i0 + 1]) / 60) or 1
            fut = [p[1] for p in px[i0 + 1:i0 + HORIZON + 1]]
            obs.setdefault(px[i0][0], []).append({
                "t": t, "dtc": dtc, "sichg": (cur / prev - 1) if prev else None,
                "surge": v5 / v60, "mom": c0 / px[i0 - 5][1] - 1, "sival": cur * c0,
                "maxup": max(fut) / c0 - 1, "r20": fut[-1] / c0 - 1})
    rows = []
    for d, lst in obs.items():
        if len(lst) < 30:
            continue
        ranks = {k: pct([o[k] for o in lst]) for k in W}
        for i, o in enumerate(lst):
            o["score"] = sum(W[k] * (ranks[k][i] or 0) for k in W)
            o["date"] = d
            rows.append(o)
    if not rows:
        return None

    def summ(sub):
        n = len(sub)
        k = sum(1 for o in sub if o["maxup"] >= HIT)
        mean = lambda key: round(sum(o[key] for o in sub) / n, 4) if n else None
        med = lambda key: round(sorted(o[key] for o in sub)[n // 2], 4) if n else None
        return {"n": n, "hit": round(k / n, 4) if n else None, "hit_ci": wilson(k, n),
                "maxup_mean": mean("maxup"), "r20_mean": mean("r20"), "r20_med": med("r20")}

    bands = [("70+", 70, 101), ("50~70", 50, 70), ("30~50", 30, 50), ("0~30", 0, 30)]
    res = {b: summ([o for o in rows if lo <= o["score"] < hi]) for b, lo, hi in bands}
    deciles = []
    for q in range(10):
        lo, hi = q * 10, (q + 1) * 10 + (1 if q == 9 else 0)
        deciles.append({"range": f"{q*10}~{(q+1)*10}", **summ([o for o in rows if lo <= o["score"] < hi])})
    # 날짜 단위 부트스트랩: 70+ 급등률 − 50 미만 급등률
    by_date = {}
    for o in rows:
        by_date.setdefault(o["date"], []).append(o)
    ds = list(by_date)
    random.seed(7)
    diffs = []
    for _ in range(1000):
        smp = [o for d in (random.choice(ds) for _ in ds) for o in by_date[d]]
        a = [o for o in smp if o["score"] >= 70]
        b = [o for o in smp if o["score"] < 50]
        if a and b:
            diffs.append(sum(o["maxup"] >= HIT for o in a) / len(a) - sum(o["maxup"] >= HIT for o in b) / len(b))
    diffs.sort()
    ci = [round(diffs[int(.025 * len(diffs))], 4), round(diffs[int(.975 * len(diffs))], 4)] if diffs else None
    return {"generated": datetime.now(KST).isoformat(timespec="seconds"),
            "dates": len(ds), "tickers": len({o["t"] for o in rows}), "obs": len(rows),
            "period": [min(ds), max(ds)], "hit_def": f"이후 {HORIZON}거래일 최고가 +{int(HIT*100)}% 이상",
            "lag": LAG, "weights": W, "all": summ(rows), "bands": res, "deciles": deciles,
            "diff_70_vs_50": {"est": round(res["70+"]["hit"] - summ([o for o in rows if o["score"] < 50])["hit"], 4)
                              if res["70+"]["n"] else None, "ci95": ci}}


def run():
    have, total = collect()
    print(f"[BT] 가격 수집 {have}/{total}")
    if total and have / total >= .9:
        if OUT.exists():
            try:
                if datetime.now(KST) - datetime.fromisoformat(json.loads(OUT.read_text())["generated"]) < timedelta(days=1):
                    return
            except Exception:
                pass
        r = compute()
        if r:
            OUT.write_text(json.dumps(r, ensure_ascii=False))
            print(f"[BT] 완료: 관측 {r['obs']}건, 시점 {r['dates']}개, 70+ 급등률 {r['bands']['70+']['hit']}")


if __name__ == "__main__":
    run()
