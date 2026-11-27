"""GURU 포트폴리오: SEC EDGAR 13F-HR 최근 2개 분기 비교 → docs/guru.json
SEC 공정 접근 규칙에 따라 User-Agent에 이름과 연락처를 밝히고, 초당 10회 미만으로 요청한다.
"""
import os, json, time, re, datetime as dt, urllib.request
import xml.etree.ElementTree as ET
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "guru.json")
KST = dt.timezone(dt.timedelta(hours=9))
UA = "JP INVESTMENT personal dashboard jonerpark-stack@users.noreply.github.com"
FUNDS = [("1067983", "Berkshire Hathaway", "워런 버핏"), ("1336528", "Pershing Square", "빌 애크먼"),
         ("1536411", "Duquesne Family Office", "스탠리 드러켄밀러"), ("1656456", "Appaloosa", "데이비드 테퍼"),
         ("1649339", "Scion Asset Mgmt", "마이클 버리"), ("1061768", "Baupost Group", "세스 클라만"),
         ("1709323", "Himalaya Capital", "리루"), ("1040273", "Third Point", "댄 로브"),
         ("1079114", "Greenlight Capital", "데이비드 아인혼"), ("1029160", "Soros Fund Mgmt", "조지 소로스"),
         ("1167483", "Tiger Global", "체이스 콜먼"), ("1135730", "Coatue", "필리프 라퐁"),
         ("1350694", "Bridgewater", "레이 달리오"), ("1061165", "Lone Pine", "스티븐 맨델")]

def get(url, raw=False):
    time.sleep(0.15)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=30) as r:
        b = r.read()
    return b if raw else json.loads(b.decode("utf-8"))

def holdings(cik, acc):
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}"
    idx = get(base + "/index.json")
    xmls = [f["name"] for f in idx["directory"]["item"] if f["name"].lower().endswith(".xml") and "primary_doc" not in f["name"].lower()]
    for nm in xmls:
        root = ET.fromstring(get(f"{base}/{nm}", raw=True))
        rows = [e for e in root.iter() if e.tag.split("}")[-1] == "infoTable"]
        if not rows: continue
        agg = {}
        for e in rows:
            g = lambda t: next((x.text for x in e.iter() if x.tag.split("}")[-1] == t), None)
            if (g("putCall") or "").strip(): continue   # 옵션 제외
            cu = g("cusip"); v = float(g("value") or 0); sh = float(g("sshPrnamt") or 0)
            a = agg.setdefault(cu, {"n": (g("nameOfIssuer") or "").strip().title(), "v": 0, "sh": 0, "cls": (g("titleOfClass") or "").strip()})
            a["v"] += v; a["sh"] += sh
        return agg
    return {}

def run():
    old = {}
    try: old = json.load(open(OUT, encoding="utf-8"))
    except Exception: pass
    if old.get("generated") and (dt.datetime.now(KST) - dt.datetime.fromisoformat(old["generated"])).total_seconds() < 12 * 3600:
        print("[GURU] 최근 계산본 유지"); return
    out = []
    for cik, name, who in FUNDS:
        try:
            sub = get(f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json")
            r = sub["filings"]["recent"]
            fl = [(r["accessionNumber"][i], r["reportDate"][i], r["filingDate"][i]) for i, f in enumerate(r["form"]) if f == "13F-HR"]
            seen, uniq = set(), []
            for a, rep, fd in fl:   # 같은 분기 중복(정정 전 원본) 제거
                if rep in seen: continue
                seen.add(rep); uniq.append((a, rep, fd))
            if not uniq: print("[GURU] 13F 없음", name); continue
            cur = holdings(cik, uniq[0][0]); prev = holdings(cik, uniq[1][0]) if len(uniq) > 1 else {}
            tot = sum(x["v"] for x in cur.values()) or 1
            rows = []
            for cu, x in cur.items():
                p = prev.get(cu); chg = None if not p or not p["sh"] else x["sh"] / p["sh"] - 1
                rows.append({"n": x["n"], "cu": cu, "w": round(x["v"] / tot * 100, 2), "v": x["v"], "sh": x["sh"],
                             "st": "new" if not p else "up" if chg and chg > 0.02 else "down" if chg is not None and chg < -0.02 else "same", "chg": round(chg * 100, 1) if chg is not None else None})
            sold = [{"n": p["n"], "cu": cu, "pw": round(p["v"] / (sum(y["v"] for y in prev.values()) or 1) * 100, 2)} for cu, p in prev.items() if cu not in cur]
            rows.sort(key=lambda x: -x["v"])
            out.append({"cik": cik, "fund": name, "who": who, "q": uniq[0][1], "filed": uniq[0][2], "pq": uniq[1][1] if len(uniq) > 1 else None,
                        "total": tot, "n": len(rows), "rows": rows[:60], "sold": sorted(sold, key=lambda x: -x["pw"])[:30]})
            print(f"[GURU] {name} {uniq[0][1]} 종목 {len(rows)} · 신규 {sum(1 for x in rows if x['st']=='new')} · 전량매도 {len(sold)}")
        except Exception as e:
            print("[GURU] 실패", name, type(e).__name__, str(e)[:120])
    if out:
        json.dump({"generated": dt.datetime.now(KST).isoformat(timespec="minutes"), "funds": out}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

if __name__ == "__main__":
    run()
