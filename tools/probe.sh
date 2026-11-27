for u in \
 "https://finance.naver.com/sise/sise_group.naver?type=upjong" \
 "https://m.stock.naver.com/api/stocks/marketValue/KOSPI?page=1&pageSize=5" \
 "https://m.stock.naver.com/api/stocks/marketValue/KOSDAQ?page=1&pageSize=5" \
 "https://finance.naver.com/sise/sise_deposit.naver" \
 "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=20261127&sosok=" \
 "https://m.stock.naver.com/api/index/KOSPI/integration" \
 "https://finance.naver.com/sise/sise_group_detail.naver?type=upjong&no=278" ; do
 echo "=== $u"; curl -s -m 15 -A "Mozilla/5.0" "$u" | iconv -f euc-kr -t utf-8 -c 2>/dev/null | sed 's/<[^>]*>/ /g' | tr -s ' \n\t' ' ' | head -c 1500; echo; done
