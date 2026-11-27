for u in \
 "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2" \
 "https://m.stock.naver.com/front-api/marketIndex/productDetail?category=bond&reutersCode=KR3YT%3DRR" \
 "https://m.stock.naver.com/front-api/marketIndex/prices?category=bond&reutersCode=KR3YT%3DRR&page=1&pageSize=5" \
 "https://m.stock.naver.com/front-api/marketIndex/prices?category=bond&reutersCode=KR10YT%3DRR&page=1&pageSize=5" \
 "https://m.stock.naver.com/front-api/marketIndex/prices?category=exchange&reutersCode=FX_USDKRW&page=1&pageSize=5" \
 "https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=5d&interval=1d" \
 "https://finance.naver.com/sise/sise_deposit.naver" \
 "https://m.stock.naver.com/front-api/marketIndex/bondList" ; do
 echo "=== $u"; curl -s -m 15 -A "Mozilla/5.0" "$u" | tail -c 900; echo; done
