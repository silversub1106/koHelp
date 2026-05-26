import zipfile, json
from pathlib import Path

zpath = Path(__file__).parent.parent / "json" / "nist_glossary.zip"
with zipfile.ZipFile(zpath) as z:
    data = json.loads(z.read("glossary-export.json").decode("utf-8-sig"))

print("totalRecords:", data["totalRecords"])
terms = data["parentTerms"]
print(f"parentTerms 수: {len(terms)}")
print("첫 항목 키:", list(terms[0].keys()))
print()
for t in terms[:3]:
    term = t.get("term", "")
    defs = t.get("definitions", [])
    print(f"term: {term}")
    if defs:
        print(f"  definition 키: {list(defs[0].keys())}")
        print(f"  첫 정의: {str(defs[0])[:150]}")
    print()
