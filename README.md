# CodeVault

A native macOS app to compress (archive) and restore codebases.

## What it does

- Drag & drop any folder to compress it into a compact `.tar.gz` archive
- Automatically excludes `node_modules`, `.git`, `.next`, `dist`, `build`, `.venv`, `vendor`, etc.
- Dashboard with stats: original size, compressed size, space saved, compression ratio
- Restore archives to any location you choose
- macOS notifications when operations complete

## Requirements

- macOS 14.0+
- Xcode 15+

## Setup (2 minutes)

### Option A: Manual Xcode project (recommended)

1. Copy all the `.swift` files to your Mac
2. Open Xcode → **File → New → Project**
3. Choose **macOS → App**
4. Configure:
   - **Name:** CodeVault
   - **Interface:** SwiftUI
   - **Language:** Swift
   - **Minimum Deployment:** macOS 14.0
   - Uncheck "Include Tests"
5. Delete the auto-generated `ContentView.swift` (we provide our own)
6. Drag all 7 `.swift` files into the project navigator:
   - `CodeVaultApp.swift`
   - `CodebaseArchive.swift`
   - `ArchiveManager.swift`
   - `ContentView.swift`
   - `ArchiveListView.swift`
   - `EmptyStateView.swift`
   - `RestoreView.swift`
7. Build and Run: **⌘R**

### Option B: Build from command line

```bash
cd /path/to/CodeVault
swift build -c release
```

## Source Files

| File | Purpose |
|---|---|
| `CodeVaultApp.swift` | App entry point |
| `CodebaseArchive.swift` | Data model — archive metadata & stats |
| `ArchiveManager.swift` | Core logic — compress, restore, list, delete |
| `ContentView.swift` | Main dashboard with stats sidebar |
| `ArchiveListView.swift` | Scrollable list of archives with search |
| `EmptyStateView.swift` | Drag & drop landing when no archives |
| `RestoreView.swift` | Sheet for choosing restore destination |

## Storage

Archives are stored locally at:
```
~/CodeVault/Archives/
```

Archive metadata (names, sizes, dates):
```
~/CodeVault/vault.json
```

Multiplied by the exclusions, most codebases shrink 80-95%.

## Excluded from Archives

These directories are always skipped:

`node_modules` · `.git` · `.next` · `.cache` · `.turbo` · `dist` · `build` · `coverage` · `.venv` · `vendor` · `__pycache__` · `.gradle` · `.idea` · `.vscode` · `DerivedData` · `.DS_Store`

## Notifications

The app requests notification permission on first launch. You'll get a macOS notification when an archive or restore operation completes.
