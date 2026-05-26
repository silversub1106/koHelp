# kohelp

Linux `man` 페이지를 한국어로 번역해 주는 CLI입니다.

```bash
kohelp ls
kohelp grep
kohelp -s 2 open
```

내부적으로 `man ls`를 실행해 나온 원문을 Gemini API로 번역하고, `json/tta_terms_en_ko_clean.json` 전문용어 사전을 함께 사용합니다. 한 번 번역한 결과는 `~/.cache/kohelp`에 저장되어 다음 실행부터 바로 출력됩니다.

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
- `json/tta_terms_en_ko_clean.json` 사전 파일 위치
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
kohelp ls
```

다른 명령어:

```bash
kohelp grep
kohelp find
kohelp tar
```

man section 지정:

```bash
kohelp -s 2 open
kohelp -s 5 passwd
```

캐시를 무시하고 다시 번역:

```bash
kohelp --refresh ls
```

번역하지 않고 원문 man 출력만 확인:

```bash
kohelp --original ls
```

진행 메시지 숨기기:

```bash
kohelp --quiet ls
```

## 동작 방식

```text
kohelp ls 입력
↓
내부적으로 man ls 실행
↓
man 출력 텍스트 수집
↓
Gemini가 원문에서 전문용어 후보 추출
↓
json/tta_terms_en_ko_clean.json에서 후보 단어 조회
↓
조회된 한국어 전문용어 후보를 프롬프트에 넣고 번역
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
    tta_terms_en_ko_clean.json
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
