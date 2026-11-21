from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "publication/PROVLAB_COMPLETE_MANUSCRIPT_Q1_WORKING_DRAFT.docx",
    "publication/FINAL_RESULTS_TABLE.csv",
    "publication/TABLE1_COHORT_CHARACTERISTICS.csv",
    "publication/figures/FIGURE1_STUDY_TIMELINE.png",
    "publication/figures/FIGURE2_CINDEX_FOREST.png",
    "publication/figures/FIGURE3_TEMPORAL_SHAP_HEATMAP.png",
    "data/processed/nhanes_survival_cohort.csv.gz",
    "data/processed/nhanes_harmonized_panel.csv.gz",
    "data/ANALYTE_REGISTRY.json",
    "data/PUBLIC_SOURCE_REGISTRY.json",
    "src/build_harmonized_panel.py",
    "SOURCE_DATA_MANIFEST.json",
    "REPRODUCTION_REFERENCE.json",
    "requirements.txt",
    "outputs/aft_survival_pilot/xgboost_aft_model.ubj",
    "outputs/tes_aft_pilot/tes_aft_model.ubj",
    "outputs/locked_confirmatory_evaluation/LOCKED_CONFIRMATORY_STATUS.json",
    "outputs/nhanes3_locked_external/NHANES3_LOCKED_EXTERNAL_STATUS.json",
]

ALLOWED_STATUS = {"PASS", "SUPERIOR"}
BANNED_NAME_TOKENS = ("s3c", "cipot", "csd_", "cycledro", "cycle_dro", "tues", "neuralsurv")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    problems = []
    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            problems.append(f"missing required file: {rel}")
    # Self-contained source path checks.
    for rel in ("src/build_harmonized_panel.py", "src/build_survival_cohort.py", "src/augment_survey_design.py"):
        path = ROOT / rel
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "PROVLAB_Q1_IDENTIFIABILITY_GUARD" in text or "ROOT.parents[1] / \"26_8\"" in text:
                problems.append(f"historical sibling-project dependency remains: {rel}")
    # Verify bundled source data.
    manifest_path = ROOT / "SOURCE_DATA_MANIFEST.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for rec in manifest.get("files", []):
                p = ROOT / rec["path"]
                if not p.is_file(): problems.append(f"missing source-data file: {rec['path']}")
                elif p.stat().st_size != rec["bytes"] or sha256(p) != rec["sha256"]:
                    problems.append(f"source-data checksum mismatch: {rec['path']}")
        except Exception as exc:
            problems.append(f"invalid source-data manifest: {exc}")
    # Verify all cryptographically frozen critical files remain pristine.
    for manifest_name in ("CONFIRMATORY_EXECUTION_MANIFEST.json", "NHANES3_PRE_OUTCOME_EXECUTION_MANIFEST.json"):
        mp = ROOT / manifest_name
        if not mp.is_file():
            problems.append(f"missing freeze manifest: {manifest_name}")
            continue
        try:
            freeze = json.loads(mp.read_text(encoding="utf-8"))
            for rel, expected in freeze.get("critical_sha256", {}).items():
                p = ROOT / rel
                if not p.is_file(): problems.append(f"missing frozen file: {rel}")
                elif sha256(p) != expected: problems.append(f"frozen SHA-256 mismatch: {rel}")
        except Exception as exc:
            problems.append(f"invalid freeze manifest {manifest_name}: {exc}")
    for path in ROOT.rglob("*"):
        low = path.name.lower()
        if any(token in low for token in BANNED_NAME_TOKENS):
            problems.append(f"excluded experiment name present: {path.relative_to(ROOT)}")
    statuses = []
    for path in (ROOT / "outputs").rglob("*.json"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "status" in obj:
            statuses.append({"file": str(path.relative_to(ROOT)), "status": obj["status"]})
            if obj["status"] not in ALLOWED_STATUS:
                problems.append(f"non-success status {obj['status']}: {path.relative_to(ROOT)}")
    docx = ROOT / REQUIRED[0]
    if docx.exists():
        with zipfile.ZipFile(docx) as zf:
            xml = b"".join(zf.read(n) for n in zf.namelist() if n.endswith(".xml")).lower()
        for term in (b"neuralsurv", b"cipot", b"s3c-surv", b"negative conformal", b"distributionally robust pilots"):
            if term in xml:
                problems.append(f"excluded experiment text present in manuscript: {term.decode()}")
    report = {
        "status": "PASS" if not problems else "FAIL",
        "required_files_checked": len(REQUIRED),
        "successful_status_files": statuses,
        "manuscript_sha256": sha256(docx) if docx.exists() else None,
        "problems": problems,
    }
    out = ROOT / "PACKAGE_VERIFICATION_STATUS.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
