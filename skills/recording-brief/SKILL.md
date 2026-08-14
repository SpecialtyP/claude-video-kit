---
name: recording-brief
description: Download a recorded session (Zoom, Meet, Loom, YouTube, or a local file), analyze it locally — frames + transcript — and write a study/meeting brief. Use when the user asks to "download the recording", "summarize this class/meeting/webinar", "prepare for the exam with the video", or hands over a link to a session-gated recording. Handles login-gated recordings by reusing the browser's cookies via yt-dlp.
allowed-tools: Bash, Read, Write, Glob, Grep
---

# recording-brief

Turn a recorded session into a written brief you can study or act on. The trick that makes this
work on gated platforms: **yt-dlp can reuse the cookies of a browser you are already logged into**,
so no screen-recording of a playback and no JS injection.

Depends on `video-toolkit` (ffmpeg/ffprobe/Whisper via `vk`) and `yt-dlp`. Check with `vk doctor`.

## 1 · Get the URL

If the recording is open in a browser tab, ask the user for the URL, or pull it from a browser-MCP
snapshot (`browsermcp` / `blueprint`). Snapshots of player pages are large — never read one whole:

```bash
head -5 "$SNAPSHOT"                                     # → "Page URL: https://…"
grep -niE "video|transcript|download|descargar" "$SNAPSHOT" | head
```

Valid Zoom shapes: `https://<org>.zoom.us/rec/play/<ID>` or `/rec/share/<ID>`.

## 2 · Identify the logged-in browser

```bash
ps -eo comm | grep -iE 'chrome|chromium|brave|vivaldi|firefox|msedge' | sort | uniq -c   # Linux/macOS
```

Windows: `Get-Process | Where-Object { $_.Name -match 'chrome|msedge|firefox|brave' }`.

Map to the yt-dlp flag: `chrome` | `chromium` | `brave` | `vivaldi` | `edge` | `firefox`.

## 3 · Probe formats before downloading

```bash
yt-dlp --cookies-from-browser chrome -F "$URL"
```

Expect an mp4 `view` format. A login/cookie error means the session is not open in *that* browser —
have the user log in and retry; do not work around it.

## 4 · Download

```bash
yt-dlp --cookies-from-browser chrome -o "Recording <topic-or-date>.%(ext)s" "$URL"
```

## 5 · Analyze locally

```bash
vk prepare "Recording <topic>.mp4" ./_work --model small --language es    # non-English → plain model + --language
```

That yields `probe.json`, sampled frames, `audio.wav`, `audio.srt`. Two evidence streams:

- **Transcript** — what was *said*. Quote the speaker verbatim when they flag something as
  important ("this is on the exam", "give the result with units", "we ship Friday").
- **Frames** — what was *shown*. `Read` a spaced sample to recover diagrams, exact configuration
  dialogs, parameter values and result screens the audio never states. This is where the numbers
  live.

If the platform already exposes a transcript (Zoom often does, in the page snapshot), use it as the
text source and skip Whisper — it is faster and usually better punctuated. Still walk the frames.

## 6 · Write the brief

Write `BRIEF-<topic>.md` next to the recording:

- **Header** — source, file, duration, generated artifacts.
- **Weighting / stakes** — whatever the speaker said counts (exam weights, deadlines, owners).
- **Core concepts** — tables: technique → when to use it.
- **Worked cases** — step by step, with the exact parameters read off the frames.
- **✅ Verified on screen** — values and results confirmed from frames, marked as such.
- **Open questions** — anything the recording left ambiguous.
- **Checklist** — the actionable residue.

Cite timestamps (`[00:14:22]`) for every claim that matters, so the user can jump back.

## 7 · Clean up

Delete the frame directory when the brief is written (`rm -rf ./_work/frame_*.jpg`). Keep
`audio.srt` — it is the cheap, greppable source of truth. Keep the video only if the user wants it.

## Notes

- Download only recordings the user is entitled to (enrolled, invited, employed). Do not
  redistribute them.
- `--cookies-from-browser` may hit the OS keyring on Linux (gnome-keyring/kwallet) — the prompt is
  expected, not a failure.
- Long sessions: `--fps 1/30` is plenty for a slide-driven lecture; keep `auto` for demos.
