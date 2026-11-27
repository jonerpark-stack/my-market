"""데이터 출처 연결 점검 (임시)."""
import json, urllib.request, datetime as dt
UA={"User-Agent":"JPView personal dashboard jonerpark@users.noreply.github.com"}
def get(url, data=None, h=None):
    req=urllib.request.Request(url, data=data, headers={**UA, **(h or {})})
    with urllib.request.urlopen(req, timeout=40) as r: return r.status, r.read()
tests={}
d=dt.date.today()
for back in range(1,6):
    day=(d-dt.timedelta(days=back)).strftime("%Y%m%d")
    tests[f"regsho {day}"]=f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{day}.txt"
tests["finra api SI"]=("https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest",
    json.dumps({"limit":3}).encode(),{"Content-Type":"application/json","Accept":"application/json"})
tests["sec tickers"]="https://www.sec.gov/files/company_tickers.json"
tests["sec frames"]="https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/CY2026Q3I.json"
tests["yahoo chart"]="https://query1.finance.yahoo.com/v8/finance/chart/GME?range=1mo&interval=1d"
tests["apewisdom"]="https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"
tests["cnn fg"]=("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",None,{"User-Agent":"Mozilla/5.0"})
for k,v in tests.items():
    try:
        st,b = get(*v) if isinstance(v,tuple) else get(v)
        print(f"[PROBE] {k}: {st} {len(b)}B {b[:160]!r}")
    except Exception as e:
        print(f"[PROBE] {k}: FAIL {e}")
