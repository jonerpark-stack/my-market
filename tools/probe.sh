echo "=== deposit urls"; curl -s -L -m 20 -A "Mozilla/5.0" "https://finance.naver.com/sise/sise_deposit.naver" | grep -oE '(https?:)?//[a-zA-Z0-9./_-]*api[a-zA-Z0-9./_?=&-]*|"/api/[^"]*"|deposit[a-zA-Z]*' | sort -u | head -40
echo "=== deposit json?"; curl -s -L -m 20 -A "Mozilla/5.0" "https://finance.naver.com/sise/sise_deposit.naver" | grep -oE '고객예탁금[^<]{0,200}' | head -5
