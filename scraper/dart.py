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

def get(params):
    q = urllib.parse.urlencode(params)
    for i in range(3):
        try:
            with urllib.request.urlopen("https://opendart.fss.or.kr/api/list.json?" + q, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print("[DART] 재시도", e); time.sleep(2 + i * 3)
    return {}

def run():
    key = os.environ.get("DART_API_KEY")
    if not key:
        print("[DART] 키 없음 → 건너뜀"); return
    old = {}
    try: old = json.load(open(OUT, encoding="utf-8"))
    except Exception: pass
    items = {x["rno"]: x for x in old.get("items", [])}
    today = dt.datetime.now(KST).date()
    bgn = today - dt.timedelta(days=KEEP_DAYS if not items else 3)
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
                    "who": r.get("flr_nm", ""), "cat": c}
                n_new += 1
            if page >= int(d.get("total_page", 1)): break
            page += 1; time.sleep(0.3)
    cut = (today - dt.timedelta(days=KEEP_DAYS)).strftime("%Y%m%d")
    lst = sorted([x for x in items.values() if x["dt"] >= cut], key=lambda x: x["rno"], reverse=True)
    json.dump({"generated": dt.datetime.now(KST).isoformat(timespec="minutes"), "items": lst}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    cnt = {k: sum(1 for x in lst if x["cat"] == k) for k in ("insider", "buyback", "dilute", "earn")}
    print(f"[DART] 신규 {n_new}건 · 보관 {len(lst)}건 {cnt}")

if __name__ == "__main__":
    run()
