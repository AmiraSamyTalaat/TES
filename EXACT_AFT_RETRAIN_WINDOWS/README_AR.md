# Optional AFT training environment comparison (Windows Python 3.12)

This optional utility runs the original training program in a separate working copy. It does not overwrite the source project or any saved model. Use the pinned environment in `requirements_frozen_runtime_exact.txt`, provide the official CDC/NCHS source files locally, and compare the resulting model with the preserved reference.

## PowerShell

```powershell
py -3.12 -m venv .venv_frozen
.\.venv_frozen\Scripts\python.exe -m pip install -r requirements_frozen_runtime_exact.txt
.\.venv_frozen\Scripts\python.exe exact_runtime_compare.py --source-root "D:\PATH\Q1" --work-root "D:\PATH\TES_AFT_RETRAIN_TEST"
```

The generated `EXACT_AFT_RETRAIN_COMPARISON.json` records the runtime, model iteration, C-index, checksums and comparisons. The original archived training files remain unchanged.
