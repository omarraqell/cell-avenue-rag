import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "app" / "data" / "raw"
CLEAN_DIR = ROOT / "app" / "data" / "cleaned"
MANIFEST_DIR = ROOT / "app" / "data" / "manifests"
CLEANING_VERSION = "v1.1"


BANNER_LINE_PATTERNS = [
    re.compile(r"^\s*dear customers,?\s*$", re.IGNORECASE),
    re.compile(r"^\s*dear customer kindly note that all placed orders", re.IGNORECASE),
    re.compile(r"^\s*thank you for shopping at cell avenue store\.?\s*$", re.IGNORECASE),
    re.compile(r"^\s*العملاء الأعزاء", re.IGNORECASE),
    re.compile(r"^\s*كل عام و انتم بخير", re.IGNORECASE),
    re.compile(r"^\s*يرجى ملاحظة أن جميع الطلبات", re.IGNORECASE),
    re.compile(r"^\s*شكرًا لكم للتسوق في متجر سيل أفينيو", re.IGNORECASE),
]


NOISE_SUBSTRINGS = [
    "shopping cart",
    "scroll up",
    "start typing to see products you are looking for",
    "ابدا بالكتابة لترى المنتجات التي تبحث عنها",
    "protected by **recaptcha**",
    "recaptcha requires verification",
    "google.com/intl/en/policies/privacy",
    "google.com/intl/en/policies/terms",
    "do not follow this link or you will be banned from the site",
    "blackhole=",
    "facebook social link",
    "linkedin social link",
    "add to wishlist",
    "quick view",
    "read more description",
    "load more products",
    "show sidebar",
]


LINK_ONLY_RE = re.compile(r"^\s*\[.*?\]\(https?://.*?\)\s*$")
IMAGE_LINE_RE = re.compile(r"^\s*!\[.*?\]\(.*?\)\s*$")
LINKED_IMAGE_LINE_RE = re.compile(r"^\s*\[!\[.*?\]\(.*?\)\]\(.*?\)\s*$")
MULTI_IMAGE_ONLY_RE = re.compile(r"^\s*(?:!\[.*?\]\(.*?\)\s*)+$")
MULTI_LINKED_IMAGE_ONLY_RE = re.compile(r"^\s*(?:\[!\[.*?\]\(.*?\)\]\(.*?\)\s*)+$")
LISTING_LINK_RE = re.compile(r"^\s*-\s*\[.*?\]\(https?://.*?\)\s*$")
SHORTCODE_RE = re.compile(r"\\?\[(vc_|la_|contact-form-7|wpum_|ultimatemember|/vc_|/la_).*", re.IGNORECASE)
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{2,}:?\s*\|)+\s*$")


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def should_drop_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    s_lower = s.lower()

    if s in {"✕", "✖", "x"}:
        return True

    for pat in BANNER_LINE_PATTERNS:
        if pat.search(s):
            return True

    if SHORTCODE_RE.match(s):
        return True

    if "<base64-image-removed>" in s_lower:
        return True

    if IMAGE_LINE_RE.match(s):
        return True

    if LINKED_IMAGE_LINE_RE.match(s):
        return True

    if MULTI_IMAGE_ONLY_RE.match(s):
        return True

    if MULTI_LINKED_IMAGE_ONLY_RE.match(s):
        return True

    if TABLE_SEPARATOR_RE.match(s):
        return True

    # Navigation/listing links are usually boilerplate noise.
    if LISTING_LINK_RE.match(s):
        return True

    for sub in NOISE_SUBSTRINGS:
        if sub in s_lower:
            return True

    if LINK_ONLY_RE.match(s) and any(k in s_lower for k in ("privacy", "terms", "close")):
        return True

    if s_lower in {
        "close",
        "search",
        "menu",
        "loading...",
        "previous",
        "next",
    }:
        return True

    return False


def strip_related_products_block(text: str, page_type: str) -> str:
    if page_type != "product":
        return text
    # Remove noisy related-products tail for product pages.
    patterns = [
        re.compile(r"\n###\s*Related products\s*\n", re.IGNORECASE),
        re.compile(r"\n###\s*منتجات ذات صلة\s*\n", re.IGNORECASE),
    ]
    cut_idx = None
    for pat in patterns:
        m = pat.search(text)
        if m:
            cut_idx = m.start() if cut_idx is None else min(cut_idx, m.start())
    if cut_idx is not None:
        return text[:cut_idx].rstrip()
    return text


def dedupe_consecutive(lines: List[str]) -> List[str]:
    out: List[str] = []
    prev = None
    for line in lines:
        if line == prev and line.strip():
            continue
        out.append(line)
        prev = line
    return out


def clean_markdown(markdown: str, page_type: str) -> str:
    text = normalize_whitespace(markdown)
    text = strip_related_products_block(text, page_type)
    lines = text.split("\n")

    kept = []
    for line in lines:
        if should_drop_line(line):
            continue
        kept.append(line)

    kept = dedupe_consecutive(kept)
    cleaned = "\n".join(kept)
    cleaned = normalize_whitespace(cleaned)
    return cleaned


def process_file(path: Path, out_path: Path) -> Tuple[int, int, int, int]:
    read_records = 0
    written_records = 0
    raw_chars = 0
    clean_chars = 0
    cleaned_at = datetime.now(timezone.utc).isoformat()

    with path.open("r", encoding="utf-8") as src, out_path.open("w", encoding="utf-8") as dst:
        for line in src:
            line = line.strip()
            if not line:
                continue

            read_records += 1
            obj = json.loads(line)
            raw_text = obj.get("markdown", "")
            page_type = obj.get("page_type", "other")
            text = clean_markdown(raw_text, page_type)

            raw_chars += len(raw_text)
            clean_chars += len(text)

            # Keep only useful records.
            if len(text) < 40:
                continue

            out = {k: v for k, v in obj.items() if k != "markdown"}
            out["text"] = text
            out["cleaned_at"] = cleaned_at
            out["cleaning_version"] = CLEANING_VERSION
            out["raw_char_count"] = len(raw_text)
            out["clean_char_count"] = len(text)

            dst.write(json.dumps(out, ensure_ascii=False) + "\n")
            written_records += 1

    return read_records, written_records, raw_chars, clean_chars


def main() -> None:
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"Raw data directory not found: {RAW_DIR}")

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cleaning_version": CLEANING_VERSION,
        "files": [],
    }

    totals = {
        "read_records": 0,
        "written_records": 0,
        "raw_chars": 0,
        "clean_chars": 0,
    }

    for src in sorted(RAW_DIR.glob("*.jsonl")):
        dst = CLEAN_DIR / src.name
        read_records, written_records, raw_chars, clean_chars = process_file(src, dst)

        totals["read_records"] += read_records
        totals["written_records"] += written_records
        totals["raw_chars"] += raw_chars
        totals["clean_chars"] += clean_chars

        manifest["files"].append(
            {
                "source": str(src.relative_to(ROOT)),
                "output": str(dst.relative_to(ROOT)),
                "read_records": read_records,
                "written_records": written_records,
                "raw_chars": raw_chars,
                "clean_chars": clean_chars,
            }
        )

    manifest["totals"] = totals
    manifest_path = MANIFEST_DIR / "clean_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"Done. Cleaned {totals['written_records']}/{totals['read_records']} records. "
        f"Chars: {totals['raw_chars']} -> {totals['clean_chars']}."
    )
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
