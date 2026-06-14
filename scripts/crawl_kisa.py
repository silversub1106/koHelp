"""
KISA 보호나라 정보보호 용어사전 크롤러
https://www.krcert.or.kr/kr/bbs/list.do?menuNo=205025&bbsId=B0001020
총 34페이지, 약 340개 용어 수집
"""

from __future__ import annotations

import json
import time
import re
import urllib.request
import urllib.error
from html.parser import HTMLParser
from pathlib import Path


BASE_URL = "https://www.krcert.or.kr/kr/bbs/list.do?menuNo=205025&bbsId=B0001020&pageIndex={page}"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "json" / "kisa_terms_ko.json"
TOTAL_PAGES = 34
DELAY = 1.0  # 서버 부하 방지


class KisaParser(HTMLParser):
    """용어명(h5 태그)과 설명(li 태그) 파싱"""

    def __init__(self) -> None:
        super().__init__()
        self.terms: list[dict[str, str]] = []
        self._in_term_title = False
        self._in_term_desc = False
        self._current_term = ""
        self._current_desc_parts: list[str] = []
        self._depth = 0
        self._capture_h5 = False
        self._capture_li = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr_dict = dict(attrs)
        if tag == "h5":
            self._capture_h5 = True
            self._current_term = ""
        if tag == "li" and self._current_term:
            self._capture_li = True
            self._current_desc_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h5" and self._capture_h5:
            self._capture_h5 = False
        if tag == "li" and self._capture_li:
            self._capture_li = False
            desc = " ".join(self._current_desc_parts).strip()
            if self._current_term and desc:
                self.terms.append({
                    "term_ko": self._current_term.strip(),
                    "desc_ko": desc,
                })
                self._current_term = ""
                self._current_desc_parts = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._capture_h5:
            # "펼치기" 같은 버튼 텍스트 제거
            if text not in ("펼치기", "접기"):
                self._current_term += text
        if self._capture_li:
            self._current_desc_parts.append(text)


def fetch_page(page: int) -> str:
    url = BASE_URL.format(page=page)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; kohelp-crawler/1.0)",
            "Accept-Language": "ko-KR,ko;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def crawl_all() -> list[dict[str, str]]:
    all_terms: list[dict[str, str]] = []

    for page in range(1, TOTAL_PAGES + 1):
        print(f"[{page}/{TOTAL_PAGES}] 페이지 수집 중...", end=" ")
        try:
            html = fetch_page(page)
            parser = KisaParser()
            parser.feed(html)
            print(f"{len(parser.terms)}개 용어 파싱")
            all_terms.extend(parser.terms)
        except urllib.error.URLError as e:
            print(f"실패: {e}")
        time.sleep(DELAY)

    return all_terms


def main() -> None:
    print("KISA 보호나라 용어사전 크롤링 시작")
    terms = crawl_all()
    print(f"\n총 {len(terms)}개 용어 수집 완료")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(terms, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"저장 완료: {OUTPUT_PATH}")

    # 샘플 출력
    print("\n--- 샘플 (앞 5개) ---")
    for t in terms[:5]:
        print(f"  {t['term_ko']}: {t['desc_ko'][:50]}...")


if __name__ == "__main__":
    main()
