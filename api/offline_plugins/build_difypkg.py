"""Build a deterministic Dify plugin package from a vendored plugin directory."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

SKIP_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "tests"}


def build(source: Path, output: Path) -> None:
    if not (source / "manifest.yaml").is_file():
        raise SystemExit(f"manifest.yaml not found under {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for file_path in sorted(p for p in source.rglob("*") if p.is_file()):
            relative = file_path.relative_to(source)
            if any(part in SKIP_PARTS for part in relative.parts):
                continue
            if relative.name == ".env" or relative.suffix == ".difypkg":
                continue

            info = ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, file_path.read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.source, args.output)
