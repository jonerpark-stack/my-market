"""GURU 포트폴리오: 13F-HR 최근 2개 분기 비교 → docs/guru.json
SEC가 클라우드 서버 접속을 막아 13f.info(SEC 13F 정리 사이트, robots.txt 허용 경로)에서 받는다. 12시간에 한 번만 요청.
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

def page(url):
    time.sleep(0.5)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode("utf-8", "ignore")

def filings(cik):
    """13f.info 운용사 페이지 → [(분기 id, 분기 이름, 공시일)] 최신순"""
    url, h = page(f"https://13f.info/manager/{cik.zfill(10)}")
    out, seen = [], set()
    for fid, q in re.findall(r'href="/13f/(\d+)-[a-z0-9-]*-(q\d-\d{4})"', h):
        if q in seen: continue
        seen.add(q); out.append((fid, q.upper().replace("-", " ")))
    # 페이지 표시 순서가 최신순이 아닐 수 있어 분기로 정렬
    key = lambda x: (int(x[1][-4:]), int(x[1][1]))
    return sorted(out, key=key, reverse=True)

def holdings(fid):
    _, t = page(f"https://13f.info/data/13f/{fid}")
    agg = {}
    for r in json.loads(t)["data"]:
        tk, nm, cls, cu, v, pct, sh = r[:7]
        if len(r) > 7 and r[7]: continue   # 옵션(Put/Call) 제외
        a = agg.setdefault(cu, {"n": (nm or "").title(), "t": tk or "", "v": 0, "sh": 0})
        a["v"] += (v or 0) * 1000; a["sh"] += sh or 0
    return agg

def run():
    old = {}
    try: old = json.load(open(OUT, encoding="utf-8"))
    except Exception: pass
    if old.get("generated") and (dt.datetime.now(KST) - dt.datetime.fromisoformat(old["generated"])).total_seconds() < 12 * 3600:
        print("[GURU] 최근 계산본 유지"); return
    out = []
    for cik, name, who in FUNDS:
        try:
            uniq = filings(cik)
            if not uniq: print("[GURU] 13F 없음", name); continue
            cur = holdings(uniq[0][0]); prev = holdings(uniq[1][0]) if len(uniq) > 1 else {}
            tot = sum(x["v"] for x in cur.values()) or 1
            rows = []
            for cu, x in cur.items():
                p = prev.get(cu); chg = None if not p or not p["sh"] else x["sh"] / p["sh"] - 1
                rows.append({"n": x["n"], "t": x["t"], "cu": cu, "w": round(x["v"] / tot * 100, 2), "v": x["v"], "sh": x["sh"],
                             "st": "new" if not p else "up" if chg and chg > 0.02 else "down" if chg is not None and chg < -0.02 else "same", "chg": round(chg * 100, 1) if chg is not None else None})
            sold = [{"n": p["n"], "t": p["t"], "cu": cu, "pw": round(p["v"] / (sum(y["v"] for y in prev.values()) or 1) * 100, 2)} for cu, p in prev.items() if cu not in cur]
            rows.sort(key=lambda x: -x["v"])
            stale = int(uniq[0][1][-4:]) * 4 + int(uniq[0][1][1]) < (dt.datetime.now(KST).year * 4 + (dt.datetime.now(KST).month - 1) // 3 + 1) - 2
            out.append({"stale": stale, "cik": cik, "fund": name, "who": who, "q": uniq[0][1], "filed": "", "pq": uniq[1][1] if len(uniq) > 1 else None,
                        "total": tot, "n": len(rows), "rows": rows[:60], "sold": sorted(sold, key=lambda x: -x["pw"])[:30]})
            print(f"[GURU] {name} {uniq[0][1]} 종목 {len(rows)} · 신규 {sum(1 for x in rows if x['st']=='new')} · 전량매도 {len(sold)}")
        except Exception as e:
            print("[GURU] 실패", name, type(e).__name__, str(e)[:120])
    if out:
        json.dump({"generated": dt.datetime.now(KST).isoformat(timespec="minutes"), "funds": out}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

if __name__ == "__main__":
    run()
