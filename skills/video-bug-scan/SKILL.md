---
name: video-bug-scan
description: Analyze a screen-recording video (WhatsApp/MP4/MOV) — extract frames, transcribe narration, correlate to the running codebase, write a dated bug-report .md, then fix the issues in one batch. Use when the user sends a video path and asks to "process/analyze/fix the bugs in the video" or references a specific recording for bug reporting.
argument-hint: <path-to-video.mp4> [tenant-name]
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, TaskCreate, TaskUpdate, mcp__claude_ai_Supabase__execute_sql, mcp__claude_ai_Supabase__apply_migration, mcp__claude_ai_Supabase__get_logs, mcp__claude_ai_Supabase__deploy_edge_function
---

# Video bug scan

Walk from a raw screen recording to a merged-and-deployed fix. The skill assumes:

- The video is a real user (dev/tester/customer) demonstrating an app and narrating bugs they hit.
- The working directory is the repo that serves the app in the video. If it isn't, **ask** before doing any writes.
- `claude-video-kit` is installed (ffmpeg + ffprobe + one Whisper engine). Verify with `vk doctor`;
  it works the same on Linux, macOS and Windows.

## Workflow

Run these phases in order. Each phase produces an artifact used by the next, so don't skip.

### 1-3 · Automated prep (one shell call)

The repetitive setup (ffprobe triage → ffmpeg frame/audio extract → Whisper transcription) is one
command from `claude-video-kit`. Call it instead of running each step by hand:

```bash
vk prepare "$VIDEO"                       # any OS, if `vk` is on PATH
python3 "$CLAUDE_VIDEO_KIT/bin/vk.py" prepare "$VIDEO"   # fallback, no PATH shim
bash ~/.claude/skills/video-bug-scan/prepare.sh "$VIDEO" # legacy wrapper (Linux/macOS)
```

On Windows use `vk prepare "%VIDEO%"` or `prepare.cmd "%VIDEO%"` — never the `.sh`.

- Writes everything to `<temp>/video-analysis-<epoch>/` (override with a 2nd positional arg).
- Picks `fps=1/3` for videos ≤3 min, `1/5` up to 10 min, `1/10` beyond, to keep frame counts sane.
- Flags the WhatsApp-audio-clip case (audio shorter than video) so you know to lean on frames for the tail.
- Runs Whisper on CPU (`CUDA_VISIBLE_DEVICES=""`) to dodge GPU-OOM on shared hosts.
- Skips transcription cleanly when the recording has no audio stream.
- Prints a compact summary and writes `prepare.json` + `probe.json` next to the frames.

Override the model / language for heavy accents or non-English narration:

```bash
vk prepare "$VIDEO" --model small --language es
```

**Language rule:** `.en` models silently *translate* non-English audio into English. For Spanish
narration pass a plain model plus `--language es` — never `base.en`.

When the script finishes, read `audio.srt` once. Quote the narrator's lines verbatim in the bug report — "the user said" beats "the user probably meant." If the script flagged audio-shorter-than-video, note that in the bug report's Source block and treat the silent tail as frame-only evidence.

### 4 · Walk the frames

Read `$WORK/frame_XXX.jpg` in spaced jumps (every other frame is usually enough). For each UI state, note:

- The screen label (Home, Create Job, Photo Editor, …)
- Any toast/error text visible (this is gold — drop it straight into the bug report)
- Specific interactions the narrator described ("I tap Done", "autocomplete doesn't trigger")

Correlate each error message to a grep across the repo:

```
Grep pattern="<exact error text>" path="src"
```

That locates the failing call site faster than reasoning about architecture.

### 5 · Root-cause each bug in code

For every symptom, read the file + function that renders or issues the call that fails. Resist the urge to guess — open the file, follow the data flow, and cite `file:line` in the bug report.

When the failure is server-side (edge function, RPC), pull live logs:

```
mcp__claude_ai_Supabase__get_logs(project_id="<ref>", service="edge-function")
```

Recent 401/500 responses against the suspect function usually point straight at the cause.

### 6 · Write the bug-report .md

Create `docs/bug-reports/YYYY-MM-DD-<tenant>-<short-tag>.md` with:

- Source block (video filename, duration, transcript path, frames path).
- A status table (#, Area, Severity, Status).
- One H2 section per bug: **Where / What / User quote / Root cause / Files / Fix approach**.
- A final "Execution batch" checklist flagging which items ship in this PR vs. deferred (ops / PM / other repo).

Use the real user's Spanish/English quotes verbatim — they're the single best tiebreaker when the fix could go two ways.

### 6.5 · Validate every proposed fix before writing code

Before touching a single file, walk back through the **Fix approach** section of every bug in the report and answer three questions for each. **Skip this phase and you will ship duplicate work, regress unrelated screens, or break callers you never opened.**

#### a. Is the fix already done — fully or partially?

The bug list comes from a user's lived experience, but the codebase has been moving in parallel. Before re-implementing anything:

```bash
# Look for recent activity on the file/function you're about to edit.
git log --oneline -20 -- <file>
git log --oneline --all --since="60 days ago" --grep="<keyword from bug>"

# Search for the symptom or proposed solution by keyword.
Grep pattern='<feature name|toast text|function name>' path=src

# Check open PRs touching the same surface.
gh pr list --state open --search "<keyword>"
gh pr list --state merged --search "<keyword>" --limit 10
```

Decide which bucket the bug falls in:

- **Already fixed** — drop it from the execution batch, change the report status to "Already fixed in <commit>" and link the commit/PR. Do not re-fix.
- **Partial** — the scaffolding exists (helper hook, modal component, edge function) but isn't wired to the screen the user hit. Reuse what's there; do not introduce a parallel implementation. Note in the report which existing piece you're extending.
- **Not started** — proceed.

A common failure mode: the team built `useFooContact` last sprint, the user's bug is "tap doesn't open contact card," and you write `useFooContactV2` because you didn't look. Always look first.

#### b. Does the fix touch a schema, contract, or shared API?

Map every fix to its blast radius:

```bash
# Schema: which tables/columns does the fix read or write?
mcp__claude_ai_Supabase__list_tables(schemas=["public"])

# Endpoint/RPC: who else calls this edge function or supabase.from(...).select?
Grep pattern='functions.invoke\(.{0,3}<fn-name>' path=src
Grep pattern="from\(.<table>." path=src

# Component/hook: who imports the thing you're about to change?
Grep pattern="from ['\"]@/.*<module>['\"]" path=src
```

Trip-wires that mean **stop and reconsider**:

- The fix changes a **column type** or **adds a NOT NULL** column → backfill + multi-deploy, not in scope for a one-shot bug batch. Document as deferred.
- The fix renames or removes a **public field** in a Supabase row used by the mobile app, the admin panel, or an edge function → other surfaces will silently break. Either keep the old field as an alias or fan the change out to every consumer in the same PR.
- The fix changes an **edge-function payload shape** (`body.foo` → `body.bar`) → grep every caller; both web and native may be in flight. Bump a version param if you can't update them all atomically.
- The fix changes **RLS policies** or `verify_jwt` → pair with an attack-surface note in the bug report. Never silently relax auth to make a symptom go away.
- The fix touches **a hook used by both `src/admin/`/`src/mobile/`/`terminal/`** → run the import grep and add the screens you didn't visit to the testing checklist.

If a fix has a schema or cross-surface trip-wire, downgrade it to **deferred** in the execution batch and explain the migration path. A surgical fix is better than a fast one that takes down a sibling screen.

#### c. Does the fix actually solve the reported symptom — or just paper over it?

For each fix, write one sentence: *"After this change, the next time the user does X, they will see Y instead of Z."* If you can't predict Y precisely, the fix is too vague — read more code first.

Prefer **surface the real error** over **guess a fix** when the root cause is uncertain. A toast that prints the actual exception is more valuable than a retry loop that hides a 500.

#### Output of this phase

Update the bug-report .md in place:

- Each section's **Fix approach** gets a short trailing **Validation:** line — what you grepped, what other consumers exist, and whether the fix is safe to ship as-is or needs a wider sweep.
- Any bug whose validation failed (already fixed, schema risk, contract change) moves out of the **Execution batch** checklist with a one-line reason.

Only after the report's batch list reflects what's actually safe to ship do you move on to phase 7.

### 7 · Batch-fix, typecheck, commit, push

Make all the code edits the plan committed to. For each file: prefer `Edit` over rewrites, preserve surrounding style, **don't** add CLAUDE-or-Claude co-author trailers to commits (global CLAUDE.md rule).

Before committing:

- Run `npx tsc --noEmit` on modified `src/` files (or the project's checked-in typecheck script). If the full build is slow, run targeted `tsc` on just the files you touched.
- Revert any tenant-regenerated artifacts that the prebuild script rewrites locally (manifest, apple-touch-icon, swapped config/*.json) so the commit is clean.

Commit message format:
```
fix(<area>): <symptom in plain English>

<why the bug happened, 2-3 sentences>
<what the fix does, file/line precise>
```

Then push to `main` (or the branch the user requested). Follow up with:
- Edge function deploys (`supabase functions deploy … --no-verify-jwt` if the original had it disabled).
- Secret rotations (`supabase secrets set …`).
- Vercel auto-deploy check (`vercel inspect <latest-prod> --logs` to confirm the new commit hash built successfully).

### 8 · Update the status table + handoff

Once commits land:

- Flip the .md status column from `Open`/`Partial` to `Fixed` / `Deployed` for each entry.
- Summarize back to the user with: what's live, what needs their manual step (ops, admin approval, PWA re-install), and any observability change (e.g. "next time it fails, the toast now shows the real error").

## Guardrails

- **Never** commit secrets (API keys, tokens) that appear in video frames or transcripts. Rotate any leaked key on the spot.
- **Don't** change `verify_jwt` on an edge function without pairing it with a note about the attack-surface trade-off.
- **Ask** before enabling destructive actions (RLS bypass, `ALTER TABLE … DROP`, force-push, etc.).
- When in doubt about a bug's root cause, prefer "surface the real error to the toast/log" over "guess a fix" — self-diagnosing telemetry pays for itself within one retry.
- **Never skip phase 6.5.** It's the difference between a clean batch fix and a regression. Validate that each proposed fix isn't already shipped, doesn't break callers you didn't open, and doesn't change a schema/contract under another surface's feet — then ship.
- PWA caching on iOS: remind the user that manifest/icon changes only take effect after they *Remove from Home Screen* → re-install.

## Handy commands

```bash
# Re-run just Whisper on an existing WAV (after model swap).
CUDA_VISIBLE_DEVICES="" whisper $WORK/audio.wav --model small --device cpu --output_dir $WORK

# Sample a single frame at T seconds, full-res, for a close-up.
ffmpeg -ss 42 -i "$VIDEO" -frames:v 1 "$WORK/closeup.jpg"

# Grep the repo for an exact toast message.
Grep pattern='Failed to generate report' path=src output_mode=files_with_matches

# Tail recent edge-function errors for a specific function.
# Then use the MCP get_logs tool with service=edge-function.
```

## Example prompt that triggers this skill

> "Process this video the same way: /home/user/Downloads/bug-report-2026-04-16.mp4"
>
> "Analyze /tmp/demo.mov and fix the bugs you find."
>
> "Here's a WhatsApp recording of the crash — extract the bugs and patch them in one batch."

In all cases, begin with Phase 1 (triage). Do not skip to coding.
