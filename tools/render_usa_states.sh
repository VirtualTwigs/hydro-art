#!/bin/bash
# Render each lower-48 state individually, then composite into one USA image.
# Usage: bash tools/render_usa_states.sh
set -e
cd "$(dirname "$0")/.."

PY=.venv/bin/python
OUT=output/usa-states
PNG_SIZE=4096
mkdir -p "$OUT"

STATES=(
  Oregon Washington California Idaho
  Montana Wyoming Nevada Utah Colorado
  Arizona "New Mexico"
  "North Dakota" "South Dakota" Nebraska Kansas
  Oklahoma Texas Minnesota Iowa Missouri
  Arkansas Louisiana
  Maine "New Hampshire" Vermont Massachusetts
  "Rhode Island" Connecticut "New York" "New Jersey"
  Pennsylvania Delaware Maryland
  Virginia "West Virginia"
  "North Carolina" "South Carolina" Georgia
  Florida Alabama Mississippi Tennessee Kentucky
  Ohio Indiana Illinois Michigan Wisconsin
)

TOTAL=${#STATES[@]}
DONE=0
FAIL=0

for state in "${STATES[@]}"; do
  DONE=$((DONE + 1))
  # Pipeline names output as lowercase region, e.g. "new york.svg"
  slug=$(echo "$state" | tr '[:upper:]' '[:lower:]')
  svg="$OUT/${slug}.svg"
  png="$OUT/${slug}.png"

  if [ -f "$svg" ] && [ -f "$png" ]; then
    echo "[$DONE/$TOTAL] SKIP $state (already rendered)"
    continue
  fi

  echo "[$DONE/$TOTAL] Rendering $state ..."
  if $PY build.py \
      --region "$state" \
      --palette neon --glow \
      --output svg png --png-size "$PNG_SIZE" \
      --output-dir "$OUT" 2>&1 | tail -3; then
    echo "  PASS $state"
  else
    echo "  FAIL $state (exit $?)"
    FAIL=$((FAIL + 1))
  fi
  echo
done

echo "=== Done: $((DONE - FAIL))/$TOTAL passed, $FAIL failed ==="

if [ "$FAIL" -eq 0 ]; then
  echo "Compositing..."
  $PY tools/composite_usa.py --dir "$OUT" --output output/usa-composite.png --size 8192
else
  echo "Some states failed — composite skipped. Fix failures and re-run."
  echo "Partial composite of successful states:"
  $PY tools/composite_usa.py --dir "$OUT" --output output/usa-composite-partial.png --size 8192
fi
