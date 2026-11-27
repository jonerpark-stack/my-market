for u in \
 "https://m.stock.naver.com/api/stock/005930/finance/quarter" \
 "https://m.stock.naver.com/api/stock/005930/price?pageSize=5&page=1" \
 "https://query1.finance.yahoo.com/v8/finance/chart/005930.KS?range=5d&interval=1d" \
 "https://api.stock.naver.com/chart/domestic/item/005930/week?startDateTime=202401010000&endDateTime=202611280000" ; do
 echo "=== $u"; curl -s -m 15 -A "Mozilla/5.0" "$u" | head -c 2500; echo; done
