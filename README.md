# kohelp

보안 CLI 도구의 `--help` / `man` 페이지를 한국어로 번역해 주는 CLI입니다.

```bash
kohelp nmap
kohelp sqlmap
kohelp hydra
```

KISA 보호나라 + NIST CSRC 데이터로 구축한 보안 전문용어 사전을 활용해 `exploit → 익스플로잇`, `payload → 페이로드`, `privilege escalation → 권한 상승` 같은 용어를 정확하게 번역합니다. `man` 페이지가 없는 도구는 `--help` 출력으로 자동 폴백합니다. 한 번 번역한 결과는 `~/.cache/kohelp`에 저장되어 다음 실행부터 바로 출력됩니다.

## 설치

Ubuntu/WSL 기준입니다.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv man-db
git clone https://github.com/YOUR_ID/kohelp.git
cd kohelp
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
```

설치 확인:

```bash
kohelp --help
```

## 첫 설정

설치 후 한 번 실행합니다.

```bash
kohelp --setting
```

이 명령은 다음을 확인합니다.

- `man` 명령 사용 가능 여부
- 가상환경 활성화 여부
- `json/security_terms_en_ko.json` 사전 파일 위치
- Gemini API 키 저장
- 캐시 디렉터리 생성

## API 키만 따로 등록

Gemini API 키를 한 번만 저장합니다.

```bash
kohelp --key "YOUR_GEMINI_API_KEY"
```

키는 `~/.config/kohelp/config.json`에 저장됩니다.

## 사용법

기본 사용:

```bash
kohelp nmap
```

다른 보안 도구:

```bash
kohelp sqlmap
kohelp hydra
kohelp gobuster
```

man section 지정:

```bash
kohelp -s 2 open
kohelp -s 5 passwd
```

캐시를 무시하고 다시 번역:

```bash
kohelp --refresh nmap
```

번역하지 않고 원문 출력만 확인:

```bash
kohelp --original nmap
```

진행 메시지 숨기기:

```bash
kohelp --quiet nmap
```

## 동작 방식

```text
kohelp nmap 입력
↓
man nmap 실행 시도 → 없으면 nmap --help 로 자동 폴백
↓
텍스트 수집
↓
Gemini API가 보안 전문용어 후보 추출
↓
json/security_terms_en_ko.json에서 후보 단어 조회
↓
조회된 한국어 전문용어를 번역 힌트로 주입 후 Gemini가 번역
↓
~/.cache/kohelp에 번역본 저장
↓
다음 실행부터 저장된 번역본 출력
```

## 파일 구조

```text
kohelp/
  kohelp.py
  pyproject.toml
  README.md
  json/
    security_terms_en_ko.json   # 보안 전문용어 사전 (443개)
    kisa_terms_ko.json          # KISA 원본 데이터
    nist_terms_en.json          # NIST 원본 데이터
  scripts/
    crawl_kisa.py               # KISA 크롤러
    build_security_glossary.py  # 용어 사전 생성 스크립트
```

## 캐시와 설정

API 키:

```text
~/.config/kohelp/config.json
```

번역 캐시:

```text
~/.cache/kohelp
```

캐시를 직접 삭제하려면:

```bash
rm -rf ~/.cache/kohelp
```

## 업데이트

GitHub에서 새 버전을 받은 뒤:

```bash
cd kohelp
git pull
. .venv/bin/activate
python3 -m pip install .
```
