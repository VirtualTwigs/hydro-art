#!/usr/bin/env bash
# Bulk-download NHDPlus HR + WBD archives to the NAS.
# Uses curl with resume support and 4 parallel downloads.
#
# Usage:
#   bash tools/bulk_download.sh                # download all
#   bash tools/bulk_download.sh --jobs 2       # limit parallelism
#
# Re-run safely — curl -C - resumes partial downloads, and the script
# skips files that already exist at full size.

set -euo pipefail

JOBS="${1:-4}"
if [[ "$1" == "--jobs" ]]; then JOBS="${2:-4}"; fi

LIST="/tmp/download_list.tsv"

if [[ ! -f "$LIST" ]]; then
    echo "ERROR: $LIST not found. Generate it first with:"
    echo "  PYTHONPATH=. .venv/bin/python -c \"...\""
    exit 1
fi

TOTAL=$(wc -l < "$LIST" | tr -d ' ')
echo "Downloading $TOTAL archives with $JOBS parallel jobs..."
echo "Output: /Volumes/home/data/incoming/"
echo ""

download_one() {
    local url="$1"
    local dest="$2"
    local dir
    dir=$(dirname "$dest")
    mkdir -p "$dir"

    # Skip if already downloaded (> 1MB, not a partial stub)
    if [[ -f "$dest" ]] && [[ $(stat -f%z "$dest" 2>/dev/null || echo 0) -gt 1000000 ]]; then
        echo "SKIP (exists): $(basename "$dest")"
        return 0
    fi

    echo "START: $(basename "$dest")"
    if curl -C - -L --retry 3 --retry-delay 5 -o "$dest" "$url" 2>/dev/null; then
        local size
        size=$(du -h "$dest" | cut -f1)
        echo "DONE:  $(basename "$dest") ($size)"
    else
        echo "FAIL:  $(basename "$dest")"
    fi
}
export -f download_one

# Run parallel downloads using xargs
# Tab-separated: URL\tDEST
cat "$LIST" | xargs -P "$JOBS" -L 1 bash -c 'download_one "$1" "$2"' _
echo ""
echo "=== Download complete ==="
echo "To extract, run:"
echo "  PYTHONPATH=. .venv/bin/python tools/bulk_download.py"
