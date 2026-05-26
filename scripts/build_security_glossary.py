"""
KISA(한국어) + NIST(영어) 데이터를 결합해 security_terms_en_ko.json 생성

매핑 전략:
1. KISA 용어명에 영어가 포함된 경우 → 직접 추출 (예: "TLP(Traffic Light Protocol)" → "tlp")
2. NIST 영어 용어와 KISA 한국어 용어명을 소문자 비교 매핑
3. 매핑 안 된 KISA 용어는 그냥 한국어 그대로 저장 (kohelp 프롬프트에서 활용)

출력 형식: { "영어소문자": ["한국어표현1", ...] }  ← 기존 TTA 사전과 동일한 형식
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "json"
KISA_PATH = BASE / "kisa_terms_ko.json"
NIST_ZIP  = BASE / "nist_glossary.zip"
OUTPUT    = BASE / "security_terms_en_ko.json"


def load_kisa() -> list[dict]:
    return json.loads(KISA_PATH.read_text(encoding="utf-8"))


def load_nist() -> list[dict]:
    with zipfile.ZipFile(NIST_ZIP) as z:
        return json.loads(z.read("glossary-export.json").decode("utf-8-sig"))["parentTerms"]


def extract_english_from_kisa_term(term_ko: str) -> list[str]:
    """
    KISA 용어명에서 영어 부분 추출
    예: "TLP(Traffic Light Protocol)" → ["tlp", "traffic light protocol"]
    예: "Use-After-Free 취약점"       → ["use-after-free"]
    예: "제로트러스트 (Zero Trust)"   → ["zero trust"]
    """
    results = []

    # 괄호 안 영어 추출
    for m in re.finditer(r"\(([A-Za-z][A-Za-z0-9 \-_./]+)\)", term_ko):
        results.append(m.group(1).strip().lower())

    # 영어로만 이루어진 단어 덩어리 추출 (한글 제외)
    en_parts = re.findall(r"[A-Za-z][A-Za-z0-9\-_./]*(?:\s+[A-Za-z][A-Za-z0-9\-_./]*)*", term_ko)
    for part in en_parts:
        cleaned = part.strip().lower()
        if len(cleaned) >= 2:
            results.append(cleaned)

    return list(dict.fromkeys(results))  # 중복 제거, 순서 유지


def normalize(text: str) -> str:
    return text.strip().lower()


def build_glossary() -> dict[str, list[str]]:
    kisa_terms = load_kisa()
    nist_terms = load_nist()

    # NIST 영어 용어 → 소문자 인덱스
    nist_index: dict[str, str] = {normalize(t["term"]): t["term"] for t in nist_terms}

    glossary: dict[str, list[str]] = {}
    matched = 0
    direct  = 0

    for item in kisa_terms:
        term_ko  = item["term_ko"]

        # KISA 용어명 전체를 한국어 표현으로 사용
        ko_label = term_ko

        en_keys = extract_english_from_kisa_term(term_ko)

        # NIST와 교차 매핑
        for key in en_keys:
            if key in nist_index:
                matched += 1
            if key and key not in glossary:
                glossary[key] = [ko_label]
            elif key and ko_label not in glossary[key]:
                glossary[key].append(ko_label)
            direct += 1

        # 영어 키가 없는 순수 한국어 용어도 한국어 키로 저장
        if not en_keys:
            key = normalize(term_ko)
            glossary[key] = [term_ko]

    return glossary, matched, direct


def main() -> None:
    print("보안 용어 사전 생성 중...")
    glossary, matched, direct = build_glossary()

    OUTPUT.write_text(
        json.dumps(glossary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"총 {len(glossary)}개 엔트리 생성")
    print(f"  - NIST 교차 매핑: {matched}개")
    print(f"  - 직접 추출 키: {direct}개")
    print(f"저장 완료: {OUTPUT}")

    print("\n--- 샘플 ---")
    items = list(glossary.items())
    for k, v in items[:10]:
        print(f"  {k!r} => {v}")


if __name__ == "__main__":
    main()
