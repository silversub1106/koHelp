from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import urllib.error
import urllib.request
from pathlib import Path


APP = "kohelp"
DEFAULT_MODEL = "gemini-2.5-flash-lite"
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
PROMPT_VERSION = "security-v1"


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="kohelp",
        description="Translate Linux man pages into Korean with Gemini and a TTA term JSON.",
    )
    parser.add_argument("command", nargs="?", help="man page name, e.g. ls")
    parser.add_argument("man_args", nargs=argparse.REMAINDER, help="extra man args")
    parser.add_argument("--section", "-s", help="man section, e.g. 2 for open(2)")
    parser.add_argument("--refresh", action="store_true", help="ignore cached translation")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model, default: {DEFAULT_MODEL}")
    parser.add_argument("--key", help="save Gemini API key and exit")
    parser.add_argument("--setting", action="store_true", help="run first-time setup")
    parser.add_argument("--cache-dir", default=None, help="cache directory")
    parser.add_argument("--original", action="store_true", help="print original man output only")
    parser.add_argument("--quiet", action="store_true", help="hide progress messages")
    args = parser.parse_args()

    if args.setting:
        return run_setting()

    if args.key:
        save_api_key(args.key)
        print("Gemini API key saved.")
        return 0

    if not args.command:
        parser.print_help()
        return 2

    man_request = ([args.section] if args.section else []) + [args.command] + args.man_args
    source, source_type = run_source(args.command, man_request)
    if args.original:
        print(source, end="" if source.endswith("\n") else "\n")
        return 0

    cache_dir = Path(args.cache_dir).expanduser() if args.cache_dir else default_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    glossary_path = find_glossary_path()
    glossary_hash = sha256_file(glossary_path)[:16]
    cache_key = sha256_text(
        json.dumps(
            {
                "man_request": man_request,
                "source_hash": sha256_text(source),
                "glossary_hash": glossary_hash,
                "model": args.model,
                "prompt": PROMPT_VERSION,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
    )
    cache_file = cache_dir / f"{safe_name('_'.join(man_request))}.{cache_key[:16]}.ko.txt"

    if cache_file.exists() and not args.refresh:
        print(cache_file.read_text(encoding="utf-8"), end="")
        return 0

    api_key = get_api_key()
    glossary = load_glossary(glossary_path)

    log(args.quiet, f"{args.command} ({source_type}) 수집 완료")
    log(args.quiet, "LLM이 전문용어 후보를 추출하는 중")
    llm_terms = extract_terms_with_llm(source, api_key=api_key, model=args.model)
    matched_terms = lookup_terms(llm_terms, glossary)
    log(args.quiet, f"전문용어 후보 {len(llm_terms)}개, JSON 매칭 {len(matched_terms)}개")

    log(args.quiet, "번역 중")
    translated = translate_with_llm(source, matched_terms, api_key=api_key, model=args.model)
    cache_file.write_text(translated if translated.endswith("\n") else translated + "\n", encoding="utf-8")
    print(translated, end="" if translated.endswith("\n") else "\n")
    return 0


def run_source(command: str, man_request: list[str]) -> tuple[str, str]:
    """Try command --help first, then fall back to man output."""
    real_cmd = shutil.which(command)
    if not real_cmd:
        raise SystemExit(f"Command '{command}' not found.")

    proc = subprocess.run(
        [real_cmd, "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    output = proc.stdout or proc.stderr
    text = output.decode("utf-8", errors="replace")
    if text.strip():
        return clean_man_text(text), "help"

    real_man = shutil.which("man")
    if real_man:
        env = os.environ.copy()
        env["MANPAGER"] = "cat"
        env["PAGER"] = "cat"
        env.pop("MAN_KEEP_FORMATTING", None)
        proc = subprocess.run(
            [real_man, *man_request],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
        if proc.returncode == 0:
            text = (proc.stdout or proc.stderr).decode("utf-8", errors="replace")
            return clean_man_text(text), "man"

    raise SystemExit(f"Could not read help text for '{command}' from --help or man.")


def clean_man_text(text: str) -> str:
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"_\x08(.)", r"\1", text)
        text = re.sub(r"(.)\x08\1", r"\1", text)
        text = re.sub(r".\x08", "", text)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract_terms_with_llm(text: str, *, api_key: str, model: str) -> list[str]:
    prompt = "\n".join(
        [
            "Extract English technical terms from this security CLI tool help text.",
            "Return only a JSON array of strings.",
            "Prefer cybersecurity, networking, exploit, vulnerability, privilege, authentication, and hacking terms.",
            "Do not include normal sentence fragments.",
            "",
            "[HELP_TEXT]",
            text,
        ]
    )
    raw = gemini_generate(prompt, api_key=api_key, model=model)
    return parse_json_string_array(raw)


def translate_with_llm(text: str, terms: dict[str, list[str]], *, api_key: str, model: str) -> str:
    glossary_lines = "\n".join(f"{src} => {' | '.join(kos[:3])}" for src, kos in sorted(terms.items()))
    if not glossary_lines:
        glossary_lines = "(none)"
    prompt = "\n".join(
        [
            "Translate this security CLI tool help text into Korean.",
            "Rules:",
            "- Preserve command names, option flags, arguments, paths, examples, and indentation.",
            "- Translate normal English sentences naturally into Korean.",
            "- Apply the glossary terms when they appear in the original text.",
            "- If a glossary term has multiple Korean candidates, choose the best one for context.",
            "- Use cybersecurity industry Korean expressions (e.g. 페이로드, 익스플로잇, 권한 상승).",
            "- Do not add new explanations.",
            "- Return only the translated help text.",
            "",
            "[GLOSSARY]",
            glossary_lines,
            "",
            "[HELP_TEXT]",
            text,
        ]
    )
    return gemini_generate(prompt, api_key=api_key, model=model).strip()


def gemini_generate(prompt: str, *, api_key: str, model: str) -> str:
    endpoint = f"{API_BASE}/models/{model}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "topP": 0.8},
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key.strip()},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Gemini API error {exc.code}: {redact_key(message)}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Gemini API connection error: {exc.reason}") from exc

    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SystemExit(f"Unexpected Gemini response: {data}") from exc
    return "".join(part.get("text", "") for part in parts)


def parse_json_string_array(raw: str) -> list[str]:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"\[[\s\S]*\]", cleaned)
    if match:
        cleaned = match.group(0)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    result = []
    seen = set()
    for item in data:
        term = str(item).strip()
        key = term.lower()
        if term and key not in seen:
            seen.add(key)
            result.append(term)
    return result


def load_glossary(path: Path) -> dict[str, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k).lower(): [str(v).strip() for v in values if str(v).strip()] for k, values in data.items()}


def lookup_terms(terms: list[str], glossary: dict[str, list[str]]) -> dict[str, list[str]]:
    matched = {}
    for term in terms:
        key = term.lower()
        if key in glossary:
            matched[term] = glossary[key]
    return matched


def find_glossary_path() -> Path:
    candidates = [
        Path(__file__).resolve().parent / "json" / "security_terms_en_ko.json",
        Path(sys.prefix) / "share" / "kohelp" / "json" / "security_terms_en_ko.json",
        Path(sysconfig.get_path("data")) / "share" / "kohelp" / "json" / "security_terms_en_ko.json",
        Path("~/.local/share/kohelp/json/security_terms_en_ko.json").expanduser(),
        Path.cwd() / "json" / "security_terms_en_ko.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise SystemExit("security_terms_en_ko.json not found.")


def get_api_key() -> str:
    configured = read_config().get("api_key")
    if configured:
        return configured.strip()
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key:
        return env_key.strip()
    key = getpass.getpass("Gemini API key: ").strip()
    if not key:
        raise SystemExit("Gemini API key is required.")
    save_api_key(key)
    return key


def run_setting() -> int:
    print("kohelp first-time setting")
    print()

    missing = []
    for command in ("man",):
        if not shutil.which(command):
            missing.append(command)

    if missing:
        print("Missing required command(s): " + ", ".join(missing))
        print("Ubuntu install command:")
        print("  sudo apt update && sudo apt install -y man-db")
        print()
    else:
        print("OK: man command found")

    if sys.prefix == sys.base_prefix:
        print("NOTE: virtualenv is not active.")
        print("Recommended install flow:")
        print("  python3 -m venv .venv")
        print("  . .venv/bin/activate")
        print("  python3 -m pip install .")
        print()
    else:
        print("OK: virtualenv is active")

    glossary = find_glossary_path()
    print(f"OK: glossary found: {glossary}")

    current = read_config().get("api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if current:
        answer = input("Gemini API key already exists. Replace it? [y/N]: ").strip().lower()
        if answer == "y":
            key = getpass.getpass("New Gemini API key: ").strip()
            if key:
                save_api_key(key)
                print("OK: API key saved")
    else:
        key = getpass.getpass("Gemini API key: ").strip()
        if key:
            save_api_key(key)
            print("OK: API key saved")
        else:
            print("SKIP: API key not saved")

    default_cache_dir().mkdir(parents=True, exist_ok=True)
    print(f"OK: cache directory ready: {default_cache_dir()}")
    print()
    print("Test command:")
    print("  kohelp --original ls")
    print("  kohelp ls")
    return 0


def save_api_key(key: str) -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps({"api_key": key.strip()}, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(config_path(), 0o600)
    except OSError:
        pass


def read_config() -> dict[str, str]:
    try:
        return json.loads(config_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / APP


def config_path() -> Path:
    return config_dir() / "config.json"


def default_cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser() / APP


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._+-]+", "_", value).strip("._")
    return (name or "man")[:80]


def redact_key(message: str) -> str:
    return re.sub(r"AIza[0-9A-Za-z_-]{20,}", "AIza***", message)


def log(quiet: bool, message: str) -> None:
    if not quiet:
        print(f"[kohelp] {message}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
