# CodeVault

**Archive. Restore. Simplify.**

A lightweight web app for archiving local folders with smart exclusions.

## Standalone Mac Edition

Download one file. Run it. Done.

```bash
curl -O https://raw.githubusercontent.com/Oswald-Benjamin/CodeVault/main/codevault.py
python3 codevault.py
```

Then open http://127.0.0.1:5555 in your browser.

**Login:** `admin` / `codevault2026`

### What it does
- Browse your Mac's folders and select any to archive
- Automatically excludes heavy directories (node_modules, .git, build, etc.)
- Shows compression ratio and space saved
- Restore archives to any location
- Dark-themed UI, password protected
- Stores archives in `~/CodeVault/Archives/`

### System Requirements
- macOS (or any OS with Python 3)
- Python 3.6+ (built into macOS)
- ~20 MB disk space for the script + archives
- No additional packages needed — uses only the standard library

### Smart Exclusions
The following directories are automatically skipped when creating archives:
`node_modules`, `.git`, `.next`, `dist`, `build`, `coverage`, `__pycache__`, `.venv`, `venv`, `vendor`, `.cache`, `tmp`
