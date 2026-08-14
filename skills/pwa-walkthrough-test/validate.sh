#!/usr/bin/env bash
# validate.sh — gate runner for PWA walkthrough specs
#
# Runs all 4 gates on each webm under test-results/walk-*:
#   G1  passed (test exited 0 — already gated by playwright)
#   G2  webm exists + duration 5-300s
#   G3  end-frame stable (no frozen modal — manual visual or text-OCR check)
#   G4  middle-frames diverse (catch home-grid loops)
#
# Usage:  bash validate.sh [test-results-dir]
set -e
ROOT="${1:-test-results}"
fail=0
shopt -s nullglob

for d in "$ROOT"/walk-*; do
  [ -d "$d" ] || continue
  webm="$d/video.webm"
  name=$(basename "$d")
  if [ ! -f "$webm" ]; then
    echo "✘ $name: G2 — no webm"
    fail=$((fail+1))
    continue
  fi
  dur=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 "$webm")
  durint=${dur%.*}
  if [ -z "$durint" ] || [ "$durint" -lt 5 ] || [ "$durint" -gt 300 ]; then
    echo "✘ $name: G2 — duration ${dur}s outside 5-300"
    fail=$((fail+1))
    continue
  fi

  # G3 — extract last frame, save for manual check
  end=$((durint - 1))
  ffmpeg -y -ss "$end" -i "$webm" -frames:v 1 -q:v 5 "$d/_end.jpg" 2>/dev/null

  # G4 — sample 5 evenly spaced frames; their JPEG sizes give a rough
  # diversity signal (home grid renders very consistent size; busy
  # screens vary)
  step=$((durint / 6))
  sizes=()
  for i in 1 2 3 4 5; do
    t=$((step * i))
    out="$d/_mid_${i}.jpg"
    ffmpeg -y -ss "$t" -i "$webm" -frames:v 1 -q:v 5 "$out" 2>/dev/null
    sizes+=("$(stat -c%s "$out")")
  done

  # Compute (max-min) / avg as a coarse "diversity" metric.
  # Home-grid loops produce tightly clustered sizes (low diversity).
  python3 - "${sizes[@]}" <<'PY' || fail=$((fail+1))
import sys
sizes = [int(x) for x in sys.argv[1:]]
avg = sum(sizes) / len(sizes)
spread = (max(sizes) - min(sizes)) / avg if avg else 0
print(f"  G4 size spread: {spread:.2%}", file=sys.stderr)
sys.exit(0 if spread > 0.05 else 1)
PY

  echo "✓ $(basename "$d"): G2 ${dur}s, G3 end frame at $d/_end.jpg, G4 mid frames at $d/_mid_*.jpg"
done

if [ "$fail" -gt 0 ]; then
  echo "$fail spec(s) failed validation. Manually review _end.jpg and _mid_*.jpg before concatenating."
  exit 1
fi
echo "All specs passed gates G2-G4. Manually verify _end.jpg + _mid_*.jpg images, then concat."
