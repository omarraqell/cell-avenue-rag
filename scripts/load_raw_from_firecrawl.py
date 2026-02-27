import json
import re
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


BASE_URL = "https://api.firecrawl.dev/v1"
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "app" / "data" / "raw"
MANIFEST_DIR = ROOT / "app" / "data" / "manifests"
CONFIG_PATH = Path.home() / ".codex" / "config.toml"


def load_api_key_from_codex_config() -> str:
    if tomllib is None:
        raise RuntimeError("Python 3.11+ is required (tomllib missing).")
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Codex config not found: {CONFIG_PATH}")

    with CONFIG_PATH.open("rb") as f:
        cfg = tomllib.load(f)

    key = (
        cfg.get("mcp_servers", {})
        .get("firecrawl", {})
        .get("env", {})
        .get("FIRECRAWL_API_KEY")
    )
    if not key:
        raise RuntimeError("FIRECRAWL_API_KEY not found in ~/.codex/config.toml")
    return key


def api_request(
    method: str,
    path: str,
    api_key: str,
    payload: Optional[Dict[str, Any]] = None,
    retries: int = 5,
) -> Dict[str, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = request.Request(f"{BASE_URL}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("x-api-key", api_key)

    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            with request.urlopen(req, timeout=180) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            # Retry rate limits.
            if e.code == 429 and attempt < retries - 1:
                wait_s = 5 + attempt * 5
                # Try to parse "retry after Xs" from provider message.
                m = re.search(r"retry after (\d+)s", detail, flags=re.IGNORECASE)
                if m:
                    wait_s = max(wait_s, int(m.group(1)))
                time.sleep(wait_s)
                last_err = RuntimeError(f"HTTP {e.code} on {path}: {detail}")
                continue
            # Retry transient server errors.
            if e.code >= 500 and attempt < retries - 1:
                time.sleep(2 + attempt * 2)
                last_err = RuntimeError(f"HTTP {e.code} on {path}: {detail}")
                continue
            raise RuntimeError(f"HTTP {e.code} on {path}: {detail}") from e
        except Exception as e:  # noqa: BLE001
            if attempt < retries - 1:
                time.sleep(2 + attempt * 2)
                last_err = e
                continue
            raise
    if last_err is not None:
        raise RuntimeError(f"Request failed for {path}: {last_err}")
    return {}


def start_crawl(payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    return api_request("POST", "/crawl", api_key, payload)


def get_crawl_status(crawl_id: str, api_key: str) -> Dict[str, Any]:
    return api_request("GET", f"/crawl/{crawl_id}", api_key)


def poll_until_complete(crawl_id: str, api_key: str) -> Dict[str, Any]:
    while True:
        status = get_crawl_status(crawl_id, api_key)
        state = str(status.get("status", "")).lower()
        if state in {"completed", "failed", "cancelled"}:
            return status
        time.sleep(5)


def page_type_from_url(url: str) -> str:
    if "/product/" in url:
        return "product"
    if any(
        p in url
        for p in (
            "/shipping-policy",
            "/returns-replacements",
            "/terms-and-conditions",
            "/privacy-policy",
            "/contact-us",
            "/about-us",
        )
    ):
        return "policy_support"
    if "/product-category/" in url:
        return "category"
    if any(
        p in url
        for p in (
            "/home-05",
            "/honor",
            "/blackfriday-2025",
            "/valentine-2025",
            "/huawei-gt-6-series",
            "/honor-400-series",
            "/ar/honor",
            "/ar/%d8%a7%d9%84%d8%b1%d8%a6%d9%8a%d8%b3%d9%8a%d8%a9",
        )
    ):
        return "brand_campaign"
    return "other"


def language_from_url(url: str, metadata: Dict[str, Any]) -> str:
    if "/ar/" in url:
        return "ar"
    lang = str(metadata.get("language", "")).lower()
    if lang.startswith("ar"):
        return "ar"
    return "en"


def normalize_record(item: Dict[str, Any], crawl_id: str) -> Dict[str, Any]:
    metadata = item.get("metadata") or {}
    source_url = metadata.get("sourceURL") or metadata.get("url") or ""
    title = metadata.get("title") or ""
    markdown = item.get("markdown") or ""
    now = datetime.now(timezone.utc).isoformat()

    return {
        "url": source_url,
        "title": title,
        "language": language_from_url(source_url, metadata),
        "page_type": page_type_from_url(source_url),
        "markdown": markdown,
        "crawled_at": now,
        "crawl_job_id": crawl_id,
    }


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scopes",
        nargs="*",
        default=None,
        help="Optional scope names to run (e.g., pages_en pages_ar).",
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    api_key = load_api_key_from_codex_config()

    excludes = [
        "/cart",
        "/checkout",
        "/my-account",
        "/login",
        "/logout",
        "/register",
        "/password-reset",
        "/wishlist",
        "/compare",
        "/profile-",
        "/thank-you",
        "/thanks",
        "/color-1/",
        "/kind/",
        "/product-tag/",
        "/capacity-gb/",
        "/author/",
        "/mobile_banners/",
        "/mobile_promotions/",
        "/screen_splashes/",
        "/page/",
    ]

    scopes = [
        {
            "name": "products_en",
            "includePaths": ["/product/"],
            "excludePaths": excludes + ["/ar/"],
            "limit": 90,
        },
        {
            "name": "products_ar",
            "includePaths": ["/ar/product/"],
            "excludePaths": excludes,
            "limit": 90,
        },
        {
            "name": "pages_en",
            "includePaths": [
                "/shipping-policy",
                "/returns-replacements",
                "/terms-and-conditions",
                "/privacy-policy",
                "/contact-us",
                "/about-us",
                "/home-05",
                "/honor",
                "/product-category/",
                "/blackfriday-2025",
                "/valentine-2025",
                "/huawei-gt-6-series",
                "/honor-400-series",
            ],
            "excludePaths": excludes + ["/ar/"],
            "limit": 40,
        },
        {
            "name": "pages_ar",
            "includePaths": [
                "/ar/honor",
                "/ar/%d8%a7%d9%84%d8%b1%d8%a6%d9%8a%d8%b3%d9%8a%d8%a9",
                "/ar/product-category/",
                "/ar/%d8%a7%d9%84%d8%a3%d8%ad%d9%83%d8%a7%d9%85-%d9%88%d8%a7%d9%84%d8%b4%d8%b1%d9%88%d8%b7",
            ],
            "excludePaths": excludes,
            "limit": 40,
        },
    ]

    run_manifest: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scopes": [],
    }

    for scope in scopes:
        if args.scopes and scope["name"] not in args.scopes:
            continue

        out_path = RAW_DIR / f"{scope['name']}.jsonl"
        if out_path.exists() and out_path.stat().st_size > 0:
            run_manifest["scopes"].append(
                {
                    "name": scope["name"],
                    "status": "skipped_existing",
                    "saved_rows": None,
                    "output_file": str(out_path.relative_to(ROOT)),
                }
            )
            continue

        payload = {
            "url": "https://cellavenuestore.com",
            "includePaths": scope["includePaths"],
            "excludePaths": scope["excludePaths"],
            "limit": scope["limit"],
            "maxDiscoveryDepth": 4,
            "allowExternalLinks": False,
            "scrapeOptions": {
                "formats": ["markdown"],
                "onlyMainContent": True,
                "removeBase64Images": True,
            },
        }

        started = start_crawl(payload, api_key)
        crawl_id = started.get("id")
        if not crawl_id:
            raise RuntimeError(f"No crawl id returned for scope {scope['name']}: {started}")

        status = started
        if str(started.get("status", "")).lower() not in {"completed", "failed", "cancelled"}:
            status = poll_until_complete(crawl_id, api_key)

        data = status.get("data") or []
        rows = [normalize_record(item, crawl_id) for item in data if item.get("markdown")]
        write_jsonl(out_path, rows)

        run_manifest["scopes"].append(
            {
                "name": scope["name"],
                "crawl_id": crawl_id,
                "status": status.get("status"),
                "completed": status.get("completed"),
                "total": status.get("total"),
                "saved_rows": len(rows),
                "output_file": str(out_path.relative_to(ROOT)),
            }
        )

    manifest_path = MANIFEST_DIR / "raw_load_manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    total_rows = sum(int(s.get("saved_rows") or 0) for s in run_manifest["scopes"])
    print(f"Done. Saved {total_rows} records across {len(run_manifest['scopes'])} files.")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
