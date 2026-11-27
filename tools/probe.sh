U="JP INVESTMENT jonerpark-stack@users.noreply.github.com"
curl -s -m 20 -A "$U" "https://13f.info/manager/0001067983-berkshire-hathaway-inc" > m.html; echo "=== size $(wc -c < m.html)"
echo "=== links"; grep -oE 'href="/13f/[^"]+"' m.html | head -5
L=$(grep -oE 'href="/13f/[^"]+"' m.html | head -1 | sed 's/href="//;s/"//'); echo "=== filing $L"
curl -s -m 20 -A "$U" "https://13f.info$L" > f.html; grep -oE '(data-url|href|src)="[^"]*(data|json|api)[^"]*"' f.html | head -10
echo "=== tbl"; sed 's/<[^>]*>/ /g' f.html | tr -s ' \n\t' ' ' | head -c 1500; echo
D=$(grep -oE '"/data/13f/[^"]+"' f.html | head -1 | tr -d '"'); echo "=== data $D"; [ -n "$D" ] && curl -s -m 20 -A "$U" "https://13f.info$D" | head -c 800
