"""Replace one oversized GFW Presence Bronze response with safe JSON parts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dark_rendezvous.cli_support import json_hash
from dark_rendezvous.providers.gfw_presence import partition_presence_report
from dark_rendezvous.storage import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAX_BYTES = 95 * 1024 * 1024


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True).encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Existing oversized report.json path.")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()

    source = args.report.resolve()
    if source.name != "report.json" or not source.is_file():
        raise ValueError("report must be an existing file named report.json")
    if not source.is_relative_to(ROOT):
        raise ValueError("report must be inside this repository")

    payload = json.loads(source.read_bytes())
    parts = partition_presence_report(payload, max_bytes=args.max_bytes)
    if len(parts) == 1:
        raise ValueError("report is already within the requested size limit")

    paths = [source.with_name(f"report.part-{index:04d}.json") for index in range(1, len(parts) + 1)]
    collisions = [path for path in paths if path.exists()]
    if collisions:
        raise FileExistsError(f"Refusing to overwrite existing part: {collisions[0]}")
    for path, part in zip(paths, parts, strict=True):
        _write_json(path, part)
        if path.stat().st_size > args.max_bytes:
            raise AssertionError(f"Part exceeds the requested limit: {path}")

    source_relative = str(source.relative_to(ROOT))
    part_relatives = [str(path.relative_to(ROOT)) for path in paths]
    part_hashes = [sha256_file(path) for path in paths]
    part_bytes = [path.stat().st_size for path in paths]
    updated_manifests = 0
    for manifest_path in (ROOT / "data").rglob("manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("raw_response_path") != source_relative:
            continue
        if manifest.get("raw_response_sha256") != json_hash(payload):
            raise ValueError(f"Manifest raw response hash does not match {source}")
        manifest.update(
            {
                "raw_response_path": part_relatives[0],
                "raw_response_paths": part_relatives,
                "raw_response_part_sha256": part_hashes,
                "raw_response_part_bytes": part_bytes,
                "raw_response_partitioned": True,
                "raw_response_max_part_bytes": args.max_bytes,
            }
        )
        _write_json(manifest_path, manifest)
        updated_manifests += 1

    # New parts have been validated and their manifests now reference them.
    # Deleting only this source removes the original GitHub-blocking object.
    source.unlink()
    print(
        json.dumps(
            {
                "replaced": source_relative,
                "part_count": len(paths),
                "max_part_bytes": max(part_bytes),
                "parts": part_relatives,
                "manifests_updated": updated_manifests,
            }
        )
    )


if __name__ == "__main__":
    main()
