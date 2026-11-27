for u in \
 "https://m.stock.naver.com/api/stocks/industry?page=1&pageSize=5" \
 "https://m.stock.naver.com/api/stocks/industry/KOSPI?page=1&pageSize=5" \
 "https://m.stock.naver.com/front-api/stocks/industry?page=1&pageSize=5" \
 "https://m.stock.naver.com/api/stock/005930/integration" \
 "https://m.stock.naver.com/api/stock/005930/basic" \
 "https://m.stock.naver.com/api/index/KOSPI/integration" ; do
 echo "=== $u"; curl -s -m 15 -A "Mozilla/5.0" "$u" | head -c 2500; echo; done
