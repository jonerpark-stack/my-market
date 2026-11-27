"""미국 숏스퀴즈 후보 계산 → docs/squeeze.json
출처: FINRA 공매도 잔고(API), FINRA Reg SHO 일별 공매도 거래량, Yahoo 일봉, ApeWisdom(Reddit 언급).
GitHub Actions에서 fetch.py 실행 뒤 호출되며, 6시간에 한 번만 다시 계산한다.
"""
import json, math, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "squeeze.json"
KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (JPView personal dashboard)"}
REFRESH_HOURS = 6
N_PRICE = 250            # Yahoo 일봉을 받을 후보 수
W = {"dtc": .25, "sichg": .20, "svr": .15, "surge": .15, "mom": .10, "reddit": .10, "sival": .05}


def _get(url, data=None, headers=None, timeout=40):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def finra_si():
    api = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    date = None
    for back in range(0, 45):  # 최근 결제기준일 찾기 (월 2회)
        d = (datetime.now(KST).date() - timedelta(days=back)).isoformat()
        body = {"limit": 1, "compareFilters": [{"compareType": "EQUAL", "fieldName": "settlementDate", "fieldValue": d}]}
        try:
            if json.loads(_get(api, json.dumps(body).encode(), h) or b"[]"):
                date = d
                break
        except urllib.error.HTTPError as e:
            print("[SQUEEZE] FINRA 응답:", e.code, e.read()[:300])
            raise
    if not date:
        raise RuntimeError("FINRA 공매도 잔고 기준일을 찾지 못함")
    rows, off = [], 0
    while True:
        body = {"limit": 5000, "offset": off,
                "compareFilters": [{"compareType": "EQUAL", "fieldName": "settlementDate", "fieldValue": date}]}
        page = json.loads(_get(api, json.dumps(body).encode(), h, timeout=90) or b"[]")
        rows += page
        if len(page) < 5000:
            break
        off += 5000
        time.sleep(.5)
    return date, rows


def regsho(days=5):
    agg, dates, d = {}, [], datetime.now(KST).date()
    for back in range(1, 15):
        if len(dates) >= days:
            break
        day = (d - timedelta(days=back)).strftime("%Y%m%d")
        try:
            txt = _get(f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{day}.txt").decode()
        except Exception:
            continue
        dates.append(day)
        for line in txt.splitlines()[1:]:
            p = line.split("|")
            if len(p) < 5 or not p[1]:
                continue
            try:
                sv, tv = float(p[2]), float(p[4])
            except ValueError:
                continue
            a = agg.setdefault(p[1], [0.0, 0.0])
            a[0] += sv; a[1] += tv
    return (dates[0] if dates else None), {k: v[0] / v[1] for k, v in agg.items() if v[1] > 0}


def reddit():
    out = {}
    for page in (1, 2, 3):
        try:
            j = json.loads(_get(f"https://apewisdom.io/api/v1.0/filter/all-stocks/page/{page}"))
        except Exception:
            break
        for r in j.get("results", []):
            out[r["ticker"]] = (int(r.get("mentions") or 0), int(r.get("mentions_24h_ago") or 0), int(r.get("rank") or 0))
    return out


def yahoo(t):
    j = json.loads(_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=3mo&interval=1d"))
    r = j["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    c = [x for x in q["close"] if x is not None]
    v = [x or 0 for x in q["volume"]]
    if len(c) < 25:
        return None
    dv20 = sum(a * b for a, b in zip(c[-20:], v[-20:])) / 20
    v5, v60 = sum(v[-5:]) / 5, (sum(v[-60:]) / len(v[-60:])) or 1
    return {"price": c[-1], "ret1": c[-1] / c[-2] - 1, "ret5": c[-1] / c[-6] - 1,
            "dv20": dv20, "surge": v5 / v60, "name": r["meta"].get("longName") or r["meta"].get("shortName"),
            "itype": r["meta"].get("instrumentType")}


def pct_rank(vals):
    s = sorted(v for v in vals if v is not None)
    n = len(s)
    import bisect
    return [None if v is None else 100 * bisect.bisect_left(s, v) / max(n - 1, 1) for v in vals]


def build():
    si_date, si = finra_si()
    sho_date, svr = regsho()
    rd = reddit()
    base = []
    for r in si:
        t = r.get("symbolCode")
        cur, prev = r.get("currentShortPositionQuantity") or 0, r.get("previousShortPositionQuantity") or 0
        adv = r.get("averageDailyVolumeQuantity") or 0
        if not t or t not in svr or cur < 100_000 or adv < 50_000:   # 상장주(Reg SHO 존재)만, 극소형 제외
            continue
        dtc = cur / adv if adv else None
        chg = (cur / prev - 1) if prev else None
        base.append({"t": t, "si": cur, "si_prev": prev, "sichg": chg, "dtc": dtc, "adv": adv,
                     "svr": svr.get(t), "issue": r.get("issueName")})
    # 1차: 가격 없이 고를 후보 (숏커버 일수·증감·공매도비중 위주)
    for k in ("dtc", "sichg", "svr"):
        for b, p in zip(base, pct_rank([b[k] for b in base])):
            b["_" + k] = p or 0
    base.sort(key=lambda b: b["_dtc"] * .5 + b["_sichg"] * .3 + b["_svr"] * .2, reverse=True)
    cand = base[:N_PRICE]
    for t in rd:  # Reddit 상위 종목은 추가로 포함
        hit = next((b for b in base if b["t"] == t), None)
        if hit and hit not in cand:
            cand.append(hit)
    rows = []
    for b in cand:
        try:
            y = yahoo(b["t"])
        except Exception:
            y = None
        time.sleep(.15)
        if not y or y.get("itype") not in ("EQUITY", None):
            continue
        nm = (y.get("name") or b.get("issue") or "").lower()
        if any(w in nm for w in (" fund", "municipal", " etf", "autocallable", "income trust", " etn", "closed-end")):
            continue
        m = rd.get(b["t"])
        b.update(y)
        b["sival"] = b["si"] * y["price"]
        b["mom"] = y["ret5"]
        b["reddit"] = m[0] if m else 0
        b["reddit_prev"] = m[1] if m else 0
        rows.append(b)
    ranks = {k: pct_rank([r.get(k) for r in rows]) for k in W}
    for i, r in enumerate(rows):
        r["score"] = round(sum(W[k] * (ranks[k][i] or 0) for k in W), 1)
        sig = []
        if r["surge"] >= 2 and r["ret1"] >= .05: sig.append("거래량 급증 + 급등")
        if r["sichg"] is not None and r["sichg"] >= .2: sig.append(f"공매도 잔고 +{r['sichg']*100:.0f}%")
        if r["dtc"] and r["dtc"] >= 5: sig.append(f"숏커버 {r['dtc']:.1f}일")
        if r["reddit"] >= 20 and r["reddit"] >= 2 * max(r["reddit_prev"], 1): sig.append("Reddit 언급 급증")
        if (r.get("svr") or 0) >= .6: sig.append(f"공매도 거래 비중 {r['svr']*100:.0f}%")
        r["signals"] = sig
    rows.sort(key=lambda r: r["score"], reverse=True)
    keep = ["t", "name", "issue", "price", "ret1", "ret5", "dv20", "surge", "si", "si_prev", "sichg", "dtc", "svr",
            "sival", "reddit", "reddit_prev", "score", "signals"]
    return {"generated": datetime.now(KST).isoformat(timespec="seconds"), "si_date": si_date,
            "regsho_date": sho_date, "count": len(rows),
            "rows": [{k: (round(r[k], 4) if isinstance(r.get(k), float) else r.get(k)) for k in keep} for r in rows]}


def run():
    if OUT.exists():
        try:
            g = datetime.fromisoformat(json.loads(OUT.read_text())["generated"])
            if datetime.now(KST) - g < timedelta(hours=REFRESH_HOURS):
                print("[SQUEEZE] 최근 계산본 유지")
                return
        except Exception:
            pass
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False))
    print(f"[SQUEEZE] {data['count']}종목, 잔고 기준일 {data['si_date']}, 일별 {data['regsho_date']}")


if __name__ == "__main__":
    run()
