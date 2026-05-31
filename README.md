# CodeVault

**Compress idle codebases.** Archive folders into compact `.tar.gz` files with smart exclusions (node_modules, .git, .next, dist, build, .venv, vendor, etc.).

Two versions available:

---

## Option A: Standalone macOS App (recommended)

A single Python file. No install, no dependencies. Runs on your Mac.

### Download

```bash
curl -O https://raw.githubusercontent.com/Oswald-Benjamin/CodeVault/main/codevault.py
```

Or clone the repo:
```bash
git clone https://github.com/Oswald-Benjamin/CodeVault.git
cd CodeVault
```

### Run

```bash
python3 codevault.py
```

That's it. It opens a browser tab at `http://localhost:40041` automatically.

**Login:**
- Username: `Cryptosi@protonmail.com`
- Password: `Talent81`

### Usage

1. **Drag & drop** a folder onto the drop zone, **or** click "Archive Folder" to browse
2. Archive appears in the list with stats (original → compressed, % saved)
3. Click 📥 to restore to any location
4. Click 🗑 to delete

**Storage:** Archives saved in `~/CodeVault/Archives/`

---

## Option B: Web Version (server)

For the server-hosted version, see `app.py` and `static/index.html`.

```bash
pip install flask gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

---

## Archived

These directories are always excluded:

`node_modules` · `.git` · `.next` · `dist` · `build` · `.venv` · `vendor` · `__pycache__` · `.turbo` · `.cache` · `.gradle` · `.idea` · `DerivedData` · `.DS_Store`

## Requirements

- **macOS:** Python 3.11+ (comes pre-installed on modern macOS)
- **Server:** Python 3 + Flask + Gunicorn
