from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "PUBLIC_SOURCE_REGISTRY.json"
RAW = ROOT / "data" / "raw"
LOCKED = ROOT / "data" / "confirmatory_locked"
MANIFEST = ROOT / "data" / "DOWNLOAD_MANIFEST.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    last_error = None
    for attempt in range(1, 6):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ProvLab-Q1-public-data/1.0"})
            with urllib.request.urlopen(request, timeout=600) as response, temporary.open("wb") as output:
                if response.geturl().lower().startswith(("http://", "https://")) is False:
                    raise RuntimeError(f"Unexpected redirect for {url}")
                while True:
                    block = response.read(256 * 1024)
                    if not block:
                        break
                    output.write(block)
            if temporary.stat().st_size < 1024:
                raise RuntimeError(f"Downloaded file is unexpectedly small: {url}")
            temporary.replace(target)
            return
        except Exception as exc:
            last_error = exc
            print(f"RETRY {attempt}/5 for {url}: {exc}", flush=True)
            time.sleep(min(3 * attempt, 12))
    raise RuntimeError(f"Download failed after 5 attempts: {url}: {last_error}")


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    base = registry["base"].rstrip("/")
    records = []
    for row in registry["cycles"]:
        destination_root = LOCKED if row["partition"] == "confirmatory_locked" else RAW / row["partition"]
        for component, code in (("laboratory", row["laboratory"]), ("demographics", row["demographics"])):
            filename = f"{code}.XPT"
            url = f"{base}/{row['year_path']}/DataFiles/{filename}"
            target = destination_root / row["cycle"] / filename
            if not target.exists():
                print(f"DOWNLOAD {url}", flush=True)
                download(url, target)
            records.append({"cycle": row["cycle"], "partition": row["partition"], "component": component,
                            "source_url": url, "relative_path": target.relative_to(ROOT).as_posix(),
                            "bytes": target.stat().st_size, "sha256": sha256(target)})
    payload = {"stage": "PUBLIC_NHANES_DOWNLOAD", "source_policy": registry["policy"],
               "downloaded_at": datetime.now(timezone.utc).isoformat(), "files": records}
    MANIFEST.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"VERIFIED {len(records)} public files")
    print(f"MANIFEST {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
