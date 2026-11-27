import urllib.request
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"en-US,en;q=0.9"}
T={
 "fed_rss":"https://www.federalreserve.gov/feeds/press_monetary.xml",
 "bis_rss":"https://www.bis.org/doclist/all_pubs.rss",
 "imf_rss":"https://www.imf.org/en/Publications/RSS?language=eng",
 "blk_weekly":"https://www.blackrock.com/corporate/insights/blackrock-investment-institute/publications/weekly-commentary",
 "jpm_gttm":"https://am.jpmorgan.com/content/dam/jpm-am-aem/global/en/insights/market-insights/guide-to-the-markets/mi-guide-to-the-markets-us.pdf",
 "gs_tom":"https://www.goldmansachs.com/insights/top-of-mind",
 "gs_rss":"https://www.goldmansachs.com/insights/rss.xml",
 "vanguard":"https://corporate.vanguard.com/content/corporatesite/us/en/corp/vemo/vemo-return-forecasts.html",
 "pimco":"https://www.pimco.com/us/en/insights",
 "ssga":"https://www.ssga.com/us/en/institutional/insights",
 "oecd_rss":"https://www.oecd.org/en/publications.rss",
 "naver_kospi":"https://finance.naver.com/sise/sise_index_day.naver?code=KOSPI",
 "naver_api":"https://m.stock.naver.com/api/index/KOSPI/price?pageSize=5&page=1",
}
for k,u in T.items():
    try:
        req=urllib.request.Request(u,headers=UA)
        with urllib.request.urlopen(req,timeout=30) as r:
            b=r.read(); print(f"[PROBE] {k}: {r.status} {len(b)}B lm={r.headers.get('Last-Modified')} {b[:120]!r}")
    except Exception as e: print(f"[PROBE] {k}: FAIL {e}")
