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
KEEP_DAYS = 183
FIRST_LIMIT = 400
SECTORS = ["반도체", "IT하드웨어·디스플레이", "2차전지", "자동차·부품", "조선·기계", "방산·우주", "전력·에너지·유틸리티",
           "건설·건자재", "화학·정유", "철강·소재", "금융·보험", "인터넷·게임·소프트웨어", "미디어·엔터", "통신",
           "바이오·헬스케어", "화장품·소비재", "유통·음식료", "운송·물류", "지주·기타", "해외주식", "매크로·전략·산업"]


UPLOAD_PER_RUN = 60
MAX_PDF_MB = 40
KDF_ITER = 200_000


def r2_client():
    need = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_URL", "REPORT_PASSWORD")
    if not all(os.environ.get(k) for k in need):
        return None
    import boto3
    return boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")


def enc_key(salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=KDF_ITER).derive(
        os.environ["REPORT_PASSWORD"].encode())


def upload_pdfs(items, meta):
    """PDF를 비밀번호로 암호화(AES-GCM)해 R2에 저장. 공개 주소로 받아도 비밀번호 없이는 못 읽음."""
    s3 = r2_client()
    if not s3:
        print("[DOC] R2 설정 없음 → PDF 저장 건너뜀")
        return
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import base64
    if not meta.get("kdf_salt"):
        meta["kdf_salt"] = base64.b64encode(os.urandom(16)).decode()
    key = enc_key(base64.b64decode(meta["kdf_salt"]))
    meta["kdf_iter"] = KDF_ITER
    todo = [x for x in items if x.get("file") and not x.get("enc") and not x.get("skip") and not x.get("too_big")][:UPLOAD_PER_RUN]
    if not todo:
        return
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    bucket, pub = os.environ["R2_BUCKET"], os.environ["R2_PUBLIC_URL"].rstrip("/")
    ok = 0
    with TelegramClient(StringSession(os.environ["TG_SESSION"]), int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]) as c:
        msgs = c.get_messages(CHANNEL, ids=[x["id"] for x in todo])
        for x, m in zip(todo, msgs):
            try:
                if not m or not m.document or m.document.size > MAX_PDF_MB * 1024 * 1024:
                    x["too_big"] = True
                    continue
                data = c.download_media(m, file=bytes)
                iv = os.urandom(12)
                blob = b"JPR1" + iv + AESGCM(key).encrypt(iv, data, None)
                k = f"reports/{x['id']}.bin"
                s3.put_object(Bucket=bucket, Key=k, Body=blob, ContentType="application/octet-stream")
                x["enc"] = f"{pub}/{k}"
                x["size"] = len(data)
                ok += 1
            except Exception as e:
                print(f"[DOC] 업로드 실패 {x['id']}: {e}", file=sys.stderr)
    print(f"[DOC] PDF 암호화 저장 {ok}/{len(todo)}건")


def r2_cleanup(keep_ids):
    s3 = r2_client()
    if not s3:
        return
    bucket = os.environ["R2_BUCKET"]
    try:
        resp = s3.list_objects_v2(Bucket=bucket, Prefix="reports/")
        for o in resp.get("Contents", []):
            rid = o["Key"].split("/")[-1].split(".")[0]
            if rid.isdigit() and int(rid) not in keep_ids:
                s3.delete_object(Bucket=bucket, Key=o["Key"])
    except Exception as e:
        print(f"[DOC] 정리 실패: {e}", file=sys.stderr)


def collect(last_id):
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    api_id, api_hash, sess = os.environ.get("TG_API_ID"), os.environ.get("TG_API_HASH"), os.environ.get("TG_SESSION")
    if not (api_id and api_hash and sess):
        print("[DOC] 텔레그램 키 없음 → 건너뜀 (" + ", ".join(f"{k}={'O' if os.environ.get(k) else 'X'}" for k in ("TG_API_ID", "TG_API_HASH", "TG_SESSION", "DART_API_KEY")) + ")")
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
    # 중복 제거: 같은 파일명 또는 같은 증권사+제목이면 하나만 남김 (PDF가 이미 저장된 것 우선, 그다음 먼저 올라온 것)
    norm = lambda v: re.sub(r"[\s_\-.,·()\[\]]+", "", (v or "").lower())
    seen, uniq = {}, []
    for x in sorted(lst, key=lambda x: (not x.get("enc"), x["id"])):
        keys = [k for k in ("f:" + norm(x.get("file")) if x.get("file") else None,
                            "t:" + norm(x.get("broker")) + norm(x.get("title")) if x.get("title") else None) if k and len(k) > 6]
        if any(k in seen for k in keys):
            continue
        for k in keys:
            seen[k] = 1
        uniq.append(x)
    if len(uniq) != len(lst):
        print(f"[DOC] 중복 {len(lst) - len(uniq)}건 제거")
    lst = sorted(uniq, key=lambda x: x["id"], reverse=True)
    meta = {k: old.get(k) for k in ("kdf_salt", "kdf_iter") if old.get(k)}
    try:
        upload_pdfs(lst, meta)
        if datetime.now(KST).hour == 4:
            r2_cleanup({x["id"] for x in lst})
    except Exception as e:
        print(f"[DOC] PDF 처리 오류: {e}", file=sys.stderr)
    OUT.write_text(json.dumps({"generated": datetime.now(KST).isoformat(timespec="seconds"), "sectors": SECTORS,
                               **meta, "items": lst}, ensure_ascii=False))
    print(f"[DOC] 신규 {len(new)}건 · 보관 {len(lst)}건 · 분류 {len(cls)}건")


if __name__ == "__main__":
    run()
