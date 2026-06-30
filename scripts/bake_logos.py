#!/usr/bin/env python3
"""Bake rot-prone external league logos into the web bundle.

The analytics snapshot carries each manager's per-season + main logo URL. A
handful (~15-20 of 70) are `CUSTOM_VALID` logos hosted on third-party sites
(postimg.cc, i.redd.it, twimg, …) that can rot. This derivation step downloads
those external-host logos into ``apps/web/public/logos/<season>/<ownerGuid>.<ext>``
and rewrites every occurrence of the URL in the snapshot to the local path, so
the demo can't break when an upstream image disappears. Stable ESPN-hosted
logos + all headshots stay remote (CDN-cached via next/image).

League-agnostic: detects external hosts by URL, never by hardcoded names/ids.
Runs locally (never in the browser); no secrets involved.

Usage:
    python scripts/bake_logos.py
    python scripts/bake_logos.py --snapshot path/to/analytics_snapshot.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOTS = [
    REPO_ROOT / "tests/fixtures/espn/league_18254195/analytics_snapshot.json",
    REPO_ROOT / "services/api/src/mygm_api/demo_snapshot.json",
]
PUBLIC_LOGOS = REPO_ROOT / "apps/web/public/logos"

# Hosts whose logos are stable and stay remote (everything else is rot-prone).
STABLE_HOST_MARKERS = ("espncdn.com", "fantasy.espn.com")
EXT_BY_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def is_external(url: str | None) -> bool:
    if not url or not url.startswith("http"):
        return False
    return not any(marker in url for marker in STABLE_HOST_MARKERS)


def guess_ext(url: str) -> str:
    suffix = Path(url.split("?")[0]).suffix.lower()
    return suffix if suffix in EXT_BY_SUFFIX else ".png"


def collect_external_logos(snapshot: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Map external URL → (ownerGuid, season) of its first reference, for naming."""
    found: dict[str, tuple[str, str]] = {}
    for manager in snapshot.get("managers", []):
        logo = manager.get("logo") or {}
        owner = str(manager.get("managerKey", "")).replace("espn-owner:", "") or "unknown"
        owner = owner.strip("{}") or "unknown"
        main_season = str(logo.get("mainSeason") or "main")
        for season, url in (logo.get("bySeason") or {}).items():
            if is_external(url) and url not in found:
                found[url] = (owner, str(season))
        main = logo.get("main")
        if is_external(main) and main not in found:
            found[main] = (owner, main_season)
    return found


def download(url: str, dest: Path) -> bool:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 mygm-bake"})
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (trusted local step)
            if response.status != 200:
                return False
            data = response.read()
        if not data:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        _ = dest.write_bytes(data)
        return True
    except Exception as error:  # noqa: BLE001 — best-effort; dead URLs fall back to monogram
        print(f"  ! skip (could not fetch): {url} — {error}")
        return False


def rewrite(node: Any, url_map: dict[str, str]) -> Any:
    if isinstance(node, str):
        return url_map.get(node, node)
    if isinstance(node, list):
        return [rewrite(item, url_map) for item in node]
    if isinstance(node, dict):
        return {key: rewrite(value, url_map) for key, value in node.items()}
    return node


def bake(snapshot_path: Path) -> int:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    external = collect_external_logos(snapshot)
    if not external:
        print(f"{snapshot_path.name}: no external logos to bake.")
        return 0

    print(f"{snapshot_path.name}: {len(external)} external logos to bake.")
    url_map: dict[str, str] = {}
    for url, (owner, season) in external.items():
        ext = guess_ext(url)
        rel = f"{season}/{owner}{ext}"
        dest = PUBLIC_LOGOS / rel
        if dest.exists() or download(url, dest):
            url_map[url] = f"/logos/{rel}"

    if not url_map:
        print("  (no logos could be fetched — leaving URLs as-is; emblems fall back to monogram)")
        return 0

    rewritten = rewrite(snapshot, url_map)
    _ = snapshot_path.write_text(
        json.dumps(rewritten, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"  baked {len(url_map)}/{len(external)} → rewrote URLs in {snapshot_path.name}")
    return len(url_map)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, action="append", help="snapshot json(s) to bake")
    args = parser.parse_args()
    snapshots = args.snapshot or DEFAULT_SNAPSHOTS

    # Bake the first snapshot, then mirror the baked file to the rest (they must
    # stay byte-identical; the API copy is the demo source).
    primary = snapshots[0]
    bake(primary)
    for other in snapshots[1:]:
        if other.exists():
            shutil.copyfile(primary, other)
            print(f"  mirrored → {other.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
