---
name: recording-brief
description: Turn any recorded session into a written brief — a class, lecture, webinar, course module, meeting, workshop or conference talk. Downloads the recording (Zoom, Meet, Teams, Loom, YouTube, Vimeo, an LMS player, or a local file), extracts frames and a transcript locally, and writes a study/meeting brief with timestamps. Handles login-gated recordings by reusing the browser's cookies. Use when the user asks to "download the recording", "summarize this class/meeting/webinar", "prepare for the exam with this video", "hazme un brief de esta clase", or hands over a link to a session recording.
allowed-tools: Bash, Read, Write, Glob, Grep
---

# recording-brief

Any recorded session → a brief you can study from or act on. Platform-agnostic and
subject-agnostic: the pipeline is always **get the file → two evidence streams (what was said,
what was shown) → structured brief**. Only step 1 changes per platform.

The trick that makes gated platforms work: **yt-dlp can reuse the cookies of a browser you are
already logged into** — no screen-recording of a playback, no JS injection.

Depends on `video-toolkit` (ffmpeg/ffprobe/Whisper via `vk`) and `yt-dlp`. Check with `vk doctor`.

---

## 1 · Get the recording

Ask which case applies before doing anything — it decides everything downstream.

| Case | Route |
|---|---|
| Local file already on disk | skip to §3 |
| Public link (YouTube, Vimeo, a public Loom) | `yt-dlp "$URL"` |
| Login-gated (Zoom, Teams, Loom private, an LMS player) | §2 — cookies |
| Platform offers a "Download" button | use it; a native download always beats scraping |
| Only streamed, no file (DRM, live-only) | say so and fall back to the platform's own transcript / captions |

Common gated URL shapes:

- Zoom · `https://<org>.zoom.us/rec/play/<ID>` or `/rec/share/<ID>`
- Teams / Stream · `https://<tenant>.sharepoint.com/.../stream.aspx?id=…`
- Google Meet · recordings land in Drive — download from Drive, not the Meet URL
- Panopto · `https://<host>/Panopto/Pages/Viewer.aspx?id=<GUID>`
- Kaltura / BigBlueButton / Echo360 · embedded in the LMS page; the player URL is what you want

**Finding the URL when it is in a browser tab:** ask the user for it, or pull it from a browser-MCP
snapshot (`blueprint`, `browsermcp`). Player-page snapshots are huge — never read one whole:

```bash
head -5 "$SNAPSHOT"                                        # → "Page URL: https://…"
grep -niE "video|transcript|download|descargar|\.mp4|\.m3u8" "$SNAPSHOT" | head
```

An LMS (Blackboard, Canvas, Moodle, Classroom, Teams) is usually just a **wrapper**: the item in
the course page links out to the real player (Zoom/Panopto/Kaltura/Drive). Follow that link and
treat it as the platform above, rather than fighting the LMS.

## 2 · Login-gated: borrow the browser session

Identify the browser where the session is actually open:

```bash
ps -eo comm | grep -iE 'chrome|chromium|brave|vivaldi|firefox|msedge' | sort | uniq -c   # Linux/macOS
```

Windows: `Get-Process | Where-Object { $_.Name -match 'chrome|msedge|firefox|brave' }`

Map to the yt-dlp flag — `chrome` | `chromium` | `brave` | `vivaldi` | `edge` | `firefox` — then
probe formats **before** downloading:

```bash
yt-dlp --cookies-from-browser chrome -F "$URL"      # expect an mp4 'view' format
yt-dlp --cookies-from-browser chrome -o "Recording <topic-or-date>.%(ext)s" "$URL"
```

A login/cookie error means the session is not open in *that* browser. Have the user log in and
retry — do not script around it. If Chrome locks its cookie DB (v127+), close it or use
`--cookies cookies.txt` exported by an extension.

## 3 · Analyze locally

```bash
vk prepare "Recording <topic>.mp4" ./_work --model small --language es
```

Non-English audio → plain model + `--language <iso>`; `.en` models translate and destroy the
original. Slide-driven talks can go sparse on frames (`--fps 1/30`); demos and whiteboard sessions
need `auto` or denser.

You now have two evidence streams, and you need both:

- **Transcript** (`audio.srt`) — what was *said*. Quote verbatim whenever the speaker marks
  something as load-bearing: "this is on the exam", "give the result with units", "we ship Friday",
  "this is the part people get wrong".
- **Frames** — what was *shown*. `Read` a spaced sample to recover diagrams, formulas,
  configuration dialogs, exact parameter values, result screens, code on screen. Numbers and
  notation live here; the audio almost never states them precisely.

If the platform already exposes a transcript or captions (Zoom, Panopto, YouTube, most LMS
players), use it as the text source and skip Whisper — faster and better punctuated. Grab it with
`yt-dlp --write-auto-subs --sub-langs "es,en" --skip-download "$URL"`, or from the page snapshot.
Still walk the frames.

## 4 · Write the brief

Write `BRIEF-<topic>.md` next to the recording. Adapt the sections to the material — an exam
review, a client meeting and a conference talk need different middles, same skeleton:

- **Header** — source, platform, file, duration, date, artifacts generated.
- **Stakes** — whatever the speaker said counts: exam weights and dates, deliverables, owners,
  deadlines, decisions taken.
- **Core content** — the substance, in tables where it is comparative (technique → when to use it,
  option → trade-off) and in prose where it is an argument.
- **Worked examples / demos** — step by step, with the exact parameters read off the frames.
- **✅ Verified on screen** — values, formulas and results confirmed from frames, marked as such
  and separated from what was only spoken.
- **Verbatim quotes** — the lines where the speaker flagged importance.
- **Open questions** — what the recording left ambiguous.
- **Checklist** — the actionable residue: what to study, what to do, who owes what.

Cite a timestamp (`[00:14:22]`) on every claim that matters, so the user can jump back and verify.
Never let the transcript override a frame: if what was said and what was shown disagree, report
both and flag the conflict.

## 5 · Clean up

Delete the frames when the brief is written (`rm -rf ./_work/frame_*.jpg`) — cheap to regenerate,
expensive to keep. Keep `audio.srt`: it is the greppable source of truth. Keep the video only if
the user wants it.

---

## Optional · Mirror the course/module structure on disk

When the user wants their local files organized the way the platform organizes them (any LMS —
Blackboard, Canvas, Moodle, Classroom, Udemy, Coursera):

1. Snapshot the course outline / curriculum page (browser MCP) and read the **module or week
   headings in order** — that hierarchy is the target structure.
2. Map every local file to the module whose section lists it. Match on title, not on filename
   guessing; ask when a match is ambiguous rather than moving blindly.
3. Create the folders (`01 - <module name>`, `02 - …`, or the platform's own numbering) and `mv`
   files in. Quote every path — module names carry spaces and accents.
4. Items the platform lists **outside** any module stay at the root.
5. Report both gaps explicitly: local files that appear nowhere in the platform, and platform
   items missing locally. Do not delete anything.

## Notes

- Download only recordings the user is entitled to — their own meetings, courses they are enrolled
  in, sessions they were invited to. Do not redistribute them.
- `--cookies-from-browser` may prompt the OS keyring on Linux (gnome-keyring / kwallet). Expected,
  not a failure.
- Multi-hour recordings: transcribe the extracted 16 kHz WAV (`vk` does this by default), and
  consider `--model small` over `medium` unless the audio is genuinely noisy — the accuracy gain
  rarely pays for the wall-clock on a long session.
- Series of recordings (a whole course, a weekly meeting): keep one brief per recording plus a
  rolling `INDEX.md` linking them, rather than one growing document.
