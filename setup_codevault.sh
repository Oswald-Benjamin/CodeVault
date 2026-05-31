#!/bin/bash
# setup_codevault.sh — Build CodeVault on macOS
#
# Prerequisite: Xcode 15+ installed
#
# Usage:
#   1. Copy the CodeVault/ folder to your Mac
#   2. Open Terminal, cd to the folder containing this script
#   3. chmod +x setup_codevault.sh && ./setup_codevault.sh
#   4. Open CodeVault.xcodeproj and Build (⌘B)
#
#   Alternatively, quick-build with no script:
#     mkdir -p CodeVault && cd CodeVault
#     # place all .swift files here
#     swift build  # if using SPM, or just open in Xcode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "CodeVault source files are in: ${SCRIPT_DIR}"
echo ""
echo "Files:"
ls -la "${SCRIPT_DIR}"/*.swift 2>/dev/null || echo "  (No .swift files found in script directory)"
echo ""
echo "Recommended: Create a new Xcode project manually"
echo "  1. Open Xcode → File → New → Project → macOS → App"
echo "  2. Name: CodeVault, Interface: SwiftUI, Language: Swift"
echo "  3. Replace the generated files with the .swift files from this folder"
echo "  4. Set minimum deployment: macOS 14.0"
echo "  5. Build & Run (⌘R)"
