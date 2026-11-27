import re, urllib.request, gzip
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def g(u):
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=40) as r:
        b=r.read()
        if b[:2]==b'\x1f\x8b': b=gzip.decompress(b)
        return b.decode('utf-8','replace')
for u in ["https://www.goldmansachs.com/robots.txt","https://www.goldmansachs.com/sitemap.xml"]:
    try:
        t=g(u); print("[PROBE]",u,len(t)); print("[PROBE]", re.findall(r"https?://[^\s<]*sitemap[^\s<]*",t)[:15])
        print("[PROBE] tom:", [x for x in re.findall(r"<loc>([^<]+)</loc>",t) if "top-of-mind" in x][:10])
    except Exception as e: print("[PROBE]",u,"FAIL",e)
try:
    t=g("https://www.goldmansachs.com/insights/top-of-mind")
    print("[PROBE] tom links:", sorted(set(re.findall(r'/insights/top-of-mind/[a-z0-9\-]+', t)))[:15])
    print("[PROBE] pdf:", sorted(set(re.findall(r'[^"\'\s]+\.pdf', t)))[:10])
    print("[PROBE] gsr:", sorted(set(re.findall(r'/(?:pdfs|insights)/[^"\'\s]*top[^"\'\s]*', t)))[:15])
except Exception as e: print("[PROBE] tom FAIL", e)
