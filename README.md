# 📊 내 시황 — 텔레그램 시황·리포트 개인 대시보드

텔레그램 공개 채널을 10분마다 수집하고, 글마다 AI 코멘트를 붙여 모바일 웹으로 보여줍니다. 각 시황 카드의 💬 버튼으로 이모지 텍스트와 등락 차트 이미지를 카카오톡에 보낼 수 있습니다.
비용은 GitHub 무료이고, AI 코멘트만 API 사용량만큼 과금됩니다(Gemini를 쓰면 무료 한도 내 0원).

---

## 설치 (PC에서 한 번, 약 15분)

### 1) 저장소 만들기
1. github.com 가입 → 오른쪽 위 **+ → New repository**
2. 이름 예: `my-market` · **Public** 선택(무료 조건) → Create
3. **Add file → Upload files**에서 이 압축을 푼 폴더 안의 내용 전부(`.github` 폴더 포함)를 끌어다 놓고 **Commit**
   - `.github` 폴더가 안 올라가면: **Add file → Create new file**에서 파일명에 `.github/workflows/update.yml`을 입력하고 내용 붙여넣기

> 저장소는 공개지만 데이터는 비밀번호로 암호화되어 저장되므로, 남이 열어봐도 내용을 읽을 수 없습니다.

### 2) 비밀값 넣기
저장소 **Settings → Secrets and variables → Actions**

| 탭 | 이름 | 값 |
|---|---|---|
| Secrets | `SITE_PASSWORD` | 페이지 비밀번호 (길고 복잡하게) |
| Secrets | `OPENAI_API_KEY` | OpenAI API 키 (platform.openai.com → API keys) |
| Variables (선택) | `AI_PROVIDER` | `openai`(기본) / `gemini` / `none` |
| Variables (선택) | `OPENAI_MODEL` | 기본 `gpt-4o-mini` |
| Secrets (Gemini 사용 시) | `GEMINI_API_KEY` | aistudio.google.com에서 발급 |

OpenAI는 **Billing → Usage limits**에서 월 한도(예: $5)를 걸어 두면 초과 과금이 없습니다.

### 3) 페이지 켜기
**Settings → Pages** → Source: *Deploy from a branch* → Branch: `main` / 폴더: `/docs` → Save
1~2분 뒤 주소가 나옵니다: `https://<아이디>.github.io/my-market/`

### 4) 첫 실행
**Actions** 탭 → (처음이면 "I understand…" 활성화) → **시황 업데이트 → Run workflow**
초록 체크가 뜨면 페이지 주소에 접속해 비밀번호를 입력합니다.

### 5) 휴대폰 홈 화면에 추가
- 아이폰(Safari): 공유 → **홈 화면에 추가**
- 안드로이드(Chrome): ⋮ → **홈 화면에 추가**

---

## 사용법
- **상단 탭**: ✈️ 텔레그램 / 📄 리포트 → **아래 칩**: 전체 · 채널별 (숫자 = 안 읽은 글)
- **💬 카톡**: 미리보기에서 문구 수정 → AI 코멘트·차트 포함 여부 선택 → 보내기 → 카카오톡 선택
  - 카톡이 이미지와 글 중 하나만 받는 경우가 있어서, 글은 자동으로 클립보드에 복사됩니다. 입력창에서 **붙여넣기**하면 됩니다.
- **⚙️**: 강조 키워드 변경 / `로그아웃` 입력 시 저장된 비밀번호 삭제
- 화면은 열려 있는 동안 5분마다, 앱으로 돌아올 때마다 자동 갱신

## 채널 추가·변경
`config.json`의 `channels`에 한 줄 추가합니다. **공개 채널만** 가능합니다(`t.me/s/채널명`이 열려야 함).
```json
{ "id": "채널아이디", "name": "표시 이름", "emoji": "📈", "source": "telegram" }
```

## 알아둘 점
- GitHub 예약 실행은 지연이 잦아 실제 간격은 10~20분 정도입니다.
- 비밀번호를 바꾸면 기존 데이터를 열 수 없으므로 최근 글부터 새로 수집합니다.
- AI 코멘트는 원문 기준이며 최신 뉴스를 모릅니다. `[AI 일반지식]` 표시는 원문에 없는 설명입니다. 투자 판단은 원문으로 확인하세요.
- 원문 전체를 외부로 퍼나르면 채널 운영 규칙이나 저작권 문제가 생길 수 있습니다. 요약과 링크 위주로 공유하세요.
- 차트는 원문에서 `+1.2%`, `▼0.3%`처럼 부호가 붙은 등락률을 자동으로 뽑아 만듭니다. 2개 미만이면 텍스트만 보냅니다.
