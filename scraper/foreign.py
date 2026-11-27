"""해외 하우스뷰·공개 리포트 수집 + Gemini 한국어 요약 → docs/foreign.json"""
import base64, html as html_lib, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "foreign.json"
KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
REFRESH_HOURS = 3
MAX_SUMMARY_PER_RUN = 2
MAX_PDF_MB = 18


def _get(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers


def _abs(base, u):
    if u.startswith("http"):
        return u
    m = re.match(r"(https?://[^/]+)", base)
    return m.group(1) + u if u.startswith("/") else u


def src_blackrock():
    base = "https://www.blackrock.com/corporate/insights/blackrock-investment-institute/publications/weekly-commentary"
    html = _get(base)[0].decode("utf-8", "replace")
    out = []
    for u in sorted(set(re.findall(r'[^"\'\s]*weekly-investment-commentary-en-us-(\d{8})[^"\'\s]*\.pdf', html))):
        pass
    for full in sorted(set(re.findall(r'(?:https://www\.blackrock\.com)?/[^"\'\s]*weekly-investment-commentary-en-us-\d{8}[^"\'\s]*\.pdf', html))):
        d = re.search(r"en-us-(\d{8})-?([^/]*)\.pdf", full)
        slug = (d.group(2) or "").replace("-", " ").strip().capitalize()
        out.append({"id": "blk-" + d.group(1), "house": "BlackRock", "series": "Weekly Commentary",
                    "title": slug or "Weekly commentary", "date": f"{d.group(1)[:4]}-{d.group(1)[4:6]}-{d.group(1)[6:]}",
                    "url": _abs(base, full), "pdf": True, "page": base})
    return out


def src_jpm():
    url = ("https://am.jpmorgan.com/content/dam/jpm-am-aem/global/en/insights/market-insights/"
           "guide-to-the-markets/mi-guide-to-the-markets-us.pdf")
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as r:
        lm = r.headers.get("Last-Modified")
    d = parsedate_to_datetime(lm).astimezone(KST).date() if lm else datetime.now(KST).date()
    q = (d.month - 1) // 3 + 1
    return [{"id": f"jpm-gttm-{d.isoformat()}", "house": "J.P. Morgan AM", "series": "Guide to the Markets",
             "title": f"Guide to the Markets — {d.year} Q{q}", "date": d.isoformat(), "url": url, "pdf": True}]


def src_fed():
    xml = _get("https://www.federalreserve.gov/feeds/press_monetary.xml")[0].decode("utf-8-sig", "replace")
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S)[:12]:
        cd = lambda v: html_lib.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", v)).strip()
        t = cd(re.search(r"<title>(.*?)</title>", it, re.S).group(1))
        link = cd(re.search(r"<link>(.*?)</link>", it, re.S).group(1))
        pd = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        d = parsedate_to_datetime(pd.group(1)).astimezone(KST).date().isoformat() if pd else ""
        if not re.search(r"FOMC statement|Minutes of the Federal Open Market|economic projections", t, re.I):
            continue
        out.append({"id": "fed-" + re.sub(r"\W+", "", link)[-40:], "house": "Federal Reserve", "series": "FOMC",
                    "title": t, "date": d, "url": link, "pdf": False})
    return out


def src_generic(house, series, base, pattern):
    html = _get(base)[0].decode("utf-8", "replace").replace("\\/", "/")
    out = []
    for full in sorted(set(re.findall(r'(?:https?://[^"\'\s]+)?/[^"\'\s<>]*\.pdf', html))):
        if not re.search(pattern, full, re.I):
            continue
        name = re.sub(r"[-_]+", " ", full.rsplit("/", 1)[-1][:-4]).strip()
        dm = re.search(r"(20\d\d)[-_]?(\d\d)[-_]?(\d\d)?", full)
        d = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3) or '01'}" if dm else ""
        out.append({"id": house[:3].lower() + "-" + re.sub(r"\W+", "", full)[-50:], "house": house, "series": series,
                    "title": name[:90].capitalize(), "date": d, "url": _abs(base, full), "pdf": True})
    for x in out:
        if house == "Vanguard":
            y = re.search(r"(20\d\d)", x["url"])
            x["title"] = f"Vanguard Economic and Market Outlook {y.group(1) if y else ''}".strip()
            x["date"] = x["date"] or datetime.now(KST).date().isoformat()
            x["id"] = "van-" + (y.group(1) if y else "x")
    return out[-6:]


def src_gs():
    xml = _get("https://www.goldmansachs.com/sitemap-1.xml", timeout=60)[0]
    if xml[:2] == b"\x1f\x8b":
        import gzip
        xml = gzip.decompress(xml)
    xml = xml.decode("utf-8", "replace")
    ent = []
    for blk in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", blk)
        if not loc or "/insights/top-of-mind/" not in loc.group(1):
            continue
        lm = re.search(r"<lastmod>([^<]+)</lastmod>", blk)
        ent.append((lm.group(1)[:10] if lm else "", loc.group(1).strip()))
    ent.sort()
    out = []
    for d, u in ent[-4:]:
        slug = u.rstrip("/").rsplit("/", 1)[-1]
        out.append({"id": "gs-" + slug[:60], "house": "Goldman Sachs", "series": "Top of Mind",
                    "title": slug.replace("-", " ").capitalize(), "date": d, "url": u, "pdf": False})
    return out


SOURCES = [
    ("BlackRock", src_blackrock),
    ("J.P. Morgan", src_jpm),
    ("Fed", src_fed),
    ("Goldman Sachs", src_gs),
    ("Vanguard", lambda: src_generic("Vanguard", "Economic & Market Outlook",
                                     "https://corporate.vanguard.com/content/corporatesite/us/en/corp/vemo/vemo-return-forecasts.html", r"outlook|vemo|forecast")),
    ("State Street", lambda: src_generic("State Street GA", "Insights", "https://www.ssga.com/us/en/institutional/insights", r"outlook|market|macro")),
]

PROMPT = """너는 한국 투자자를 위한 리서치 번역·요약가다. 첨부 문서(해외 운용사/중앙은행 리포트)를 읽고 한국어로 정리하라.
- 핵심 결론 1~2문장으로 시작
- 이어서 중요한 주장·근거·수치를 불릿(•) 4~8개로 정리 (분량은 내용에 맞게 자유롭게)
- 자산배분·포지셔닝 의견(비중확대/축소 등)이 있으면 반드시 포함
- 한국 시장에 주는 시사점이 문서에 있으면 포함, 없으면 지어내지 말 것
- 문서에 없는 사실이나 수치를 만들지 말 것
- 일반 텍스트로만 답할 것 (마크다운 제목 금지)"""


def summarize(item):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    parts = [{"text": PROMPT + f"\n\n[출처] {item['house']} · {item['series']} · {item['title']} · {item['date']}"}]
    data = None
    if item["pdf"]:
        for u in (item["url"], item["url"].replace("/gls-download/literature/", "/corporate/literature/")):
            try:
                d, h = _get(u, timeout=90)
            except Exception:
                continue
            if d[:5] == b"%PDF-":
                data = d
                break
    if data and len(data) <= MAX_PDF_MB * 1024 * 1024:
        parts.append({"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(data).decode()}})
    else:  # PDF를 못 받으면 웹페이지 본문으로 요약
        page = item.get("page") or (None if item["pdf"] else item["url"])
        if not page:
            return None
        html = _get(page)[0].decode("utf-8", "replace")
        mm = re.search(r'href="(/monetarypolicy/fomcminutes\d+\.htm)"', html)
        if item["house"] == "Federal Reserve" and mm:  # 의사록 보도자료 → 의사록 본문으로 이동
            html = _get("https://www.federalreserve.gov" + mm.group(1))[0].decode("utf-8", "replace")
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        parts.append({"text": re.sub(r"\s+", " ", text)[:30000]})
    body = json.dumps({"contents": [{"parts": parts}]}).encode()
    for model in [os.environ.get("GEMINI_MODEL"), "gemini-3.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash"]:
        if not model:
            continue
        try:
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", data=body,
                headers={"Content-Type": "application/json", "x-goog-api-key": key})
            with urllib.request.urlopen(req, timeout=180) as r:
                j = json.loads(r.read())
            return {"text": j["candidates"][0]["content"]["parts"][0]["text"].strip(), "model": model}
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"[FOREIGN] 요약 실패 {item['id']} ({model}): {e} {e.read()[:300]!r}", file=sys.stderr)
                return None
    return None


import urllib.error  # noqa: E402


def run():
    old = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text())
            old = {x["id"]: x for x in prev.get("items", [])}
            g = datetime.fromisoformat(prev["generated"])
            pending = any(x.get("summary") is None for x in prev.get("items", []))
            if datetime.now(KST) - g < timedelta(hours=REFRESH_HOURS) and not pending:
                print("[FOREIGN] 최근 수집본 유지")
                return
        except Exception:
            pass
    items, status = {}, {}
    for name, fn in SOURCES:
        try:
            got = fn()
            status[name] = len(got)
            for x in got:
                x["summary"] = (old.get(x["id"]) or {}).get("summary")
                items[x["id"]] = x
        except Exception as e:
            status[name] = f"실패: {e}"
    for k, x in old.items():  # 소스에서 사라진 과거 항목도 보존 (최대 120일)
        if k not in items and x.get("date", "") >= (datetime.now(KST).date() - timedelta(days=120)).isoformat():
            items[k] = x
    lst = sorted(items.values(), key=lambda x: x.get("date", ""), reverse=True)[:80]
    budget = MAX_SUMMARY_PER_RUN
    for x in lst:
        if budget <= 0:
            break
        if x.get("summary") is None:
            try:
                x["summary"] = summarize(x)
            except Exception as e:
                print(f"[FOREIGN] 요약 오류 {x['id']}: {e}", file=sys.stderr)
            budget -= 1
    OUT.write_text(json.dumps({"generated": datetime.now(KST).isoformat(timespec="seconds"),
                               "status": status, "items": lst}, ensure_ascii=False))
    print(f"[FOREIGN] {len(lst)}건 · 출처별 {status}")


if __name__ == "__main__":
    run()
