@echo off
REM video-bug-scan\prepare.cmd — Windows dispatcher onto `vk prepare`.
REM Usage:  prepare.cmd <video-path> [work-dir]
setlocal

set "KIT=%CLAUDE_VIDEO_KIT%"
if not defined KIT (
  for /f "usebackq delims=" %%p in (`python -c "import json,os;print(json.load(open(os.path.expanduser('~/.claude/video-kit.json'))).get('kitPath',''))" 2^>nul`) do set "KIT=%%p"
)
if not defined KIT set "KIT=%~dp0..\.."

if not exist "%KIT%\bin\vk.py" (
  echo error: claude-video-kit not found. Set CLAUDE_VIDEO_KIT to the repo root. 1>&2
  exit /b 1
)

set "EXTRA="
if defined VBS_WHISPER_MODEL set "EXTRA=--model %VBS_WHISPER_MODEL%"
if defined VBS_WHISPER_LANG set "EXTRA=%EXTRA% --language %VBS_WHISPER_LANG%"

if exist "%KIT%\.venv\Scripts\python.exe" (
  "%KIT%\.venv\Scripts\python.exe" "%KIT%\bin\vk.py" prepare %* %EXTRA%
) else (
  python "%KIT%\bin\vk.py" prepare %* %EXTRA%
)
exit /b %ERRORLEVEL%
