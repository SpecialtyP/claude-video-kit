# claude-video-kit

Portable video-processing setup for **Claude Code / Claude Desktop** — the skills, the CLI and the
MCP wiring needed to take an existing recording and turn it into frames, a transcript and a
report. One `git clone` + one installer brings a Linux, macOS or Windows machine to parity.

> Scope: **processing video that already exists** (screen recordings, meetings, lectures, clips).
> *Authoring* new motion graphics is HyperFrames' job — see [Authoring](#authoring-hyperframes).

---

## What you get

### Skills (installed into `~/.claude/skills/`)

| Skill | Does |
|---|---|
| **video-toolkit** | The base contract: `vk` verbs, Whisper engines + model/language rules, yt-dlp downloads, the ffmpeg recipes worth not re-deriving. Every other skill leans on this. |
| **video-bug-scan** | Screen recording of a bug → frames + transcript → root-caused, dated bug report → batched fix. |
| **recording-brief** | Session recording (Zoom/Meet/Loom/local) → download via browser cookies → frames + transcript → study/meeting brief. |
| **pwa-walkthrough-test** | The other direction: drive a PWA/SPA with Playwright, record it, validate against bug fingerprints, concat to a single MP4. |

### `vk` — one CLI, three operating systems

```bash
vk doctor                    # dependency check + per-OS install hints
vk probe      clip.mp4       # duration, codecs, resolution, has_audio, audio_clipped
vk frames     clip.mp4 -o ./frames --fps auto
vk audio      clip.mp4 -o audio.wav          # 16 kHz mono
vk transcribe audio.wav --model small --language es --format srt
vk prepare    clip.mp4 [workdir]             # all of the above, one call
```

`vk` is stdlib-only Python around ffmpeg/ffprobe plus a **Whisper engine cascade** — it uses
whichever of these is installed, so the same command works everywhere:

| Engine | Weight | Install |
|---|---|---|
| `faster` — faster-whisper / CTranslate2 | ~200 MB, no PyTorch | `pip install faster-whisper` *(installer default)* |
| `whisper` — openai-whisper CLI | ~2.5 GB with torch | `pip install openai-whisper` |
| `hyperframes` — `npx hyperframes transcribe` (whisper.cpp) | nothing local | Node ≥ 22 |

### MCP

**blueprint** (browser automation over your real browser profile) is registered by the installer.
Definitions and Claude Desktop config: [`mcp/README.md`](mcp/README.md).

---

## Install

### macOS / Linux

```bash
git clone git@github.com:SpecialtyP/claude-video-kit.git ~/claude-video-kit
cd ~/claude-video-kit
bash install/install.sh
```

### Windows (PowerShell)

```powershell
git clone git@github.com:SpecialtyP/claude-video-kit.git $HOME\claude-video-kit
cd $HOME\claude-video-kit
powershell -ExecutionPolicy Bypass -File install\install.ps1
```

Then restart Claude Code and ask it to `vk doctor`.

### What the installer does

1. Installs `ffmpeg`, `python3`, `node`, `yt-dlp` (brew / apt / dnf / pacman / zypper / apk / winget).
2. Creates a private venv at `<kit>/.venv` with the chosen Whisper engine — no system Python
   pollution, no PEP 668 fights.
3. Installs the `vk` launcher (`~/.local/bin/vk`, or `~/.claude/bin/vk.cmd` on Windows).
4. Links the skills into `~/.claude/skills/` (symlink / directory junction, so `git pull` updates
   them; `--copy` / `-Copy` to copy instead) and writes `~/.claude/video-kit.json` so the skills can
   find the kit from anywhere.
5. Registers the **blueprint** MCP server.
6. Optionally installs the HyperFrames authoring pack from upstream.

Flags — `install.sh`: `--engine faster|openai|none` · `--copy` · `--with-hyperframes` ·
`--no-mcp` · `--no-deps` · `-y`.
`install.ps1`: `-Engine` · `-Copy` · `-WithHyperframes` · `-NoMcp` · `-NoDeps` · `-Yes`.

Re-running is safe and is the supported upgrade path:

```bash
cd ~/claude-video-kit && git pull && bash install/install.sh -y
```

---

## Use it

Ask Claude Code, in plain language:

- *"Analiza este video y arregla los bugs: ~/Downloads/demo.mp4"* → `video-bug-scan`
- *"Descarga esta grabación de Zoom y hazme un brief"* → `recording-brief`
- *"Graba un walkthrough de la app y mándamelo en MP4"* → `pwa-walkthrough-test`
- *"Transcribe este audio en español"* → `video-toolkit`

Or drive the CLI directly:

```bash
vk prepare ~/Downloads/demo.mp4 --model small --language es
```

**Language rule:** `.en` models (`base.en`, `small.en`, …) *translate* non-English audio into
English and silently lose the original. Spanish audio → plain model + `--language es`.

---

## Authoring (HyperFrames)

Making new video — motion graphics, explainers, captioned recuts, product promos — is a separate,
much larger skill pack maintained upstream by [HyperFrames](https://www.npmjs.com/package/hyperframes).
It is deliberately **not vendored here**: it ships its own installer, updates on its own cadence,
and some of its assets are third-party licensed.

```bash
npx hyperframes skills     # installs hyperframes-core/-creative/-animation/-cli/-registry/-media,
                           # plus embedded-captions, talking-head-recut and the video orchestrators
npx hyperframes doctor
```

`install.sh --with-hyperframes` / `install.ps1 -WithHyperframes` just calls that for you.
Its `hyperframes transcribe` (bundled whisper.cpp) also serves as `vk`'s third fallback engine.

---

## Troubleshooting

See [`docs/troubleshooting.md`](docs/troubleshooting.md). Start with `vk doctor`.

## Licence

MIT — see [`LICENSE`](LICENSE). Third-party attributions in [`NOTICE.md`](NOTICE.md).
