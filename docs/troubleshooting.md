# Troubleshooting

Always start with `vk doctor` (`vk doctor --json` in scripts — gate on `.ok`).

## `vk: command not found`

The launcher is at `~/.local/bin/vk` (macOS/Linux) or `%USERPROFILE%\.claude\bin\vk.cmd` (Windows)
and that folder may not be on PATH.

```bash
# bash / zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.profile && exec $SHELL
# fish
fish_add_path ~/.local/bin
```

Windows: the installer offers to add it to the user PATH — the change only affects **new** terminals.
Fallback that always works: `python3 "$CLAUDE_VIDEO_KIT/bin/vk.py" …`.

## Claude does not see the skills

1. Skills live in `~/.claude/skills/<name>/SKILL.md`. Check the link resolved:
   `ls -l ~/.claude/skills | grep video` (Windows: `dir /AL %USERPROFILE%\.claude\skills`).
2. Restart Claude Code — skills are read at startup.
3. A skill is only *offered* when the request matches its description. Ask for it by name to force
   it: "usa la skill recording-brief con este archivo".

## `no transcription engine worked`

Install one into the kit venv (not the system Python):

```bash
"$CLAUDE_VIDEO_KIT/.venv/bin/python" -m pip install faster-whisper       # light
"$CLAUDE_VIDEO_KIT/.venv/bin/python" -m pip install openai-whisper       # heavy, PyTorch
```

Or re-run the installer with `--engine faster` / `-Engine faster`. With Node ≥ 22 present, `vk`
also falls back to `npx hyperframes transcribe` with no Python dependency at all.

## `pip install` fails with *externally-managed-environment* (PEP 668)

Do not fight it and do not use `--break-system-packages`. The kit's venv exists precisely for this:
install into `<kit>/.venv`, which the `vk` launcher prefers automatically.

## Transcription is slow / hangs on first run

The first call for a given model downloads it (75 MB `tiny` → 3.1 GB `large-v3`), then caches it
(`~/.cache/whisper`, `~/.cache/huggingface`, or `~/.cache/hyperframes`). It is a download, not a
hang. Use `--model tiny` to smoke-test the pipeline before committing to a big model.

## GPU / CUDA out of memory

`vk` forces CPU by default (`VK_WHISPER_DEVICE=cpu`, `CUDA_VISIBLE_DEVICES=""`). To opt into GPU:
`VK_WHISPER_DEVICE=cuda vk transcribe …`.

## The transcript came back in English but the audio was Spanish

You used an `.en` model. They translate. Use a plain model plus `--language es`.

## `ffmpeg: command not found` on Windows after winget install

winget puts it on PATH for new shells only. Close and reopen the terminal (and Claude Code).

## `--cookies-from-browser` fails

- The browser must be the one where the session is open, and it must be logged in.
- Linux may prompt for the keyring (gnome-keyring / kwallet) — expected.
- Chrome ≥ 127 locks its cookie DB while running; close the browser or use `--cookies cookies.txt`
  exported by an extension.

## blueprint MCP shows as disconnected

```bash
claude mcp list                                       # status
npx -y @railsblueprint/blueprint-mcp@latest           # run by hand, read the actual error
```

Needs Node on PATH. On Windows inside Claude Desktop, wrap it: `cmd /c npx -y @railsblueprint/blueprint-mcp@latest`.

## Shell snippets in the skills fail on Windows

The skills document POSIX one-liners. `vk` itself is native on Windows; for the surrounding
`grep`/`ps` snippets use Git Bash, WSL, or the PowerShell equivalent noted in the skill.

## Frames are enormous / too many

`--fps` and `--scale` are yours: `vk frames long.mp4 --fps 1/30 --scale 0.4`. For a one-shot visual
scan of a long recording, the contact-sheet recipe in `video-toolkit` beats hundreds of JPEGs.
