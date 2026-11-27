echo "=== naver deposit"; curl -s -L -m 20 -A "Mozilla/5.0" -w "\nHTTP %{http_code}\n" "https://finance.naver.com/sise/sise_deposit.naver" | iconv -f euc-kr -t utf-8 -c | sed 's/<[^>]*>/ /g' | tr -s ' \n\t' ' ' | head -c 1200; echo
echo "=== krx investor"; curl -s -m 20 -A "Mozilla/5.0" -H "Referer: https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd" \
 --data "bld=dbms/MDC/STAT/standard/MDCSTAT02201&locale=ko_KR&inqTpCd=1&trdVolVal=2&askBid=3&mktId=STK&strtDd=20261120&endDd=20261127&detailView=1" \
 "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd" | head -c 1500; echo
echo "=== krx lending"; curl -s -m 20 -A "Mozilla/5.0" -H "Referer: https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd" \
 --data "bld=dbms/MDC/STAT/srt/MDCSTAT30501&locale=ko_KR&searchType=1&mktId=STK&trdDd=20261126" \
 "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd" | head -c 800; echo
