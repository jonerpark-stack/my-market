"""Reddit 화제 종목 (ApeWisdom) → docs/reddit.json"""
import os, json, datetime as dt, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "reddit.json")
KST = dt.timezone(dt.timedelta(hours=9))

def run():
    rows = []
    for page in (1, 2):
        try:
            req = urllib.request.Request(f"https://apewisdom.io/api/v1.0/filter/all-stocks/page/{page}", headers={"User-Agent": "Mozilla/5.0"})
            j = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
        except Exception as e:
            print("[REDDIT] 실패", e); break
        for r in j.get("results", []):
            i = lambda k: int(r.get(k) or 0)
            rows.append({"t": r["ticker"], "n": r.get("name", ""), "rank": i("rank"), "rank24": i("rank_24h_ago"),
                         "m": i("mentions"), "m24": i("mentions_24h_ago"), "up": i("upvotes")})
    if rows:
        json.dump({"generated": dt.datetime.now(KST).isoformat(timespec="minutes"), "rows": rows}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[REDDIT] {len(rows)}종목")

if __name__ == "__main__":
    run()
