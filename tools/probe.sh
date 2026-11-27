for u in \
 "https://m.stock.naver.com/front-api/marketIndex/productDetail?category=exchange&reutersCode=FX_USDKRW" \
 "https://m.stock.naver.com/front-api/marketIndex/prices?category=bond&reutersCode=US2YT%3DRR&page=1&pageSize=10" ; do
 echo "=== $u"; curl -s -m 15 -A "Mozilla/5.0" "$u" | head -c 1200; echo; done
