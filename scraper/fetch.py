"""텔레그램 공개 채널 수집 + AI 코멘트 + 암호화 저장.

GitHub Actions에서 10분마다 실행된다.
환경변수:
  SITE_PASSWORD   (필수) 페이지 비밀번호 = 데이터 암호화 키
  AI_PROVIDER     openai | gemini | none   (기본 openai)
  OPENAI_API_KEY, OPENAI_MODEL  (기본 gpt-4o-mini)
  GEMINI_API_KEY, GEMINI_MODEL  (기본 gemini-2.0-flash)
"""
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
DATA_FILE = ROOT / "docs" / "data.enc.json"   # 비밀번호 사용 시
PLAIN_FILE = ROOT / "docs" / "data.json"      # 비밀번호 없이 사용 시
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"
PBKDF2_ITER = 200_000


# ---------------------------------------------------------------- 암호화
def _key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITER)
    return kdf.derive(password.encode("utf-8"))


def encrypt(obj, password: str) -> dict:
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_key(password, salt)).encrypt(iv, json.dumps(obj, ensure_ascii=False).encode(), None)
    b = lambda x: base64.b64encode(x).decode()
    return {"v": 1, "iter": PBKDF2_ITER, "salt": b(salt), "iv": b(iv), "ct": b(ct)}


def decrypt(env: dict, password: str):
    d = lambda k: base64.b64decode(env[k])
    key = _key(password, d("salt"))
    return json.loads(AESGCM(key).decrypt(d("iv"), d("ct"), None))


# ---------------------------------------------------------------- 수집
def http_get(url: str, data: bytes | None = None, headers: dict | None = None, timeout=30) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _text_with_breaks(el) -> str:
    for br in el.find_all("br"):
        br.replace_with("\n")
    return el.get_text().strip()


def parse_channel_html(html: str, channel: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    for m in soup.select("div.tgme_widget_message[data-post]"):
        data_post = m.get("data-post", "")
        try:
            msg_id = int(data_post.split("/")[-1])
        except ValueError:
            continue
        t = m.select_one(".tgme_widget_message_date time[datetime]") or m.select_one("time[datetime]")
        if not t:
            continue
        dt = datetime.fromisoformat(t["datetime"].replace("Z", "+00:00")).astimezone(KST)

        text_el = m.select_one(".tgme_widget_message_text")
        text = _text_with_breaks(text_el) if text_el else ""

        links = []
        if text_el:
            for a in text_el.select("a[href]"):
                href = a["href"]
                if href.startswith("http") and href not in links:
                    links.append(href)

        photos = []
        for p in m.select("a.tgme_widget_message_photo_wrap"):
            mt = re.search(r"url\(['\"]?(.*?)['\"]?\)", p.get("style", ""))
            if mt:
                photos.append(mt.group(1))

        docs = [d.get_text(strip=True) for d in m.select(".tgme_widget_message_document_title")]
        fwd = m.select_one(".tgme_widget_message_forwarded_from_name")

        if not text and not photos and not docs:
            continue
        posts.append({
            "uid": f"{channel}/{msg_id}",
            "channel": channel,
            "id": msg_id,
            "date": dt.isoformat(),
            "text": text,
            "links": links,
            "photos": photos[:4],
            "docs": docs,
            "forwarded": fwd.get_text(strip=True) if fwd else None,
            "url": f"https://t.me/{channel}/{msg_id}",
        })
    return posts


def fetch_channel(channel: str, pages: int = 1) -> list[dict]:
    out, before = [], None
    for _ in range(pages):
        url = f"https://t.me/s/{channel}" + (f"?before={before}" if before else "")
        html = http_get(url).decode("utf-8", "replace")
        got = parse_channel_html(html, channel)
        if not got:
            break
        out.extend(got)
        before = min(p["id"] for p in got)
        time.sleep(1)
    return out


def is_report(post: dict) -> bool:
    if post["docs"]:
        return True
    if any(re.search(r"\.pdf($|\?)", l, re.I) for l in post["links"]):
        return True
    return bool(re.search(r"(주간\s*전망|리포트|보고서|Weekly|목표주가|투자의견)", post["text"][:200]))


# ---------------------------------------------------------------- AI 코멘트
AI_PROMPT = """너는 거시경제·채권·주식 시장을 다루는 시니어 애널리스트다.
아래 텔레그램 시황 원문을 읽고, 개인 투자자가 놓치지 말아야 할 내용을 한국어로 정리하라.

규칙:
- 원문에 없는 수치나 사실을 만들어 내지 말 것.
- 원문이 아닌 너의 일반 지식에서 나온 설명에는 문장 끝에 [AI 일반지식]을 붙일 것.
- 최신 뉴스는 모른다는 전제로, 확인이 필요한 내용은 "확인 필요"라고 쓸 것.
- 각 항목은 1~2문장, 이모지로 시작.
- 반드시 아래 JSON 형식으로만 답할 것.

JSON 키 설명 (예시 문구를 그대로 쓰지 말고 원문 내용으로 채울 것):
- key: 🔑로 시작하는 핵심 요약 1문장
- watch: ⚠️로 시작하는 주목할 점 1~3개 배열
- background: 📚로 시작하는 배경지식 0~2개 배열
- implication: 🧭로 시작하는 시장 시사점 1문장

[채널] {channel}
[작성시각] {date}
[원문]
{text}"""


def _parse_ai_json(s: str) -> dict | None:
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return {
        "key": str(obj.get("key", ""))[:300],
        "watch": [str(x)[:300] for x in (obj.get("watch") or [])][:4],
        "background": [str(x)[:300] for x in (obj.get("background") or [])][:3],
        "implication": str(obj.get("implication", ""))[:300],
    }


def ai_comment(post: dict, channel_name: str) -> dict | None:
    provider = (os.environ.get("AI_PROVIDER") or "").lower()
    # Gemini 키만 있으면 자동으로 Gemini 사용 (OpenAI 키가 없을 때)
    if provider in ("", "openai") and not os.environ.get("OPENAI_API_KEY") and os.environ.get("GEMINI_API_KEY"):
        provider = "gemini"
    provider = provider or "openai"
    prompt = (AI_PROMPT.replace("{channel}", channel_name)
              .replace("{date}", post["date"][:16])
              .replace("{text}", post["text"][:6000]))
    try:
        if provider == "openai":
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                return None
            body = {
                "model": os.environ.get("OPENAI_MODEL") or "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }
            r = json.loads(http_get("https://api.openai.com/v1/chat/completions",
                                    json.dumps(body).encode(),
                                    {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                                    timeout=90))
            content = r["choices"][0]["message"]["content"]
            model = body["model"]
        elif provider == "gemini":
            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                return None
            # 모델이 종료되면 404 → 다음 후보로 자동 전환
            cands = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-3.5-flash-lite", "gemini-2.5-flash-lite",
                                 "gemini-2.5-flash", "gemini-flash-latest"] if m]
            body = {"contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"}}
            content, last = None, None
            for model in cands:
                try:
                    r = json.loads(http_get(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                        json.dumps(body).encode(),
                        {"Content-Type": "application/json", "x-goog-api-key": key}, timeout=90))
                    content = r["candidates"][0]["content"]["parts"][0]["text"]
                    break
                except urllib.error.HTTPError as e:
                    last = e
                    if e.code != 404:
                        raise
            if content is None:
                raise last or RuntimeError("사용 가능한 Gemini 모델 없음")
        else:
            return None
    except Exception as e:  # 네트워크/한도 오류 → 다음 실행에서 재시도
        print(f"[AI] {post['uid']} 실패: {e}", file=sys.stderr)
        return None
    parsed = _parse_ai_json(content)
    if parsed and ("핵심 한 줄" in parsed["key"] or len(parsed["key"]) < 12):
        return None
    if parsed:
        parsed["model"] = f"{provider}:{model}"
    return parsed


# ---------------------------------------------------------------- 메인
def main():
    password = os.environ.get("SITE_PASSWORD") or None

    state = {"posts": []}
    if not password and PLAIN_FILE.exists():
        state = json.loads(PLAIN_FILE.read_text(encoding="utf-8"))
    elif password and DATA_FILE.exists():
        try:
            state = decrypt(json.loads(DATA_FILE.read_text()), password)
        except Exception:
            print("기존 데이터 복호화 실패(비밀번호 변경?) → 새로 수집합니다.", file=sys.stderr)

    by_uid = {p["uid"]: p for p in state.get("posts", [])}
    for p in by_uid.values():  # 예시 문구를 그대로 베낀 불량 코멘트는 재생성
        if p.get("ai") and ("핵심 한 줄" in (p["ai"].get("key") or "") or len(p["ai"].get("key") or "") < 12):
            p["ai"] = None
    first_run = not by_uid
    names = {c["id"]: c["name"] for c in CONFIG["channels"]}

    for ch in CONFIG["channels"]:
        try:
            fetched = fetch_channel(ch["id"], pages=3 if first_run else 1)
        except Exception as e:
            print(f"[수집] {ch['id']} 실패: {e}", file=sys.stderr)
            continue
        for p in fetched:
            old = by_uid.get(p["uid"])
            if old:  # 수정된 글 반영, AI 코멘트는 유지
                p["ai"] = old.get("ai")
            p["report"] = is_report(p)
            by_uid[p["uid"]] = p
        print(f"[수집] {ch['id']}: {len(fetched)}건")

    cutoff = datetime.now(KST) - timedelta(days=CONFIG.get("retention_days", 90))
    posts = sorted((p for p in by_uid.values() if datetime.fromisoformat(p["date"]) >= cutoff),
                   key=lambda p: p["date"], reverse=True)

    # AI 코멘트: 코멘트 없는 최신 글부터 실행당 최대 N건 (비용·시간 제한)
    budget = CONFIG.get("ai_max_per_run", 6)
    ai_window = datetime.now(KST) - timedelta(days=CONFIG.get("ai_days", 3))
    for p in posts:
        if budget <= 0:
            break
        if p.get("ai") or len(p["text"]) < 80 or datetime.fromisoformat(p["date"]) < ai_window:
            continue
        p["ai"] = ai_comment(p, names.get(p["channel"], p["channel"]))
        budget -= 1

    out = {
        "updated": datetime.now(KST).isoformat(timespec="seconds"),
        "channels": CONFIG["channels"],
        "posts": posts,
    }
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if password:
        DATA_FILE.write_text(json.dumps(encrypt(out, password)))
        PLAIN_FILE.unlink(missing_ok=True)
    else:
        PLAIN_FILE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        DATA_FILE.unlink(missing_ok=True)
    print(f"[저장] 총 {len(posts)}건, 갱신 {out['updated']}")


if __name__ == "__main__":
    main()
    try:
        import importlib.util, pathlib
        for mod in ("squeeze",):
            f = pathlib.Path(__file__).with_name(mod + ".py")
            if f.exists():
                spec = importlib.util.spec_from_file_location(mod, f); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.run()
    except Exception as e:
        print(f"[EXTRA] 실패: {e}", file=sys.stderr)
