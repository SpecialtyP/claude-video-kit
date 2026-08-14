#!/usr/bin/env python3
"""
vk — claude-video-kit CLI.

One cross-platform entry point (Linux / macOS / Windows) for the video-processing
primitives the Claude skills in this repo depend on: probe, frame extraction,
audio extraction, transcription, and the combined `prepare` pipeline.

Stdlib only. Every heavy dependency (whisper engines) is resolved at call time
and degrades through a documented cascade instead of hard-failing.

Usage:
    vk doctor [--json]
    vk probe      <media>
    vk frames     <video> [-o DIR] [--fps auto|1/3|2] [--scale 0.5]
    vk audio      <video> [-o out.wav] [--rate 16000]
    vk transcribe <media> [-o DIR] [--model base] [--language es]
                          [--format srt|txt|json] [--engine auto|whisper|faster|hyperframes]
    vk prepare    <video> [workdir] [--model base] [--language en] [--fps auto]

Env:
    VK_WHISPER_BIN     explicit path to an openai-whisper CLI
    VK_WHISPER_MODEL   default model (default: base)
    VK_WHISPER_ENGINE  default engine (default: auto)
    VK_WHISPER_DEVICE  cpu | cuda | auto   (default: cpu — dodges GPU OOM on shared hosts)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

IS_WIN = os.name == "nt"
DEFAULT_MODEL = os.environ.get("VK_WHISPER_MODEL", "base")
DEFAULT_ENGINE = os.environ.get("VK_WHISPER_ENGINE", "auto")
DEFAULT_DEVICE = os.environ.get("VK_WHISPER_DEVICE", "cpu")


# ── shell helpers ──────────────────────────────────────────────────────────


def which(name: str) -> str | None:
    """shutil.which + the usual non-PATH install locations."""
    found = shutil.which(name)
    if found:
        return found
    candidates = [
        Path.home() / ".local" / "bin" / name,
        Path.home() / ".local" / "bin" / f"{name}.exe",
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
    ]
    if IS_WIN:
        candidates += [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / name / f"{name}.exe",
        ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def die(msg: str, code: int = 1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def need(bin_name: str) -> str:
    p = which(bin_name)
    if not p:
        die(f"missing dependency: {bin_name} — run `vk doctor` for install hints")
    return p


def npx() -> list[str] | None:
    """npx invocation, shell-wrapped on Windows where npx is a .cmd."""
    p = which("npx") or which("npx.cmd")
    if not p:
        return None
    return [p]


# ── probe ──────────────────────────────────────────────────────────────────


def probe(media: Path) -> dict:
    ffprobe = need("ffprobe")
    cp = run([
        ffprobe, "-v", "error",
        "-show_entries", "format=duration,size,format_name"
        ":stream=index,codec_type,codec_name,width,height,duration,r_frame_rate",
        "-of", "json", str(media),
    ])
    if cp.returncode != 0:
        die(f"ffprobe failed: {cp.stderr.strip()}", 3)
    data = json.loads(cp.stdout or "{}")
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    def dur_of(kind: str) -> float:
        for s in streams:
            if s.get("codec_type") == kind:
                try:
                    return float(s.get("duration") or 0)
                except ValueError:
                    return 0.0
        return 0.0

    video_dur = dur_of("video")
    audio_dur = dur_of("audio")
    total = float(fmt.get("duration") or 0) or max(video_dur, audio_dur)
    vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
    return {
        "path": str(media),
        "duration": total,
        "video_duration": video_dur or total,
        "audio_duration": audio_dur,
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        "width": vstream.get("width"),
        "height": vstream.get("height"),
        "vcodec": vstream.get("codec_name"),
        # WhatsApp / screen recorders sometimes clip audio before the video ends
        "audio_clipped": bool(audio_dur and video_dur and audio_dur + 5 < video_dur),
        "size": int(fmt.get("size") or 0),
    }


# ── frames ─────────────────────────────────────────────────────────────────


def auto_fps(duration: float) -> str:
    if duration <= 180:
        return "1/3"
    if duration <= 600:
        return "1/5"
    return "1/10"


def extract_frames(video: Path, out_dir: Path, fps: str = "auto", scale: float = 0.5) -> int:
    ffmpeg = need("ffmpeg")
    out_dir.mkdir(parents=True, exist_ok=True)
    if fps == "auto":
        fps = auto_fps(probe(video)["video_duration"])
    vf = f"fps={fps}"
    if scale and scale != 1:
        vf += f",scale=iw*{scale}:ih*{scale}"
    cp = run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
        "-vf", vf, "-q:v", "3", str(out_dir / "frame_%03d.jpg"),
    ])
    if cp.returncode != 0:
        die(f"frame extraction failed: {cp.stderr.strip()}", 3)
    return len(list(out_dir.glob("frame_*.jpg")))


# ── audio ──────────────────────────────────────────────────────────────────


def extract_audio(video: Path, out: Path, rate: int = 16000) -> Path:
    ffmpeg = need("ffmpeg")
    out.parent.mkdir(parents=True, exist_ok=True)
    cp = run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
        "-vn", "-acodec", "pcm_s16le", "-ar", str(rate), "-ac", "1", str(out),
    ])
    if cp.returncode != 0:
        die(f"audio extraction failed: {cp.stderr.strip()}", 3)
    return out


# ── transcription ──────────────────────────────────────────────────────────


def srt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments: list[dict], dest: Path) -> Path:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines += [
            str(i),
            f"{srt_ts(seg['start'])} --> {srt_ts(seg['end'])}",
            seg["text"].strip(),
            "",
        ]
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def available_engines() -> list[str]:
    engines = []
    if which(os.environ.get("VK_WHISPER_BIN") or "whisper"):
        engines.append("whisper")
    try:
        import faster_whisper  # noqa: F401
        engines.append("faster")
    except Exception:
        pass
    if npx():
        engines.append("hyperframes")
    return engines


def _engine_whisper(media: Path, out_dir: Path, model: str, language: str | None,
                    fmt: str) -> Path:
    """openai-whisper CLI (same contract as the Linux box: CPU, explicit model)."""
    binary = os.environ.get("VK_WHISPER_BIN") or which("whisper")
    if not binary:
        raise RuntimeError("openai-whisper CLI not found")
    cmd = [binary, str(media), "--model", model, "--output_format", fmt,
           "--output_dir", str(out_dir), "--device", DEFAULT_DEVICE]
    if language:
        cmd += ["--language", language]
    env = dict(os.environ)
    if DEFAULT_DEVICE == "cpu":
        env["CUDA_VISIBLE_DEVICES"] = ""
    cp = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if cp.returncode != 0:
        raise RuntimeError(f"whisper failed: {(cp.stderr or cp.stdout)[-400:]}")
    dest = out_dir / f"{media.stem}.{fmt}"
    if not dest.exists():
        raise RuntimeError(f"whisper produced no {dest.name}")
    return dest


def _engine_faster(media: Path, out_dir: Path, model: str, language: str | None,
                   fmt: str) -> Path:
    """faster-whisper (CTranslate2) — no torch, the light default for Mac/Windows."""
    from faster_whisper import WhisperModel  # lazy: only when this engine is picked

    device = "cpu" if DEFAULT_DEVICE == "cpu" else DEFAULT_DEVICE
    compute = "int8" if device == "cpu" else "float16"
    wm = WhisperModel(model, device=device, compute_type=compute)
    seg_iter, info = wm.transcribe(str(media), language=language, vad_filter=True)
    segments = [{"start": s.start, "end": s.end, "text": s.text} for s in seg_iter]
    dest = out_dir / f"{media.stem}.{fmt}"
    out_dir.mkdir(parents=True, exist_ok=True)
    if fmt == "srt":
        write_srt(segments, dest)
    elif fmt == "txt":
        dest.write_text("\n".join(s["text"].strip() for s in segments), encoding="utf-8")
    else:
        dest.write_text(json.dumps({
            "language": getattr(info, "language", language),
            "segments": segments,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def _engine_hyperframes(media: Path, out_dir: Path, model: str, language: str | None,
                        fmt: str) -> Path:
    """`npx hyperframes transcribe` — bundles whisper.cpp, zero local install.

    Emits word-level JSON; converted to SRT here when SRT was requested.
    """
    base = npx()
    if not base:
        raise RuntimeError("npx not found (Node.js >= 22 required)")
    out_dir.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in out_dir.iterdir()}
    cmd = base + ["-y", "hyperframes@latest", "transcribe", str(media),
                  "-d", str(out_dir), "--json", "--model", model]
    if language:
        cmd += ["--language", language]
    cp = subprocess.run(cmd, capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError(f"hyperframes transcribe failed: {(cp.stderr or cp.stdout)[-400:]}")
    new = [p for p in out_dir.iterdir() if p.name not in before and p.suffix in (".json", ".srt")]
    if not new:
        raise RuntimeError("hyperframes transcribe produced no output file")
    produced = sorted(new, key=lambda p: p.stat().st_mtime)[-1]
    if fmt == "json" or produced.suffix == f".{fmt}":
        return produced
    words = json.loads(produced.read_text(encoding="utf-8"))
    if isinstance(words, dict):
        words = words.get("words") or words.get("segments") or []
    segments, cur = [], None
    for w in words:  # group words into ~8-word cues
        if cur is None or len(cur["words"]) >= 8:
            cur = {"start": w["start"], "end": w["end"], "words": []}
            segments.append(cur)
        cur["words"].append(w.get("text") or w.get("word", ""))
        cur["end"] = w["end"]
    segs = [{"start": s["start"], "end": s["end"], "text": " ".join(s["words"])} for s in segments]
    dest = out_dir / f"{media.stem}.{fmt}"
    if fmt == "srt":
        return write_srt(segs, dest)
    dest.write_text("\n".join(s["text"] for s in segs), encoding="utf-8")
    return dest


ENGINES = {
    "whisper": _engine_whisper,
    "faster": _engine_faster,
    "hyperframes": _engine_hyperframes,
}
CASCADE = ["whisper", "faster", "hyperframes"]


def transcribe(media: Path, out_dir: Path, model: str = DEFAULT_MODEL,
               language: str | None = None, fmt: str = "srt",
               engine: str = DEFAULT_ENGINE) -> tuple[Path, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    order = CASCADE if engine == "auto" else [engine]
    errors = []
    for name in order:
        fn = ENGINES.get(name)
        if not fn:
            die(f"unknown engine: {name} (pick one of {', '.join(ENGINES)})")
        try:
            print(f"[vk] transcribe · engine={name} model={model}"
                  f"{' lang=' + language if language else ''}", file=sys.stderr)
            return fn(media, out_dir, model, language, fmt), name
        except Exception as exc:  # try the next engine in the cascade
            errors.append(f"  {name}: {exc}")
            if engine != "auto":
                die(f"engine '{name}' failed:\n{errors[-1]}", 3)
    die("no transcription engine worked:\n" + "\n".join(errors) +
        "\n\nInstall one:  pip install faster-whisper   |   pip install openai-whisper"
        "\n              (or install Node >= 22 so `npx hyperframes transcribe` can run)", 1)


# ── prepare (probe → frames → audio → transcript) ──────────────────────────


def prepare(video: Path, work: Path, model: str, language: str | None,
            fps: str, engine: str) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    print("[vk] triage", file=sys.stderr)
    info = probe(video)
    (work / "probe.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    use_fps = auto_fps(info["video_duration"]) if fps == "auto" else fps
    print(f"[vk] extract frames at fps={use_fps}", file=sys.stderr)
    n_frames = extract_frames(video, work, fps=use_fps)

    transcript = None
    engine_used = None
    if info["has_audio"]:
        print("[vk] extract audio (16kHz mono wav)", file=sys.stderr)
        wav = extract_audio(video, work / "audio.wav")
        transcript, engine_used = transcribe(wav, work, model=model, language=language,
                                             fmt="srt", engine=engine)
    else:
        print("[vk] no audio stream — frames only", file=sys.stderr)

    srt_lines = 0
    if transcript and transcript.exists():
        srt_lines = len(transcript.read_text(encoding="utf-8", errors="replace").splitlines())

    report = {
        "video": str(video),
        "work_dir": str(work),
        "video_duration": round(info["video_duration"], 1),
        "audio_duration": round(info["audio_duration"], 1),
        "audio_clipped": info["audio_clipped"],
        "frames": n_frames,
        "fps": use_fps,
        "transcript": str(transcript) if transcript else None,
        "transcript_lines": srt_lines,
        "engine": engine_used,
    }
    (work / "prepare.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    clip_note = "  ⚠ audio clipped — lean on frames for the tail" if info["audio_clipped"] else ""
    print(f"""
────────────────────────────────────────────────────────────
vk prepare — complete
────────────────────────────────────────────────────────────
video:          {report['video']}
video duration: {report['video_duration']}s
audio duration: {report['audio_duration']}s{clip_note}
work dir:       {report['work_dir']}
frames:         {report['frames']} jpg  (fps={report['fps']})
transcript:     {report['transcript'] or '— (no audio)'}  ({report['transcript_lines']} lines)
engine:         {report['engine'] or '—'}
────────────────────────────────────────────────────────────
next → walk the frames, then correlate to code
""")
    return report


# ── doctor ─────────────────────────────────────────────────────────────────

HINTS = {
    "ffmpeg": {"mac": "brew install ffmpeg", "linux": "apt/dnf/pacman install ffmpeg",
               "win": "winget install Gyan.FFmpeg"},
    "ffprobe": {"mac": "brew install ffmpeg", "linux": "ships with ffmpeg",
                "win": "winget install Gyan.FFmpeg"},
    "node": {"mac": "brew install node", "linux": "distro pkg or nvm",
             "win": "winget install OpenJS.NodeJS.LTS"},
    "yt-dlp": {"mac": "brew install yt-dlp", "linux": "pipx install yt-dlp",
               "win": "winget install yt-dlp.yt-dlp"},
}


def platform_key() -> str:
    if IS_WIN:
        return "win"
    return "mac" if sys.platform == "darwin" else "linux"


def doctor(as_json: bool = False) -> int:
    plat = platform_key()
    checks = []

    def add(name, path, required, hint_key=None):
        checks.append({
            "name": name, "found": bool(path), "path": path or None,
            "required": required,
            "hint": HINTS.get(hint_key or name, {}).get(plat),
        })

    add("ffmpeg", which("ffmpeg"), True)
    add("ffprobe", which("ffprobe"), True)
    add("python3", sys.executable, True)
    add("node", which("node"), False)
    add("npx", which("npx"), False)
    add("yt-dlp", which("yt-dlp"), False)
    add("magick", which("magick") or which("convert"), False)

    engines = available_engines()
    checks.append({
        "name": "whisper engine", "found": bool(engines),
        "path": ", ".join(engines) or None, "required": True,
        "hint": "pip install faster-whisper   (light)   |   pip install openai-whisper   (torch)",
    })

    ok = all(c["found"] for c in checks if c["required"])
    if as_json:
        print(json.dumps({"ok": ok, "platform": plat, "checks": checks}, indent=2))
        return 0 if ok else 1

    print(f"claude-video-kit · doctor · {plat}\n")
    for c in checks:
        mark = "✓" if c["found"] else ("✗" if c["required"] else "·")
        detail = c["path"] or (c["hint"] or "not installed")
        tag = "" if c["required"] else " (optional)"
        print(f"  {mark} {c['name']:<16}{detail}{tag}")
    print(f"\n{'OK — ready to process video' if ok else 'MISSING required dependencies (see ✗ above)'}")
    return 0 if ok else 1


# ── cli ────────────────────────────────────────────────────────────────────


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="vk", description="claude-video-kit CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("probe"); p.add_argument("media")

    p = sub.add_parser("frames")
    p.add_argument("video"); p.add_argument("-o", "--out", default=None)
    p.add_argument("--fps", default="auto"); p.add_argument("--scale", type=float, default=0.5)

    p = sub.add_parser("audio")
    p.add_argument("video"); p.add_argument("-o", "--out", default=None)
    p.add_argument("--rate", type=int, default=16000)

    p = sub.add_parser("transcribe")
    p.add_argument("media"); p.add_argument("-o", "--out", default=None)
    p.add_argument("--model", default=DEFAULT_MODEL); p.add_argument("--language", default=None)
    p.add_argument("--format", default="srt", choices=["srt", "txt", "json"])
    p.add_argument("--engine", default=DEFAULT_ENGINE,
                   choices=["auto", "whisper", "faster", "hyperframes"])

    p = sub.add_parser("prepare")
    p.add_argument("video"); p.add_argument("workdir", nargs="?", default=None)
    p.add_argument("--model", default=DEFAULT_MODEL); p.add_argument("--language", default=None)
    p.add_argument("--fps", default="auto")
    p.add_argument("--engine", default=DEFAULT_ENGINE,
                   choices=["auto", "whisper", "faster", "hyperframes"])

    a = ap.parse_args(argv)

    if a.cmd == "doctor":
        return doctor(a.json)

    media = Path(a.media if a.cmd in ("probe", "transcribe") else a.video).expanduser()
    if not media.is_file():
        die(f"file not found: {media}", 2)

    if a.cmd == "probe":
        print(json.dumps(probe(media), indent=2))
    elif a.cmd == "frames":
        out = Path(a.out).expanduser() if a.out else media.parent / f"{media.stem}_frames"
        print(f"{extract_frames(media, out, a.fps, a.scale)} frames → {out}")
    elif a.cmd == "audio":
        out = Path(a.out).expanduser() if a.out else media.with_suffix(".wav")
        print(extract_audio(media, out, a.rate))
    elif a.cmd == "transcribe":
        out = Path(a.out).expanduser() if a.out else media.parent
        dest, eng = transcribe(media, out, a.model, a.language, a.format, a.engine)
        print(f"{dest}  (engine: {eng})")
    elif a.cmd == "prepare":
        work = Path(a.workdir).expanduser() if a.workdir else \
            Path(os.environ.get("TMPDIR") or ("C:/Temp" if IS_WIN else "/tmp")) / \
            f"video-analysis-{int(time.time())}"
        prepare(media, work, a.model, a.language, a.fps, a.engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())
