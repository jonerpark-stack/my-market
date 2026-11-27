import re, urllib.request, gzip
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def g(u):
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60) as r:
        b=r.read()
        if b[:2]==b'\x1f\x8b': b=gzip.decompress(b)
        return b.decode('utf-8','replace')
try:
    t=g("https://www.goldmansachs.com/sitemap-1.xml")
    locs=re.findall(r"<loc>([^<]+)</loc>",t)
    print("[PROBE] n",len(locs))
    tm=[x for x in locs if "top-of-mind" in x]
    print("[PROBE] tom", tm[:12])
    if tm:
        h=g(tm[-1]); print("[PROBE] pdfs", sorted(set(re.findall(r'[^"\'\s>]+\.pdf',h)))[:8])
except Exception as e: print("[PROBE] FAIL",e)
