"""DOC_POOL(증권사 리포트 공유 채널) 수집 → 섹터 분류 → docs/reports.json
- 텔레그램 사용자 세션(TG_SESSION)으로 읽음. PDF 파일은 저장하지 않고 제목·출처·링크만 기록.
- Gemini로 증권사/종목/인뎁스 여부/제목/섹터를 추출 (요약은 하지 않음).
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "reports.json"
KST = timezone(timedelta(hours=9))
CHANNEL = "DOC_POOL"
KEEP_DAYS = 120
FIRST_LIMIT = 400
SECTORS = ["반도체", "IT하드웨어·디스플레이", "2차전지", "자동차·부품", "조선·기계", "방산·우주", "전력·에너지·유틸리티",
           "건설·건자재", "화학·정유", "철강·소재", "금융·보험", "인터넷·게임·소프트웨어", "미디어·엔터", "통신",
           "바이오·헬스케어", "화장품·소비재", "유통·음식료", "운송·물류", "지주·기타", "해외주식", "매크로·전략·산업"]


def collect(last_id):
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    api_id, api_hash, sess = os.environ.get("TG_API_ID"), os.environ.get("TG_API_HASH"), os.environ.get("TG_SESSION")
    if not (api_id and api_hash and sess):
        print("[DOC] 텔레그램 키 없음 → 건너뜀")
        return []
    out = []
    with TelegramClient(StringSession(sess), int(api_id), api_hash) as c:
        kw = {"min_id": last_id} if last_id else {"limit": FIRST_LIMIT}
        for m in c.iter_messages(CHANNEL, **kw):
            fname = None
            if m.document:
                for a in m.document.attributes:
                    if getattr(a, "file_name", None):
                        fname = a.file_name
            text = (m.message or "").strip()
            if not fname and not text:
                continue
            out.append({"id": m.id, "date": m.date.astimezone(KST).isoformat(timespec="minutes"),
                        "file": fname, "text": text[:500], "url": f"https://t.me/{CHANNEL}/{m.id}"})
    return out


PROMPT = """아래는 증권사 리포트 공유 채널의 게시물 목록이다(파일명과 본문 일부). 각 게시물을 분석해 JSON 배열로만 답하라.
각 원소: {"id": 숫자, "report": true/false(증권사·기관 리포트가 아니면 false), "broker": "증권사명(예: 미래에셋증권, KB증권; 모르면 빈 문자열)",
"target": "종목명(종목 리포트일 때) 또는 빈 문자열", "indepth": true/false(산업·전략 심층 리포트이면 true),
"title": "리포트 제목(파일명의 날짜·증권사·확장자 제거한 핵심 제목)", "sector": 아래 섹터 중 하나}
섹터: """ + ", ".join(SECTORS) + """
규칙: 종목이 속한 업종으로 섹터를 정할 것. 해외 기업 리포트는 '해외주식'. 거시경제·시황·전략은 '매크로·전략·산업'.
없는 정보는 지어내지 말 것.

[게시물]
"""


def classify(items):
    key = os.environ.get("GEMINI_API_KEY")
    if not key or not items:
        return {}
    res = {}
    for i in range(0, len(items), 25):
        batch = items[i:i + 25]
        lines = "\n".join(json.dumps({"id": x["id"], "file": x["file"], "text": x["text"][:300]}, ensure_ascii=False) for x in batch)
        body = {"contents": [{"parts": [{"text": PROMPT + lines}]}], "generationConfig": {"responseMimeType": "application/json"}}
        for model in [os.environ.get("GEMINI_MODEL"), "gemini-3.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash"]:
            if not model:
                continue
            try:
                req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                             data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json", "x-goog-api-key": key})
                with urllib.request.urlopen(req, timeout=120) as r:
                    txt = json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"]
                arr = json.loads(re.search(r"\[.*\]", txt, re.S).group(0))
                for a in arr:
                    if isinstance(a, dict) and "id" in a:
                        res[int(a["id"])] = a
                break
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    print(f"[DOC] 분류 실패: {e}", file=sys.stderr)
                    break
            except Exception as e:
                print(f"[DOC] 분류 오류: {e}", file=sys.stderr)
                break
    return res


import urllib.error  # noqa: E402


def run():
    old = {"items": []}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text())
        except Exception:
            pass
    items = {x["id"]: x for x in old.get("items", [])}
    last_id = max(items) if items else 0
    try:
        new = collect(last_id)
    except Exception as e:
        print(f"[DOC] 수집 실패: {e}", file=sys.stderr)
        return
    if new:
        for x in new[:3]:
            print("[DOC] 예시:", (x["file"] or "")[:80], "|", x["text"][:80].replace("\n", " "))
    todo = [x for x in new] + [x for x in items.values() if not x.get("sector")]
    cls = classify(todo[:200])
    for x in todo:
        c = cls.get(x["id"])
        if c:
            if not c.get("report", True):
                x["skip"] = True
            x.update({k: c.get(k) for k in ("broker", "target", "indepth", "title", "sector")})
        items[x["id"]] = x
    cutoff = (datetime.now(KST) - timedelta(days=KEEP_DAYS)).isoformat()
    lst = sorted((x for x in items.values() if x["date"] >= cutoff and not x.get("skip")), key=lambda x: x["id"], reverse=True)
    OUT.write_text(json.dumps({"generated": datetime.now(KST).isoformat(timespec="seconds"), "sectors": SECTORS, "items": lst},
                              ensure_ascii=False))
    print(f"[DOC] 신규 {len(new)}건 · 보관 {len(lst)}건 · 분류 {len(cls)}건")


if __name__ == "__main__":
    run()
