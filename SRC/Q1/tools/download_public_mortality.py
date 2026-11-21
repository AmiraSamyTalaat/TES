from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "PUBLIC_MORTALITY_REGISTRY.json"
RAW = ROOT / "data" / "raw_mortality"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = []
    for cycle in registry["cycles"]:
        url = registry["url_template"].format(cycle=cycle)
        target = RAW / f"NHANES_{cycle}_MORT_2019_PUBLIC.dat"
        if not target.exists() or target.stat().st_size == 0:
            print(f"Downloading {cycle} ...")
            urllib.request.urlretrieve(url, target)
        manifest.append({"cycle": cycle.replace("_", "-"), "file": target.name,
                         "bytes": target.stat().st_size, "sha256": sha256(target), "url": url})
    (ROOT / "data" / "MORTALITY_DOWNLOAD_MANIFEST.json").write_text(
        json.dumps({"files": manifest}, indent=2), encoding="utf-8")
    print(f"PASS: {len(manifest)} public mortality files verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

