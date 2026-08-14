#!/usr/bin/env bash
#
# video-bug-scan/prepare.sh
# ─────────────────────────
# Thin dispatcher onto `vk prepare` (claude-video-kit). Kept so the historic
# invocation keeps working:
#
#   bash ~/.claude/skills/video-bug-scan/prepare.sh <video> [work-dir]
#   VBS_WHISPER_MODEL=small bash .../prepare.sh <video>
#
# All the real work (ffprobe triage → ffmpeg frames + 16k mono wav → Whisper)
# lives in bin/vk.py so Linux, macOS and Windows run identical logic.
#
# Exit codes: 0 ok · 1 missing dependency · 2 bad args · 3 processing failure
set -euo pipefail

# ── locate the kit ────────────────────────────────────────────────────────
resolve_kit() {
  if [[ -n "${CLAUDE_VIDEO_KIT:-}" && -f "$CLAUDE_VIDEO_KIT/bin/vk.py" ]]; then
    echo "$CLAUDE_VIDEO_KIT"; return
  fi
  local marker="$HOME/.claude/video-kit.json"
  if [[ -f "$marker" ]]; then
    local p
    p=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('kitPath',''))" "$marker" 2>/dev/null || true)
    if [[ -n "$p" && -f "$p/bin/vk.py" ]]; then echo "$p"; return; fi
  fi
  # walk up from this script's physical location — the skill dir itself is usually
  # a symlink into the kit, so resolve with `pwd -P`, not just readlink on the file
  local src="${BASH_SOURCE[0]}" dir
  while [[ -L "$src" ]]; do src=$(readlink "$src"); done
  dir=$(cd "$(dirname "$src")" && pwd -P)
  while [[ "$dir" != "/" ]]; do
    [[ -f "$dir/bin/vk.py" ]] && { echo "$dir"; return; }
    dir=$(dirname "$dir")
  done
}

KIT=$(resolve_kit)
if [[ -z "${KIT:-}" ]]; then
  echo "error: claude-video-kit not found. Set CLAUDE_VIDEO_KIT=/path/to/claude-video-kit" >&2
  exit 1
fi

if [[ -x "$KIT/.venv/bin/python" ]]; then
  PY="$KIT/.venv/bin/python"          # kit venv — carries the whisper engine
else
  PY=$(command -v python3 || command -v python)
fi
[[ -n "$PY" ]] || { echo "error: python3 not found" >&2; exit 1; }

args=("$@")
[[ ${#args[@]} -ge 1 ]] || { echo "usage: $(basename "$0") <video-path> [work-dir]" >&2; exit 2; }

extra=()
[[ -n "${VBS_WHISPER_MODEL:-}" ]] && extra+=(--model "$VBS_WHISPER_MODEL")
[[ -n "${VBS_WHISPER_LANG:-}" ]]  && extra+=(--language "$VBS_WHISPER_LANG")

exec "$PY" "$KIT/bin/vk.py" prepare "${args[@]}" "${extra[@]}"
