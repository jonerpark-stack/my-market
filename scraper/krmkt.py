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
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[KR] 지수 {list(out['idx'])} · 업종 {len(out['sectors'])} · 종목상세 {sum(1 for s in out['sectors'] if s.get('stocks'))}")

if __name__ == "__main__":
    run()
