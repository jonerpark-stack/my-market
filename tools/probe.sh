echo "=== robots"; curl -s -m 20 -A "Mozilla/5.0" "https://www.dataroma.com/robots.txt" | head -c 600; echo
echo "=== managers"; curl -s -m 20 -A "Mozilla/5.0" -w "\nHTTP %{http_code}\n" "https://www.dataroma.com/m/managers.php" | grep -oE 'holdings.php\?m=[A-Za-z0-9]+">[^<]*' | head -80; 
echo "=== brk"; curl -s -m 20 -A "Mozilla/5.0" "https://www.dataroma.com/m/holdings.php?m=BRK" | sed 's/<[^>]*>/ /g' | tr -s ' \n\t' ' ' | head -c 2500; echo
echo "=== brkraw"; curl -s -m 20 -A "Mozilla/5.0" "https://www.dataroma.com/m/holdings.php?m=BRK" | grep -n "<tr" | head -5; curl -s -m 20 -A "Mozilla/5.0" "https://www.dataroma.com/m/holdings.php?m=BRK" | sed -n '/id="grid"/,/<\/table>/p' | head -c 3000
