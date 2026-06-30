from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FixtureRoots:
    repository: Path
    espn_export: Path


def repository_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for path in (current, *current.parents):
        if (path / "README.md").exists() and (path / ".git").exists():
            return path
    message = f"Could not find repository root from {current}"
    raise FileNotFoundError(message)


def fixture_roots(start: Path | None = None) -> FixtureRoots:
    repository = repository_root(start)
    return FixtureRoots(
        repository=repository,
        espn_export=default_espn_export_root(repository),
    )


def require_espn_export_root(path: Path | None = None) -> Path:
    export_root = path.resolve() if path else fixture_roots().espn_export
    manifest = export_root / "export_manifest.json"
    if not manifest.exists():
        message = (
            f"Missing ESPN export manifest at {manifest}. "
            "Pass an explicit export root when more than one ESPN export is available."
        )
        raise FileNotFoundError(message)
    return export_root


def default_espn_export_root(repository: Path) -> Path:
    exports_root = repository / "espn_exports"
    if (exports_root / "export_manifest.json").exists():
        return exports_root

    export_roots = sorted(
        export_root
        for export_root in exports_root.glob("league_*")
        if (export_root / "export_manifest.json").exists()
    )
    if len(export_roots) == 1:
        return export_roots[0]
    return exports_root
