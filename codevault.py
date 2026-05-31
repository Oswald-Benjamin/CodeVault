#!/usr/bin/env python3
"""
CodeVault — Standalone macOS app.
Double-click to run, or run from Terminal: python3 codevault.py

Stores compressed archives in ~/CodeVault/Archives/
Excludes: node_modules, .git, .next, dist, build, .venv, vendor, etc.
"""

import os
import re
import sys
import json
import shutil
import tarfile
import tempfile
import webbrowser
import threading
from pathlib import Path
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import base64

# ── Configuration ────────────────────────────────────────────────────────────

HOME = Path.home()
VAULT_DIR = HOME / "CodeVault"
ARCHIVES_DIR = VAULT_DIR / "Archives"
METADATA_FILE = VAULT_DIR / "vault.json"

EXCLUDES = {
    "node_modules", ".git", ".next", ".turbo", ".cache",
    "dist", "build", "coverage", ".venv", "vendor",
    "__pycache__", ".gradle", ".idea", "DerivedData",
    ".DS_Store", "tmp", "temp", ".Trash",
}

PORT = 40041  # Arbitrary high port

# Auth
AUTH_USER = "Cryptosi@protonmail.com"
AUTH_PASS = "Talent81"

# ── Helpers ─────────────────────────────────────────────────────────────────

VAULT_DIR.mkdir(exist_ok=True)
ARCHIVES_DIR.mkdir(exist_ok=True)


def fmt_bytes(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def calc_size(path):
    t = 0
    for e in path.rglob("*"):
        if any(p in EXCLUDES for p in e.parts):
            continue
        if e.is_file():
            try:
                t += e.stat().st_size
            except OSError:
                pass
    return t


def count_files(path):
    c = 0
    for e in path.rglob("*"):
        if any(p in EXCLUDES for p in e.parts):
            continue
        if e.is_file():
            c += 1
    return c


def should_exclude(name):
    return name in EXCLUDES or name.startswith(".")


def load_meta():
    if METADATA_FILE.exists():
        try:
            return json.loads(METADATA_FILE.read_text())
        except Exception:
            return []
    return []


def save_meta(data):
    METADATA_FILE.write_text(json.dumps(data, indent=2))


def create_archive(source_path):
    """Create a .tar.gz archive, excluding heavy directories."""
    name = source_path.name
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_name = f"{name}-{ts}.tar.gz"
    archive_path = ARCHIVES_DIR / archive_name

    orig_size = calc_size(source_path)
    file_count = count_files(source_path)

    def filter_func(tarinfo):
        parts = Path(tarinfo.name).parts
        if any(p in EXCLUDES for p in parts):
            return None
        return tarinfo

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(source_path, arcname=name, filter=filter_func)

    comp_size = archive_path.stat().st_size
    saved = orig_size - comp_size
    pct = round((1 - comp_size / orig_size) * 100, 1) if orig_size > 0 else 0

    entry = {
        "id": ts,
        "name": name,
        "orig": orig_size,
        "comp": comp_size,
        "saved": saved,
        "pct": pct,
        "fcount": file_count,
        "date": datetime.now(timezone.utc).isoformat(),
        "archiveFile": archive_name,
        "origPath": str(source_path),
    }

    meta = load_meta()
    meta.insert(0, entry)
    save_meta(meta)

    return entry


def extract_archive(archive_name, dest):
    """Extract .tar.gz archive to destination."""
    archive_path = ARCHIVES_DIR / archive_name
    if not archive_path.exists():
        return False
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as tar:
        # Security: prevent path traversal
        for member in tar.getmembers():
            member_path = (dest / member.name).resolve()
            if not str(member_path).startswith(str(dest.resolve())):
                continue
            tar.extract(member, path=str(dest))
    return True


# ── Frontend HTML ────────────────────────────────────────────────────────────

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CodeVault</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0d1117;--surface:#161b22;--surface-h:#1c2333;--border:#30363d;--text:#c9d1d9;--dim:#8b949e;--accent:#58a6ff;--green:#3fb950;--orange:#d29922;--red:#f85149;--purple:#bc8cff;--r:8px}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text)}
.app{display:flex;min-height:100vh}
.sidebar{width:260px;min-width:260px;background:var(--surface);border-right:1px solid var(--border);padding:20px;display:flex;flex-direction:column;gap:14px;position:sticky;top:0;height:100vh;overflow-y:auto}
.logo{display:flex;align-items:center;gap:10px}
.logo-icon{width:36px;height:36px;background:linear-gradient(135deg,#58a6ff,#bc8cff);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}
.logo h1{font-size:17px;font-weight:700}
.sc{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:12px}
.sc .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--dim);margin-bottom:3px}
.sc .val{font-size:22px;font-weight:700}
.sc .val.g{color:var(--green)}.sc .val.b{color:var(--accent)}.sc .val.o{color:var(--orange)}.sc .val.p{color:var(--purple)}
.sinfo{font-size:11px;color:var(--dim);margin-top:auto;padding-top:12px;border-top:1px solid var(--border)}
.main{padding:28px;flex:1;max-width:820px}
.hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
.hdr h2{font-size:20px;font-weight:600}
.btn{display:inline-flex;align-items:center;gap:5px;padding:7px 13px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface);color:var(--text);font-size:12px;font-weight:500;cursor:pointer;transition:all .15s}
.btn:hover{background:var(--surface-h)}
.btn-prim{background:var(--accent);color:#000;border-color:var(--accent)}
.btn-dng{color:var(--red)}.btn-dng:hover{background:rgba(248,81,73,.1)}
.btn-sm{padding:4px 9px;font-size:11px}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-explore{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:7px 13px;border-radius:var(--r);font-size:12px;cursor:pointer;width:100%;text-align:left;display:flex;align-items:center;gap:6px}
.btn-explore:hover{background:var(--surface-h)}
.sbox{position:relative;margin-bottom:14px}
.sbox input{width:100%;padding:8px 10px 8px 32px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);color:var(--text);font-size:13px;outline:none}
.sbox input:focus{border-color:var(--accent)}
.sbox .ic{position:absolute;left:9px;top:50%;transform:translateY(-50%);font-size:12px;color:var(--dim)}
.alist{display:flex;flex-direction:column;gap:7px}
.acard{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:13px;display:flex;align-items:center;gap:11px}
.acard:hover{border-color:var(--dim)}
.aicon{width:40px;height:40px;background:linear-gradient(135deg,rgba(88,166,255,.1),rgba(188,140,255,.1));border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0}
.ainfo{flex:1;min-width:0}
.aname{font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cbar{width:100%;height:3px;background:rgba(210,153,34,.2);border-radius:2px;margin-top:5px;overflow:hidden}
.cbar .f{height:100%;background:var(--green);border-radius:2px;transition:width .3s}
.ameta{font-size:10px;color:(--dim);margin-top:5px;display:flex;gap:9px;flex-wrap:wrap;align-items:center}
.badge{display:inline-flex;align-items:center;gap:3px;padding:2px 6px;border-radius:9px;font-size:10px;font-weight:600;background:rgba(63,185,80,.1);color:var(--green)}
.aacts{display:flex;gap:4px;flex-shrink:0}
.empty{text-align:center;padding:60px 20px;border:2px dashed var(--border);border-radius:12px}.empty .ei{font-size:40px;margin-bottom:10px}
.empty h3{font-size:16px;margin-bottom:5px}.empty p{color:var(--dim);font-size:13px}
.excludes{margin-top:12px;font-size:11px;color:var(--dim)}
/* modal */
.moverlay{position:fixed;inset:0;background:rgba(0,0,0,.55);display:none;align-items:center;justify-content:center;z-index:100;backdrop-filter:blur(3px)}
.moverlay.open{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:24px;width:500px;max-width:92vw}
.modal h3{font-size:16px;margin-bottom:8px}
.modal p{font-size:12px;color:var(--dim);margin-bottom:12px}
.browser{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);max-height:280px;overflow-y:auto;margin-bottom:12px}
.bitem{padding:7px 11px;cursor:pointer;display:flex;align-items:center;gap:7px;font-size:12px;border-bottom:1px solid var(--border)}
.bitem:hover{background:var(--surface-h)}
.bitem .fi{color:var(--accent)}
.mactions{display:flex;justify-content:flex-end;gap:7px}
.path-bar{font-size:11px;color:var(--dim);font-family:'SF Mono',monospace;margin-bottom:7px;word-break:break-all;background:var(--bg);padding:5px 8px;border-radius:var(--r);border:1px solid var(--border)}
/* drop */
.dropzone{border:2px dashed var(--border);border-radius:10px;padding:24px;text-align:center;margin-bottom:18px;transition:all .2s;cursor:pointer}
.dropzone.drag{border-color:var(--accent);background:rgba(88,166,255,.05)}
.dropzone .di{font-size:28px;margin-bottom:6px}
.dropzone p{font-size:13px;color:var(--dim)}
/* status */
.sbar{position:fixed;bottom:0;left:0;right:0;padding:7px 20px;background:var(--surface);border-top:1px solid var(--border);font-size:11px;color:var(--dim);display:flex;align-items:center;gap:7px;z-index:50}
.sbar .spin{width:12px;height:12px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:sp .8s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
@media(max-width:680px){.sidebar{display:none}.main{padding:16px}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar">
  <div class="logo"><div class="logo-icon">📦</div><h1>CodeVault</h1></div>
  <div class="sc"><div class="lbl">Archives</div><div class="val" id="sc">0</div></div>
  <div class="sc"><div class="lbl">Original</div><div class="val o" id="so">—</div></div>
  <div class="sc"><div class="lbl">Compressed</div><div class="val b" id="sp">—</div></div>
  <div class="sc"><div class="lbl">Saved</div><div class="val g" id="ss">—</div></div>
  <div class="sc"><div class="lbl">Avg Reduction</div><div class="val p" id="sr">—</div></div>
  <div class="sinfo">Local storage:<br><code>~/CodeVault/</code><br><br>Running on localhost</div>
</aside>
<main class="main">
  <div class="hdr"><h2>Archives</h2><button class="btn btn-prim" onclick="openAM()">📁 Archive Folder</button></div>

  <div class="dropzone" id="dz" ondragover="dz.classList.add('drag');event.preventDefault()" ondragleave="dz.classList.remove('drag')" ondrop="handleDrop(event)">
    <div class="di">📦</div><p>Drag &amp; drop a folder here to archive it</p>
  </div>

  <div class="sbox"><span class="ic">🔍</span>
    <input id="q" placeholder="Search archives…" oninput="renderA()">
  </div>
  <div id="content"></div>
</main>
</div>
<div class="sbar" id="sbar" style="display:none"><div class="spin" id="sspin"></div><span id="stxt"></span></div>

<div class="moverlay" id="amod">
  <div class="modal">
    <h3>📁 Choose Folder</h3>
    <p>Navigate to a folder to archive. node_modules, .git, .next, etc. are automatically excluded.</p>
    <div class="path-bar" id="apath">/</div>
    <div class="browser" id="alist"></div>
    <div class="mactions">
      <button class="btn" onclick="closeAM()">Cancel</button>
      <button class="btn btn-prim" id="abtn" disabled onclick="doArchive()">Archive This Folder</button>
    </div>
  </div>
</div>

<div class="moverlay" id="rmod">
  <div class="modal">
    <h3>📥 Restore Archive</h3>
    <p id="rname" style="font-weight:600;margin-bottom:3px"></p>
    <p>Choose where to extract contents.</p>
    <div class="path-bar" id="rpath">/</div>
    <div class="browser" id="rlist"></div>
    <div class="mactions">
      <button class="btn" onclick="closeRM()">Cancel</button>
      <button class="btn btn-prim" id="rbtn" disabled onclick="doRestore()">Restore Here</button>
    </div>
  </div>
</div>

<script>
let archs=[],curAP="",curRP="",curA=null;

function fb(n){const u=["B","KB","MB","GB","TB"];let i=0;while(Math.abs(n)>=1024&&i<u.length-1){n/=1024;i++}return n.toFixed(1)+" "+u[i]}
function ta(iso){const d=Date.now()-new Date(iso).getTime();if(d<6e4)return"just now";if(d<36e5)return Math.floor(d/6e4)+"m ago";if(d<864e5)return Math.floor(d/36e5)+"h ago";return Math.floor(d/864e5)+"d ago"}
function stat(t,w){const b=document.getElementById("sbar"),s=document.getElementById("sspin"),x=document.getElementById("stxt");b.style.display="flex";s.style.display=w?"block":"none";x.textContent=t;if(!w)setTimeout(()=>b.style.display="none",4000)}

async function api(u,opt={}){const r=await fetch(u,{...opt,headers:{...opt.headers,"Authorization":"Basic "+btoa("Cryptosi@protonmail.com:Talent81")}});return r.json()}

async function loadA(){try{const d=await api("/api/archives");archs=d.archives||[];renderS(d.stats);renderA()}catch(e){console.error(e)}}
function renderS(s){document.getElementById("sc").textContent=s.totalArchives||0;document.getElementById("so").textContent=s.totalOriginal?fb(s.totalOriginal):"—";document.getElementById("sp").textContent=s.totalCompressed?fb(s.totalCompressed):"—";document.getElementById("ss").textContent=s.totalSaved?fb(s.totalSaved):"—";document.getElementById("sr").textContent=s.totalOriginal>0?Math.round((1-s.totalCompressed/s.totalOriginal)*100)+"%":"—"}

function renderA(){
  const q=document.getElementById("q").value.toLowerCase(),f=archs.filter(a=>a.name.toLowerCase().includes(q)),c=document.getElementById("content");
  if(!f.length){c.innerHTML=`<div class="empty"><div class="ei">📦</div><h3>${archs.length?"No matches":"No archives yet"}</h3><p>${archs.length?"Try a different search":"Drop a folder above or click Archive Folder."}</p>${archs.length?"":'<div class="excludes">Excludes: node_modules · .git · .next · dist · build · ·venv · vendor</div>'}</div>`;return}
  c.innerHTML=f.map(a=>`<div class="acard"><div class="aicon">📦</div><div class="ainfo"><div class="aname">${esc(a.name)}</div><div class="cbar"><div class="f" style="width:${100-(a.pct||0)}%"></div></div><div class="ameta"><span>📄 ${fb(a.orig)}</span><span>→</span><span>📦 ${fb(a.comp)}</span><span class="badge">▼ ${a.pct}%</span><span>🕐 ${ta(a.date)}</span></div></div><div class="aacts"><button class="btn btn-sm" onclick="openRM('${a.id}')" title="Restore">📥</button><button class="btn btn-sm btn-dng" onclick="delA('${a.id}')" title="Delete">🗑</button></div></div>`).join("")
}
function esc(s){const d=document.createElement("div");d.textContent=s;return d.innerHTML}

// Drag & drop
async function handleDrop(e){e.preventDefault();document.getElementById("dz").classList.remove("drag");const items=e.dataTransfer.items;for(const item of items){if(item.kind==="file"){const entry=item.webkitGetAsEntry();if(entry&&entry.isDirectory){stat("Archiving…",true);try{const d=await api("/api/archive",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sourcePath:entry.fullPath})});d.success?stat(`Archived ${d.archive.name} — saved ${fb(d.archive.saved)}`):stat("Error");loadA()}catch(e){stat("Error: "+e.message)}}}}}

// Archive
async function browseA(p){curAP=p;document.getElementById("apath").textContent=p;document.getElementById("abtn").disabled=false;document.getElementById("alist").innerHTML="Loading…";try{const d=await api("/api/browse?path="+encodeURIComponent(p));let h="";if(d.parent&&d.parent!==d.current)h+=`<div class="bitem" onclick="browseA('${d.parent}')"><span class="fi">⬆️</span> …</div>`;d.dirs.forEach(x=>h+=`<div class="bitem" onclick="browseA('${x.path}')"><span class="fi">📁</span> ${esc(x.name)}</div>`);document.getElementById("alist").innerHTML=h||"Empty"}catch(e){console.error(e)}}
function openAM(){document.getElementById("amod").classList.add("open");browseA("/Users")}function closeAM(){document.getElementById("amod").classList.remove("open")}
async function doArchive(){stat("Archiving…",true);closeAM();try{const d=await api("/api/archive",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sourcePath:curAP})});d.success?stat(`Archived ${d.archive.name} — ${d.archive.pct}% saved`):stat("Error");loadA()}catch(e){stat("Error: "+e.message)}}

// Restore
async function browseR(p){curRP=p;document.getElementById("rpath").textContent=p;document.getElementById("rbtn").disabled=false;document.getElementById("rlist").innerHTML="Loading…";try{const d=await api("/api/browse?path="+encodeURIComponent(p));let h="";if(d.parent&&d.parent!==d.current)h+=`<div class="bitem" onclick="browseR('${d.parent}')"><span class="fi">⬆️</span> …</div>`;d.dirs.forEach(x=>h+=`<div class="bitem" onclick="browseR('${x.path}')"><span class="fi">📁</span> ${esc(x.name)}</div>`);document.getElementById("rlist").innerHTML=h||"Empty"}catch(e){console.error(e)}}
function openRM(id){curA=archs.find(a=>a.id===id);if(!curA)return;document.getElementById("rname").textContent=`${curA.name} — ${fb(curA.comp)}`;document.getElementById("rmod").classList.add("open");browseR("/Users")}function closeRM(){document.getElementById("rmod").classList.remove("open")}
async function doRestore(){if(!curA)return;stat("Restoring…",true);closeRM();try{const d=await api("/api/restore/"+curA.id,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({dest:curRP})});d.success?stat(`Restored ${curA.name}`):stat("Error");loadA()}catch(e){stat("Error: "+e.message)}}

// Delete
async function delA(id){if(!confirm("Delete permanently?"))return;try{await api("/api/delete/"+id,{method:"DELETE"});stat("Deleted");loadA()}catch(e){stat("Error")}}

// Quick-pick common macOS folders
async function quickPick(p){document.getElementById("amod").classList.add("open");browseA(p)}

loadA();
</script>
</body>
</html>"""


# ── HTTP Server ──────────────────────────────────────────────────────────────

class Handler(SimpleHTTPRequestHandler):
    """Combined static file + API handler."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        # Serve frontend
        if path == "/" or path == "/index.html":
            self._html(PAGE)
            return

        # API: list archives
        if path == "/api/archives":
            self._api(self._get_archives)
            return

        # API: browse
        if path == "/api/browse":
            self._api(self._browse, parse_qs(parsed.query))
            return

        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/archive":
            self._api(self._create_archive)
            return

        m = re.match(r"^/api/restore/(\w+)$", path)
        if m:
            self._api(lambda: self._restore_archive(m.group(1)))
            return

        self.send_error(404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        m = re.match(r"^/api/delete/(\w+)$", path)
        if m:
            self._api(lambda: self._delete_archive(m.group(1)))
            return

        self.send_error(404)

    # ── API handlers ──────────────────────────────────────────────────────

    def _get_archives(self):
        a = load_meta()
        return {
            "archives": a,
            "stats": {
                "totalArchives": len(a),
                "totalOriginal": sum(x["orig"] for x in a),
                "totalCompressed": sum(x["comp"] for x in a),
                "totalSaved": sum(x["orig"] - x["comp"] for x in a),
            },
        }

    def _browse(self, params):
        p = Path(params.get("path", [str(HOME)])[0]).expanduser().resolve()
        if not p.is_dir():
            return {"dirs": [], "current": str(p)}
        dirs = []
        try:
            for e in sorted(p.iterdir()):
                if e.is_dir() and not should_exclude(e.name):
                    dirs.append({"name": e.name, "path": str(e)})
        except PermissionError:
            pass
        return {"dirs": dirs, "current": str(p), "parent": str(p.parent)}

    def _create_archive(self):
        body = self._body()
        src = Path(body["sourcePath"]).expanduser().resolve()
        if not src.is_dir():
            return {"error": "Not a directory"}, 400
        entry = create_archive(src)
        return {"success": True, "archive": entry}

    def _restore_archive(self, aid):
        body = self._body()
        dest = Path(body.get("dest", str(HOME))).expanduser().resolve()
        meta = load_meta()
        a = next((x for x in meta if x["id"] == aid), None)
        if not a:
            return {"error": "Not found"}, 404
        if extract_archive(a["archiveFile"], dest):
            return {"success": True}
        return {"error": "Restore failed"}, 500

    def _delete_archive(self, aid):
        meta = load_meta()
        a = next((x for x in meta if x["id"] == aid), None)
        if not a:
            return {"error": "Not found"}, 404
        ap = ARCHIVES_DIR / a["archiveFile"]
        if ap.exists():
            ap.unlink()
        save_meta([x for x in meta if x["id"] != aid])
        return {"success": True}

    # ── Auth ───────────────────────────────────────────────────────────────

    def _check_auth(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                user, passwd = base64.b64decode(auth[6:]).decode().split(":", 1)
                if user == AUTH_USER and passwd == AUTH_PASS:
                    return True
            except Exception:
                pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="CodeVault"')
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Authentication required")
        return False

    # ── Helpers ────────────────────────────────────────────────────────────

    def _api(self, handler, *args):
        if not self._check_auth():
            return
        try:
            result = handler(*args)
            status = 200
            if isinstance(result, tuple):
                result, status = result
            body = json.dumps(result).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            body = json.dumps({"error": str(e)}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    def _html(self, content):
        if not self._check_auth():
            return
        body = content.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def log_message(self, format, *args):
        pass  # Suppress log noise


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("")
    print("  ╔══════════════════════════════════════╗")
    print("  ║         CodeVault is running         ║")
    print("  ╠══════════════════════════════════════╣")
    print(f"  ║  URL:   http://localhost:{PORT}       ║")
    print(f"  ║  User:  {AUTH_USER}    ║")
    print(f"  ║  Pass:  {AUTH_PASS}                  ║")
    print("  ╠══════════════════════════════════════╣")
    print("  ║  Archives: ~/CodeVault/Archives/    ║")
    print("  ║  Quit: Ctrl+C                       ║")
    print("  ╚══════════════════════════════════════╝")
    print("")

    # Open browser
    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()

    server = HTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCodeVault stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
