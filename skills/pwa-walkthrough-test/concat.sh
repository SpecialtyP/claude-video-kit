#!/usr/bin/env bash
# concat.sh — webm → mp4 → concat pipeline.
#
# Usage:
#   bash concat.sh                                  # find walk-* in test-results/
#   bash concat.sh /path/to/output.mp4              # custom output
#   bash concat.sh out.mp4 v1 v2 v3 v4 v5 v6        # explicit order
set -e
OUT="${1:-/tmp/walkthrough-$(date +%Y%m%d-%H%M).mp4}"
shift || true

WORK=$(mktemp -d)
trap "rm -rf $WORK" EXIT

if [ "$#" -eq 0 ]; then
  # Auto-discover: each walk-* dir is one section. Order alphabetically.
  mapfile -t DIRS < <(find test-results -maxdepth 1 -type d -name "walk-*" 2>/dev/null | sort)
  if [ "${#DIRS[@]}" -eq 0 ]; then
    echo "no walk-* dirs in test-results/. Run the specs first." >&2
    exit 1
  fi
else
  DIRS=()
  for v in "$@"; do
    d=$(find test-results -path "*walk-${v}-*" -type d 2>/dev/null | head -1)
    [ -n "$d" ] && DIRS+=("$d")
  done
fi

echo "=== Found ${#DIRS[@]} sections ==="
LIST="$WORK/concat.txt"
i=0
for d in "${DIRS[@]}"; do
  webm="$d/video.webm"
  if [ ! -f "$webm" ]; then
    echo "  skip $d — no video.webm"
    continue
  fi
  mp4="$WORK/$(printf "%02d" $i).mp4"
  i=$((i+1))
  ffmpeg -y -i "$webm" -c:v libx264 -preset fast -crf 24 -pix_fmt yuv420p -an -movflags +faststart "$mp4" 2>&1 | tail -1
  echo "file '$mp4'" >> "$LIST"
  d_sec=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 "$webm")
  printf "  %s  %5.1fs\n" "$(basename "$d")" "$d_sec"
done

if [ ! -s "$LIST" ]; then
  echo "no usable webms found." >&2
  exit 1
fi

echo "=== Concatenating ==="
ffmpeg -y -f concat -safe 0 -i "$LIST" -c copy "$OUT" 2>&1 | tail -1
size=$(stat -c%s "$OUT")
dur=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 "$OUT")
printf "\n=== Final: %s\n  size: %d MB\n  duration: %s s\n" "$OUT" "$((size/1024/1024))" "$dur"
