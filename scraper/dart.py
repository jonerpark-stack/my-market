"""DART 공시 수집: 내부자 매매 · 자사주 · 희석(증자/CB/BW) · 잠정실적 → docs/dart.json"""
import os, json, time, datetime as dt, urllib.request, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "dart.json")
KEEP_DAYS = 30
KST = dt.timezone(dt.timedelta(hours=9))

def cat_of(nm):
    n = nm.replace(" ", "")
    if "잠정" in n and "실적" in n: return "earn"
    if "자기주식" in n: return "buyback"
    if any(k in n for k in ("유상증자결정", "전환사채권발행결정", "신주인수권부사채권발행결정", "교환사채권발행결정", "전환가액의조정")): return "dilute"
    if ("임원" in n and "소유상황" in n) or "대량보유상황" in n: return "insider"
    return None

def get(params, ep="list"):
    q = urllib.parse.urlencode(params)
    for i in range(3):
        try:
            with urllib.request.urlopen(f"https://opendart.fss.or.kr/api/{ep}.json?" + q, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print("[DART] 재시도", e); time.sleep(2 + i * 3)
    return {}

DET_BUDGET = 150
SKIP = {"rcept_no", "rcept_dt", "corp_code", "corp_name", "corp_cls", "status", "message"}
def ep_of(nm):
    n = nm.replace(" ", "")
    if "대량보유" in n: return "majorstock", False
    if "임원" in n and "소유상황" in n: return "elestock", False
    if "자기주식취득신탁" in n: return "tsstkAqTrctrCnsDecsn", True
    if "자기주식신탁계약해지" in n or "자기주식취득신탁계약해지" in n: return "tsstkAqTrctrCcDecsn", True
    if "자기주식처분" in n: return "tsstkDpDecsn", True
    if "자기주식취득결정" in n: return "tsstkAqDecsn", True
    if "유상증자" in n: return "piicDecsn", True
    if "전환사채" in n and "발행" in n: return "cvbdIsDecsn", True
    if "신주인수권부사채" in n: return "bdwtIsDecsn", True
    if "교환사채" in n: return "exbdIsDecsn", True
    return None, False

def fill_details(key, items):
    todo = [x for x in sorted(items.values(), key=lambda x: x["rno"], reverse=True)
            if x["cat"] in ("insider", "buyback", "dilute") and "det" not in x and x.get("cc")]
    calls, cache, n = 0, {}, 0
    for x in todo:
        ep, dated = ep_of(x["nm"])
        if not ep:
            x["det"] = None; continue
        ck = (ep, x["cc"]) if not dated else (ep, x["cc"], x["dt"])
        if ck not in cache:
            if calls >= DET_BUDGET: break
            p = {"crtfc_key": key, "corp_code": x["cc"]}
            if dated: p.update(bgn_de=x["dt"], end_de=x["dt"])
            d = get(p, ep); calls += 1; time.sleep(0.15)
            cache[ck] = d.get("list", []) if d.get("status") == "000" else []
            if d.get("status") not in ("000", "013"): print("[DART] 상세", ep, d.get("status"), d.get("message"))
        rows = [r for r in cache[ck] if r.get("rcept_no") == x["rno"]]
        if not rows and calls >= DET_BUDGET: break
        x["det"] = {k: v for k, v in rows[0].items() if k not in SKIP and v not in (None, "", "-")} if rows else None
        n += bool(rows)
    left = sum(1 for x in items.values() if x["cat"] in ("insider", "buyback", "dilute") and "det" not in x)
    print(f"[DART] 상세 {n}건 채움 · 호출 {calls} · 남은 {left}")

def run():
    key = os.environ.get("DART_API_KEY")
    if not key:
        print("[DART] 키 없음 → 건너뜀"); return
    old = {}
    try: old = json.load(open(OUT, encoding="utf-8"))
    except Exception: pass
    items = {x["rno"]: x for x in old.get("items", [])}
    today = dt.datetime.now(KST).date()
    full = not items or any("cc" not in x for x in items.values())
    if full: items = {}
    bgn = today - dt.timedelta(days=KEEP_DAYS if full else 3)
    n_new = 0
    for ty in ("B", "D", "I"):
        page = 1
        while page <= 60:
            d = get({"crtfc_key": key, "bgn_de": bgn.strftime("%Y%m%d"), "end_de": today.strftime("%Y%m%d"),
                     "pblntf_ty": ty, "page_no": page, "page_count": 100})
            if d.get("status") not in ("000",):
                if d.get("status") != "013": print("[DART]", ty, d.get("status"), d.get("message"))
                break
            for r in d.get("list", []):
                if r.get("corp_cls") not in ("Y", "K"): continue
                c = cat_of(r.get("report_nm", ""))
                if not c or r["rcept_no"] in items: continue
                items[r["rcept_no"]] = {"rno": r["rcept_no"], "dt": r["rcept_dt"], "corp": r["corp_name"], "code": r.get("stock_code", ""),
                    "mkt": "KOSPI" if r["corp_cls"] == "Y" else "KOSDAQ", "nm": " ".join(r["report_nm"].split()),
                    "who": r.get("flr_nm", ""), "cat": c, "cc": r.get("corp_code", "")}
                n_new += 1
            if page >= int(d.get("total_page", 1)): break
            page += 1; time.sleep(0.3)
    fill_details(key, items)
    cut = (today - dt.timedelta(days=KEEP_DAYS)).strftime("%Y%m%d")
    lst = sorted([x for x in items.values() if x["dt"] >= cut], key=lambda x: x["rno"], reverse=True)
    json.dump({"generated": dt.datetime.now(KST).isoformat(timespec="minutes"), "items": lst}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    cnt = {k: sum(1 for x in lst if x["cat"] == k) for k in ("insider", "buyback", "dilute", "earn")}
    print(f"[DART] 신규 {n_new}건 · 보관 {len(lst)}건 {cnt}")

if __name__ == "__main__":
    run()
