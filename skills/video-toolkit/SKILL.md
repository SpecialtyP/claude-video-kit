---
name: video-toolkit
description: Base toolbox for processing existing video/audio on this machine — probe, extract frames, extract audio, transcribe with Whisper, download a remote recording, and the ffmpeg recipes for trimming/concat/format conversion. Use whenever a task involves reading, analyzing, transcribing, cutting or converting a video or audio file that already exists (a screen recording, a meeting recording, a clip a user sent). Not for authoring new motion graphics — that is HyperFrames.
allowed-tools: Bash, Read, Write, Glob, Grep
---

# video-toolkit

The shared, cross-platform layer every video skill in this kit sits on. Same commands on
Linux, macOS and Windows: one Python CLI (`vk`) wrapping ffmpeg/ffprobe/Whisper, plus the raw
ffmpeg recipes for the cases the CLI does not cover.

## 0 · Preflight (run once per machine, not per task)

```bash
vk doctor          # ✓/✗ per dependency + install hint for this OS
vk doctor --json   # machine-readable; gate scripts on .ok
```

If `vk` is not on PATH: `python3 "$CLAUDE_VIDEO_KIT/bin/vk.py" doctor`
(Windows: `python "%CLAUDE_VIDEO_KIT%\bin\vk.py" doctor`).

Required: `ffmpeg`, `ffprobe`, Python 3.9+, one Whisper engine.
Optional: `node` (unlocks the `hyperframes` engine + authoring), `yt-dlp` (downloads), ImageMagick.

## 1 · The `vk` verbs

| Need | Command |
|---|---|
| What is this file? | `vk probe clip.mp4` → JSON (duration, codecs, resolution, has_audio, audio_clipped) |
| Look at the content | `vk frames clip.mp4 -o ./frames --fps auto` |
| Audio for STT | `vk audio clip.mp4 -o audio.wav` (16 kHz mono) |
| Transcript | `vk transcribe audio.wav --model small --language es --format srt` |
| All of the above | `vk prepare clip.mp4 [workdir]` |

`vk prepare` is the default entry point for "analyze this recording": it probes, extracts frames
at an adaptive rate, pulls a 16 kHz mono WAV, transcribes it, and writes `probe.json`,
`prepare.json`, `frame_XXX.jpg`, `audio.wav`, `audio.srt` into the work dir.

**Adaptive frame rate** (`--fps auto`): ≤3 min → `1/3`; ≤10 min → `1/5`; longer → `1/10`.
Override with `--fps 1/2` or `--fps 2` when you need denser sampling of a fast interaction.

**Reading frames:** use the `Read` tool on a *sample* (`frame_002.jpg`, `frame_006.jpg`, …), not
every frame. Jump in spaced steps, then narrow around the interesting state. Delete the frame dir
when done — they are cheap to regenerate and expensive to keep.

## 2 · Whisper engines and the language rule

`vk transcribe` tries engines in this order, so the same command works on a machine with any of
them installed (`--engine` pins one explicitly):

| Engine | What it is | Install |
|---|---|---|
| `whisper` | openai-whisper CLI (PyTorch) | `pip install openai-whisper` (~2.5 GB w/ torch) |
| `faster` | faster-whisper / CTranslate2 | `pip install faster-whisper` (~200 MB, no torch) — **default for macOS/Windows** |
| `hyperframes` | `npx hyperframes transcribe`, bundles whisper.cpp | nothing to install beyond Node ≥ 22 |

Models: `tiny` (75 MB) · `base` (142 MB) · `small` (466 MB) · `medium` (1.5 GB) · `large-v3` (3.1 GB).
Start at `base` for clear narration, `small` for accents or Spanish, `medium` for music/noise.

**Language rule (non-negotiable):** the `.en` models (`base.en`, `small.en`, …) *translate*
non-English audio into English and silently destroy the original. For Spanish audio use a plain
model plus `--language es`. When the language is unknown, use a plain model and let it detect.

First run of any model downloads it; expect a delay, not a hang.

## 3 · Downloading a remote recording

`yt-dlp` handles YouTube, Loom, Vimeo and — the useful one — session-gated recordings such as
Zoom, by borrowing the cookies of a browser you are already logged into:

```bash
yt-dlp --cookies-from-browser chrome -F "$URL"    # probe formats, no download
yt-dlp --cookies-from-browser chrome -o "Recording.%(ext)s" "$URL"
```

Browser flag values: `chrome` | `chromium` | `brave` | `vivaldi` | `edge` | `firefox`. On Linux the
keyring (gnome-keyring / kwallet) may prompt. If cookies are rejected, the session simply is not
open in that browser — re-login and retry rather than scripting around it.

Only download recordings the user is entitled to. Do not redistribute them.

## 4 · ffmpeg recipes worth not re-deriving

```bash
# Trim without re-encoding (keyframe-aligned, instant)
ffmpeg -ss 00:01:30 -to 00:02:45 -i in.mp4 -c copy out.mp4

# Trim frame-accurate (re-encodes)
ffmpeg -ss 00:01:30 -to 00:02:45 -i in.mp4 -c:v libx264 -crf 20 -c:a aac out.mp4

# Concat same-codec clips
printf "file '%s'\n" a.mp4 b.mp4 > list.txt && ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4

# webm (Playwright recordings) → mp4
ffmpeg -i in.webm -c:v libx264 -pix_fmt yuv420p -crf 22 -an out.mp4

# Shrink a screen recording for review/sharing
ffmpeg -i in.mp4 -vf "scale=iw*0.5:ih*0.5" -c:v libx264 -crf 28 -preset veryfast out.mp4

# Burn an SRT into the picture
ffmpeg -i in.mp4 -vf "subtitles=audio.srt:force_style='FontSize=18'" -c:a copy out.mp4

# Single frame at a timestamp
ffmpeg -ss 00:00:42 -i in.mp4 -frames:v 1 -q:v 2 frame.jpg

# Contact sheet (fast visual scan of a long recording)
ffmpeg -i in.mp4 -vf "fps=1/30,scale=320:-1,tile=4x4" -frames:v 1 sheet.jpg
```

Always pass `-hide_banner -loglevel error` in scripts, and `-y` when overwriting is intended.

## 5 · Which skill for what

| Input | Skill |
|---|---|
| Class, lecture, webinar, course module, meeting or talk to summarize | `recording-brief` |
| Any other existing clip — transcribe, cut, convert, sample frames | this skill, directly |
| Author a new video / motion graphic from scratch | HyperFrames pack (`npx hyperframes`) — not this kit |

## 6 · Gotchas

- **Audio shorter than video** — WhatsApp and some screen recorders clip the audio track.
  `vk probe` reports `audio_clipped: true`; treat the silent tail as frame-only evidence.
- **No audio stream at all** — `vk prepare` skips transcription instead of failing. Say so in the
  report rather than inventing narration.
- **Never let the transcript override the frames.** Quote the narrator verbatim, but confirm every
  UI claim against a frame.
- **Windows**: the `.sh` helpers in this kit need Git Bash or WSL; the `vk` CLI and `.cmd` wrappers
  are native. Prefer `vk`.
- **Long recordings**: transcribe the extracted 16 kHz WAV, not the mp4 — it is faster and avoids
  container quirks.
