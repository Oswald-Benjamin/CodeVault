#!/usr/bin/env python3
"""
CodeVault — Standalone Local Mac Edition
A single-file web app for archiving and restoring local folders.
Runs entirely locally. No server needed.

Usage: python3 codevault.py
Then open http://127.0.0.1:5555 in your browser.
"""

import os
import sys
import json
import shutil
import hashlib
import tarfile
import threading
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import base64

# ─── Config ───────────────────────────────────────────────────────────────────

HOST = "127.0.0.1"
PORT = 5555
USERNAME = "admin"
PASSWORD = "codevault2026"
ARCHIVE_DIR = Path.home() / "CodeVault" / "Archives"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = Path.home() / "CodeVault" / "archives.json"
DB_FILE.parent.mkdir(parents=True, exist_ok=True)

# Directories to exclude from archives (never archive these)
EXCLUDE_DIRS = {
    "node_modules", ".git", ".next", "dist", "build", "coverage",
    ".venv", "venv", "__pycache__", ".cache", ".tox", ".mypy_cache",
    ".gradle", "vendor", "tmp", ".tmp", ".DS_Store",
}
EXCLUDE_FILES = {
    ".DS_Store", "Thumbs.db", ".env", ".env.local",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_dir_size(path):
    """Get actual byte size of a directory by walking all files.
    Uses st_size (apparent size) — matches what Finder shows."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        # Remove excluded dirs from traversal so we don't descend into them
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            if f in EXCLUDE_FILES:
                continue
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except (OSError, FileNotFoundError):
                pass
    return total


def human_size(size_bytes):
    """Convert bytes to human-readable string matching macOS Finder conventions (base-10)."""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)
    while size >= 1000 and unit_index < len(units) - 1:
        size /= 1000
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[unit_index]}"


def count_items(path):
    """Count total files and folders in a directory."""
    files = 0
    folders = 0
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        files += len(f for f in filenames if f not in EXCLUDE_FILES)
        folders += len(dirnames)
    return files, folders


def load_db():
    if DB_FILE.exists():
        try:
            return json.loads(DB_FILE.read_text())
        except Exception:
            return []
    return []


def save_db(data):
    DB_FILE.write_text(json.dumps(data, indent=2))


def encrypt_name(name):
    return hashlib.sha256(name.encode()).hexdigest()[:16]


def create_archive(src_path):
    """Create a tar.gz archive with smart exclusions. Returns (archive_path, original_size_bytes)."""
    src_path = Path(src_path).resolve()
    if not src_path.exists():
        return None, 0

    name = src_path.name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = name.replace(" ", "_").replace("/", "_")
    archive_name = f"{safe_name}_{timestamp}.tar.gz"
    archive_path = ARCHIVE_DIR / archive_name

    # Measure original folder size BEFORE archiving (including everything)
    original_size = get_dir_size(str(src_path))

    file_count, folder_count = count_items(str(src_path))

    with tarfile.open(archive_path, "w:gz") as tar:
        for dirpath, dirnames, filenames in os.walk(src_path):
            # Filter excluded directories in-place so os.walk doesn't descend into them
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for filename in filenames:
                if filename in EXCLUDE_FILES:
                    continue
                filepath = Path(dirpath) / filename
                arcname = filepath.relative_to(src_path.parent)
                try:
                    tar.add(filepath, arcname=arcname)
                except (OSError, FileNotFoundError):
                    pass

    archive_size = archive_path.stat().st_size
    ratio = ((original_size - archive_size) / original_size * 100) if original_size > 0 else 0

    record = {
        "id": encrypt_name(archive_name),
        "name": name,
        "original_path": str(src_path),
        "archive_file": str(archive_path),
        "original_size": original_size,       # bytes (uncompressed)
        "archive_size": archive_size,          # bytes (compressed)
        "ratio": round(ratio, 1),
        "file_count": file_count,
        "folder_count": folder_count,
        "created_at": timestamp,
    }

    db = load_db()
    db.insert(0, record)
    save_db(db)

    return archive_path, original_size


def restore_archive(archive_id, dest_dir=None):
    """Restore an archive to dest_dir or original location."""
    db = load_db()
    record = next((r for r in db if r["id"] == archive_id), None)
    if not record:
        return False

    src = Path(record["archive_file"])
    if not src.exists():
        return False

    if dest_dir:
        dest = Path(dest_dir).resolve()
    else:
        dest = Path(record["original_path"]).parent / record["name"]
        # Avoid overwriting — append _restored if exists
        if dest.exists():
            dest = dest.parent / f"{record['name']}_restored"

    dest.mkdir(parents=True, exist_ok=True)

    with tarfile.open(src, "r:gz") as tar:
        tar.extractall(dest)

    return True


def delete_archive(archive_id):
    """Delete an archive file and its database record."""
    db = load_db()
    record = next((r for r in db if r["id"] == archive_id), None)
    if not record:
        return False

    archive_path = Path(record["archive_file"])
    if archive_path.exists():
        archive_path.unlink()

    db = [r for r in db if r["id"] != archive_id]
    save_db(db)
    return True


def browse_directory(path):
    """List contents of a directory for the browser dialog."""
    p = Path(path)
    if not p.is_dir():
        return []

    items = []
    try:
        for item in sorted(p.iterdir()):
            try:
                is_dir = item.is_dir()
                size = get_dir_size(str(item)) if is_dir else item.stat().st_size
                items.append({
                    "name": item.name,
                    "is_dir": is_dir,
                    "size": size,
                    "size_human": human_size(size),
                })
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return items


# ─── HTTP Handler ─────────────────────────────────────────────────────────────

class CodeVaultHandler(SimpleHTTPRequestHandler):
    """Custom handler with Basic Auth and API routing."""

    def _check_auth(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        encoded = header[6:]
        decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
        user, _, pwd = decoded.partition(":")
        return user == USERNAME and pwd == PASSWORD

    def _send_auth_required(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="CodeVault"')
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>401 - Authorisation Required</h1>")

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._check_auth():
            return self._send_auth_required()

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/":
            return self._serve_index()
        elif path == "/api/archives":
            db = load_db()
            return self._send_json([{
                "id": r["id"],
                "name": r["name"],
                "original_size_human": human_size(r["original_size"]),
                "original_size_bytes": r["original_size"],
                "archive_size_human": human_size(r["archive_size"]),
                "archive_size_bytes": r["archive_size"],
                "ratio": r["ratio"],
                "file_count": r.get("file_count", 0),
                "folder_count": r.get("folder_count", 0),
                "created_at": r["created_at"],
            } for r in db])
        elif path == "/api/browse":
            qs = parse_qs(parsed.query)
            dirpath = unquote(qs.get("p", ["/"])[0])
            if not os.path.isdir(dirpath):
                return self._send_json([])
            items = browse_directory(dirpath)
            parent = str(Path(dirpath).parent) if dirpath != "/" else ""
            return self._send_json({"parent": parent, "current": dirpath, "items": items})
        elif path == "/api/stats":
            db = load_db()
            archives_total_original = sum(r["original_size"] for r in db)
            archives_total_compressed = sum(r["archive_size"] for r in db)
            savings = archives_total_original - archives_total_compressed
            return self._send_json({
                "total_archives": len(db),
                "total_original": human_size(archives_total_original),
                "total_original_bytes": archives_total_original,
                "total_compressed": human_size(archives_total_compressed),
                "total_compressed_bytes": archives_total_compressed,
                "total_savings": human_size(savings),
                "total_savings_bytes": savings,
                "archive_dir": str(ARCHIVE_DIR),
            })
        else:
            self.send_error(404)

    def do_POST(self):
        if not self._check_auth():
            return self._send_auth_required()

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if path == "/api/archive":
            src = data.get("path", "").strip()
            if not src or not os.path.isdir(src):
                return self._send_json({"error": "Invalid path"}, 400)

            def do_archive():
                create_archive(src)

            threading.Thread(target=do_archive, daemon=True).start()
            return self._send_json({"status": "archiving", "path": src})

    def do_DELETE(self):
        if not self._check_auth():
            return self._send_auth_required()

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/archive/"):
            archive_id = path[len("/api/archive/"):]
            success = delete_archive(archive_id)
            return self._send_json({"success": success})

    def do_PUT(self):
        if not self._check_auth():
            return self._send_auth_required()

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if path.startswith("/api/restore/"):
            archive_id = path[len("/api/restore/"):]
            dest = data.get("dest")
            success = restore_archive(archive_id, dest)
            return self._send_json({"success": success})

    def _serve_index(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode())

    def log_message(self, format, *args):
        """Silence default logging."""
        pass


# ─── HTML Frontend ────────────────────────────────────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CodeVault</title>
<style>
:root {
  --bg: #0f1117;
  --surface: #1a1d27;
  --surface2: #222633;
  --border: #2a2e3d;
  --text: #e4e6f0;
  --text2: #8b8fa3;
  --accent: #6c5ce7;
  --accent2: #a29bfe;
  --green: #00cec9;
  --red: #ff6b6b;
  --orange: #fdcb6e;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}
.header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 10;
}
.header h1 {
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent), var(--green));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.header .btn {
  background: var(--accent);
  color: white;
  border: none;
  padding: 8px 18px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.header .btn:hover { opacity: 0.85; }
.container { padding: 24px; max-width: 960px; margin: auto; }
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
}
.stat-card .label { font-size: 12px; color: var(--text2); margin-bottom: 6px; }
.stat-card .value { font-size: 22px; font-weight: 700; }
.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text2);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.archive-list { display: flex; flex-direction: column; gap: 8px; }
.archive-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 18px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: border-color 0.15s;
}
.archive-card:hover { border-color: var(--accent); }
.ac-icon {
  font-size: 28px;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface2);
  border-radius: 10px;
  flex-shrink: 0;
}
.ac-info { flex: 1; min-width: 0; }
.ac-name {
  font-weight: 600;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}
.ac-meta { font-size: 12px; color: var(--text2); }
.ac-arrow { color: var(--text2); font-size: 16px; margin: 0 4px; }
.ac-ratio {
  font-size: 13px;
  color: var(--green);
  font-weight: 600;
  white-space: nowrap;
}
.ac-actions { display: flex; gap: 6px; flex-shrink: 0; }
.ac-actions button {
  background: var(--surface2);
  color: var(--text);
  border: 1px solid var(--border);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.ac-actions button:hover { background: var(--border); }
.ac-actions .btn-del:hover { background: var(--red); color: white; border-color: var(--red); }
.empty {
  text-align: center;
  padding: 48px;
  color: var(--text2);
  font-size: 14px;
}
/* Modal */
.modal-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.65);
  z-index: 100;
  align-items: center;
  justify-content: center;
}
.modal-overlay.active { display: flex; }
.modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  width: 90%;
  max-width: 540px;
  max-height: 70vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.modal-header h3 { font-size: 15px; font-weight: 600; }
.modal-close {
  background: none;
  border: none;
  color: var(--text2);
  font-size: 20px;
  cursor: pointer;
}
.modal-body { padding: 0; overflow-y: auto; flex: 1; }
.browse-item {
  padding: 8px 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.1s;
}
.browse-item:hover { background: var(--surface2); }
.browse-item .icon { font-size: 16px; width: 20px; text-align: center; }
.browse-item .b-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.browse-item .b-size { color: var(--text2); font-size: 12px; white-space: nowrap; }
.modal-footer {
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.modal-footer .path {
  font-size: 12px;
  color: var(--text2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}
.modal-footer button {
  background: var(--accent);
  color: white;
  border: none;
  padding: 7px 18px;
  border-radius: 7px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: var(--surface2);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 12px 18px;
  border-radius: 9px;
  font-size: 13px;
  z-index: 200;
  animation: fadeIn 0.2s;
}
.toast.ok { border-color: var(--green); color: var(--green); }
.toast.err { border-color: var(--red); color: var(--red); }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.spin { animation: spin 1s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="header">
  <h1>🔐 CodeVault</h1>
  <button class="btn" onclick="openBrowse()">＋ Archive Folder</button>
</div>
<div class="container">
  <div id="stats" class="stats-grid"></div>
  <div class="section-title">Archives</div>
  <div id="archives" class="archive-list"><div class="empty"><span class="spin">⏳</span> Loading…</div></div>
</div>
<!-- Browse Modal -->
<div id="modal" class="modal-overlay">
  <div class="modal">
    <div class="modal-header">
      <h3>Select a folder to archive</h3>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div id="modalBody" class="modal-body"></div>
    <div class="modal-footer">
      <span id="modalPath" class="path"></span>
      <button onclick="confirmArchive()">Archive This Folder</button>
    </div>
  </div>
</div>
<script>
let selectedPath = '';

async function api(url, opts = {}) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts });
  return r.json();
}

function toast(msg, type = 'ok') {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

async function loadAll() {
  const [stats, archives] = await Promise.all([
    api('/api/stats'),
    api('/api/archives')
  ]);
  document.getElementById('stats').innerHTML = `
    <div class="stat-card"><div class="label">Archives</div><div class="value">${stats.total_archives}</div></div>
    <div class="stat-card"><div class="label">Original Size</div><div class="value">${stats.total_original}</div></div>
    <div class="stat-card"><div class="label">Compressed</div><div class="value">${stats.total_compressed}</div></div>
    <div class="stat-card"><div class="label">Space Saved</div><div class="value" style="color:var(--green)">${stats.total_savings}</div></div>
  `;
  const el = document.getElementById('archives');
  if (!archives.length) {
    el.innerHTML = '<div class="empty">No archives yet. Click "Archive Folder" to get started.</div>';
    return;
  }
  el.innerHTML = archives.map(a => `
    <div class="archive-card">
      <div class="ac-icon">📦</div>
      <div class="ac-info">
        <div class="ac-name">${a.name}</div>
        <div class="ac-meta">${a.file_count || '?'} files · ${a.folder_count || '?'} folders · ${a.created_at}</div>
      </div>
      <div style="text-align:right;white-space:nowrap">
        <div>${a.original_size_human} <span class="ac-arrow">→</span> ${a.archive_size_human}</div>
        <div class="ac-ratio">▼ ${a.ratio}%</div>
      </div>
      <div class="ac-actions">
        <button onclick="restore('${a.id}')">📥 Restore</button>
        <button class="btn-del" onclick="removeArc('${a.id}')">🗑 Delete</button>
      </div>
    </div>
  `).join('');
}

async function openBrowse() {
  const startPath = '/';
  document.getElementById('modal').classList.add('active');
  await loadBrowse(startPath);
}

async function loadBrowse(p) {
  const data = await api('/api/browse?p=' + encodeURIComponent(p));
  document.getElementById('modalPath').textContent = data.current;
  selectedPath = data.current;
  const body = document.getElementById('modalBody');
  let html = '';
  if (data.parent && data.parent !== data.current) {
    html += `<div class="browse-item" onclick="loadBrowse('${data.parent}')"><span class="icon">⬆️</span><span class="b-name">..</span></div>`;
  }
  for (const item of data.items) {
    if (item.is_dir) {
      html += `<div class="browse-item" onclick="loadBrowse('${data.current}/${item.name}')">
        <span class="icon">📁</span>
        <span class="b-name">${item.name}</span>
        <span class="b-size">${item.size_human}</span>
      </div>`;
    } else {
      html += `<div class="browse-item" style="opacity:0.45">
        <span class="icon">📄</span>
        <span class="b-name">${item.name}</span>
        <span class="b-size">${item.size_human}</span>
      </div>`;
    }
  }
  body.innerHTML = html;
}

function closeModal() {
  document.getElementById('modal').classList.remove('active');
}

function confirmArchive() {
  if (!selectedPath) return;
  api('/api/archive', { method: 'POST', body: JSON.stringify({ path: selectedPath }) });
  closeModal();
  toast('Archiving ' + selectedPath.split('/').pop() + '…');
  setTimeout(loadAll, 3000);
}

function restore(id) {
  api('/api/restore/' + id, { method: 'PUT', body: JSON.stringify({}) });
  toast('Restoring archive…');
}

function removeArc(id) {
  if (!confirm('Delete this archive permanently?')) return;
  api('/api/archive/' + id, { method: 'DELETE' });
  toast('Archive deleted');
  loadAll();
}

// Close modal on overlay click
document.getElementById('modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeModal();
});

loadAll();
</script>
</body>
</html>
"""

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("")
    print("  ╔══════════════════════════════════════╗")
    print("  ║        🔐  CodeVault v1.0            ║")
    print("  ║   Standalone Local Mac Edition       ║")
    print("  ╚══════════════════════════════════════╝")
    print(f"  Archives stored in: {ARCHIVE_DIR}")
    print(f"  URL: http://{HOST}:{PORT}")
    print(f"  Login: {USERNAME} / {PASSWORD}")
    print("")

    def open_browser():
        import time
        time.sleep(0.8)
        webbrowser.open(f"http://{HOST}:{PORT}")

    threading.Thread(target=open_browser, daemon=True).start()

    with HTTPServer((HOST, PORT), CodeVaultHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  CodeVault stopped.")
            sys.exit(0)


if __name__ == "__main__":
    main()
