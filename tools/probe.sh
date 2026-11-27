for o in STATSCU0100000060BO STATSCU0100000070BO; do
 echo "=== freesis $o"
 curl -s -m 20 -A "Mozilla/5.0" -H "Content-Type: application/json" -X POST "https://freesis.kofia.or.kr/meta/getMetaDataList.do" \
  --data "{\"dmSearch\":{\"tmpV40\":\"1000000\",\"tmpV41\":\"1\",\"tmpV1\":\"D\",\"tmpV45\":\"20261101\",\"tmpV46\":\"20261127\",\"OBJ_NM\":\"$o\"}}" | head -c 1500; echo
done
echo "=== krx"; curl -s -m 20 -A "Mozilla/5.0" -o /dev/null -w "%{http_code}\n" "https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd"
