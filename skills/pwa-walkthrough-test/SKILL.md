---
name: pwa-walkthrough-test
description: Record a paced Playwright walkthrough of a PWA / React-SPA mobile app, validate it against bug fingerprints, concat to MP4, ship via email or Drive. Use this when the user wants to (1) reproduce screen-recordings of a tester's session, (2) verify bug fixes landed by replaying the broken flows, (3) demo a feature visually, or (4) regression-test a mobile flow end-to-end. Triggers when the user asks to "record the app", "show me the fix on video", "replay the test recordings", or "verify the bugs are fixed visually".
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, TaskCreate, TaskUpdate, TaskList, mcp__claude_ai_Supabase__execute_sql, mcp__claude_ai_Supabase__list_tables
---

# PWA walkthrough test

Take a list of intended user actions (or a set of source recordings the tester sent), run them in headless chromium against a local copy of the app, record video, and ship a single MP4. Bake in regression assertions so "did the fix land?" is verified, not guessed.

## Decision tree — when to invoke this

- **User sent screen recordings of a tester** → start with Phase 1 (frame walk) to extract an action log, then Phases 2-7.
- **User wants to verify a bug fix visually** → skip Phase 1; jump to Phase 2 with a hand-written action log focused on the broken flow + bug fingerprints.
- **User wants a feature demo / marketing video** → use Phases 2-6 only; skip the bug-fingerprint step.
- **User wants real-time tap fidelity (finger drags, gesture pacing)** → wrong tool; Playwright clicks by selector, no finger path.

## Prerequisites — verify in this order before authoring anything

```bash
which supabase && which docker && which bun && which ffmpeg && which python3
docker info >/dev/null 2>&1 && echo "docker UP" || echo "docker DOWN"
ls node_modules/@playwright/test/package.json >/dev/null 2>&1 || bun add -D @playwright/test
ls ~/.cache/ms-playwright/chromium-* >/dev/null 2>&1 || npx playwright install chromium
```

If Docker is down, the user has to start it (`sudo systemctl start docker` is sandbox-blocked from inside the agent).

## Phase 1 — frame walk (only if reproducing tester recordings)

The tester sent N screen-recordings. Goal: produce an `action_log.md` mapping every visible interaction to a numbered step the spec author can replay.

1. **Unzip + dedupe.** Sample sha256s — testers often duplicate recordings. Keep one of each.
2. **Probe + extract frames** at 1 fps (use `ffmpeg -vf "fps=1,scale=540:-1"`). 1206×2622 iPhone HEVC inputs scale to ~540 wide for fast read by sub-agents.
3. **Spawn 1 general-purpose Agent per video, in parallel.** Each agent reads every 2nd-3rd frame and emits an action log. The prompt template:
   ```
   Walk frames at /tmp/vbs/v{N}/ (frame_NNNN.jpg, 1fps from <duration>s).
   Read every 2nd-3rd frame. Output one line per action:
     [mm:ss] frame=N  action  →  observed result
   Capture EXACT visible text (button labels, form values, error toasts).
   Don't analyze for bugs — transcribe actions only.
   Report ~30-100 lines depending on video length.
   ```
4. **Merge logs** into one `action_log.md`. Add a "Replay map" section that maps each line to a Playwright primitive (tap / type / scroll / swipe / iOS-only-skip).

## Phase 2 — local app boot + auth verification

Most PWAs ship with a Supabase backend. The right mental model: don't run the spec against prod (writes leak), and don't re-implement seed data; spin up the project's `supabase start` stack which usually contains seed data.

```bash
supabase start                    # Docker images pulled first run (~2-5 min)
supabase status                   # capture API URL, publishable key, project ref
PGPASSWORD=postgres psql -h 127.0.0.1 -p 54322 -U postgres -d postgres \
  -c "SELECT count(*) FROM auth.users;"
# Find a usable seeded user (check for marco@local.dev, dev@local.dev, etc.)
```

Verify auth works at the REST level *before* writing the spec:

```bash
curl -s -X POST 'http://127.0.0.1:54321/auth/v1/token?grant_type=password' \
  -H 'Content-Type: application/json' -H "apikey: $LOCAL_ANON_KEY" \
  -d '{"email":"marco@local.dev","password":"localdev"}' | jq -r '.access_token // .error_description'
```

For the project ref derivation in localStorage keys: `sb-${baseUrl.hostname.split('.')[0]}-auth-token`. For `http://127.0.0.1:54321` that's **`sb-127-auth-token`** — different from prod. Always export `E2E_SUPABASE_REF=127` (or the right value) so the auth-token injection lands.

Build the app once; subsequent runs reuse `dist/`:

```bash
NODE_OPTIONS="--max-old-space-size=8192" bun run build
bun run preview -- --port 5208 --host 127.0.0.1 &   # background
until curl -sf http://127.0.0.1:5208/ -o /dev/null; do sleep 1; done
```

## Phase 3 — selector discovery (CRITICAL — don't skip)

The single biggest cause of broken walkthroughs is selectors that look right in code but don't match the rendered DOM. **Run a one-shot inspect spec before authoring** (template at `~/.claude/skills/pwa-walkthrough-test/templates/_inspect.spec.ts`):

```ts
test('inspect <screen> selectors', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/mobile/<route>`, { waitUntil: 'domcontentloaded' });
  await pause(page, 2500);
  // Dump button text + parent classes, plus svg icon classes (lucide-*)
  const info = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('button')).slice(0, 30).map((el: any) => ({
      text: (el.textContent || '').trim().slice(0, 40),
      svg: el.querySelector('svg')?.getAttribute('class')?.slice(0, 40),
      role: el.getAttribute('role'),
    }));
  });
  console.log(JSON.stringify(info, null, 2));
});
```

Run it for each screen the spec will visit. This is the difference between a 3-min walkthrough that hits everything and a 5-min recording stuck on one home grid.

**Selector pitfalls already burned through, encoded as guidance:**

| Failure mode | Fix |
|---|---|
| Multiple buttons with the same icon (`svg.lucide-plus`) → `.first()` lands on the wrong one | Anchor by neighboring text or aria-label, not just the icon class |
| Tile labels render in `<span>` children of `<button>` — `filter({ hasText: re })` works because `hasText` includes descendants | Confirmed pattern: `page.locator('a, button, [role="button"]').filter({ hasText: /^Label$/i })` |
| Modal opens but has no programmatic Close (e.g. `Select a Project` picker, iOS swipe-to-dismiss only) | Skip the entry tile entirely. Document it as iOS-only-reproducible. |
| Search input behind a focus trap rejects `type()` events (e.g. some `Start a Conversation` modals) | Skip that section; it WILL hang the test until timeout. |
| Tile not visible because home grid has multiple swipeable pages and the tile is on page 2/3 | Direct route nav: `page.goto('/mobile/<route>')`. Faster + more reliable than chromium swipe. |

## Phase 4 — author the specs (one per source recording or per flow)

**Six small specs > one big spec.** A monolithic spec hitting 14 minutes' worth of content always blows the timeout cap and leaves the recording frozen on whatever was on screen when chromium got killed. Six independent ~30-90s specs each end with `cleanFinish()` so no recording ends mid-modal.

Boilerplate at `~/.claude/skills/pwa-walkthrough-test/templates/_helpers.ts`:

```ts
export const TAP_TIMEOUT = 1500;
export const SETTLE = 700;
export const READ = 1500;

export async function login(page: Page) {
  // POST /auth/v1/token + localStorage.setItem(`sb-${REF}-auth-token`, …)
}

export async function tap(page: Page, label: string, settle = SETTLE) {
  const re = new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`, 'i');
  const target = page.locator('a, button, [role="button"]').filter({ hasText: re }).first();
  try {
    await target.waitFor({ state: 'visible', timeout: TAP_TIMEOUT });
    await target.click({ delay: 60 });
    await pause(page, settle);
    return true;
  } catch { return false; }       // never throw — let the spec keep moving
}

export async function back(page: Page, settle = SETTLE) {
  const arrow = page.locator(
    'button[aria-label*="back" i], button:has(svg.lucide-arrow-left), button:has(svg[class*="arrow-left" i])'
  ).first();
  if (await arrow.count().catch(() => 0)) {
    await arrow.click({ delay: 50 }).catch(() => {});
  } else {
    await page.goBack().catch(() => {});
  }
  await pause(page, settle);
}

/** ALWAYS the last thing in every spec — guarantees no frozen-modal endings. */
export async function cleanFinish(page: Page) {
  for (let i = 0; i < 3; i++) {
    await page.keyboard.press('Escape').catch(() => {});
    await pause(page, 250);
  }
  await page.goto(`${BASE_URL}/mobile/home`, { waitUntil: 'domcontentloaded' });
  await pause(page, 1500);
}
```

Each spec uses:

```ts
test.use({
  viewport: { width: 393, height: 852 },          // iPhone 16 logical
  isMobile: true, hasTouch: true,
  permissions: ['microphone', 'geolocation'],
  video: { mode: 'on', size: { width: 393, height: 852 } },
});
```

And in `playwright.config.ts`: `preserveOutput: 'always'` — without this, **passing test webms get deleted on next run**. We learned this the hard way.

## Phase 5 — per-spec validation gates (don't ship without these)

After running each spec:

| Gate | Check | Fix on fail |
|---|---|---|
| **G1: passed** | exit code 0 | Look for the timeout — usually a stuck modal or unreachable selector |
| **G2: webm exists + duration sane** | 30-180 s typical | <10 s → spec falling through every tap; tighten selectors |
| **G3: end-frame stable** | `ffmpeg -ss $(duration-1) -i webm -frames:v 1 frame.jpg` + visual check | If frozen on a modal, add `cleanFinish()` or trim the broken tail with `-t` |
| **G4: middle-frames diverse** | Sample 5 evenly-spaced frames; if 4+ are home grid, flow is stuck | Inspect the spec — `page.goto(home)` between every step kills the recording |

Bash helper: `~/.claude/skills/pwa-walkthrough-test/validate.sh`.

## Phase 6 — concat + ship

```bash
# Convert each webm to mp4 with consistent codec (concat protocol requires same codec)
for v in v1 v2 v3 v4 v5 v6; do
  src=$(find test-results -path "*walk-${v}-*" -name "video.webm" | head -1)
  ffmpeg -y -i "$src" -c:v libx264 -preset fast -crf 24 -pix_fmt yuv420p -an -movflags +faststart /tmp/walk/${v}.mp4
done
{ for v in v1 v2 v3 v4 v5 v6; do echo "file '/tmp/walk/${v}.mp4'"; done; } > /tmp/walk/concat.txt
ffmpeg -y -f concat -safe 0 -i /tmp/walk/concat.txt -c copy /tmp/walkthrough.mp4
```

**File-size envelope:** Resend max 40 MB, Gmail 25 MB. A 14-min H.264 mp4 at 393×852, CRF 24, audio off ≈ 30-50 MB. Strategies, in order of preference:
1. Drop audio (`-an`) — saves nothing big but no PII risk from background noise.
2. Higher CRF (28-30) — visible artifacting starts ~32.
3. Speed up specific sections (`setpts=0.667*PTS` for 1.5x). DON'T speed-up the whole thing — feels frantic.
4. Upload to Google Drive via MCP if mp4 is still >40 MB.

Send via Resend edge function (template at `templates/send.py`). The Supabase edge function path is project-specific — usually `<project>.supabase.co/functions/v1/send-report-email` taking `{to, subject, html, pdfBase64, filename}`.

## Phase 7 — bug-fix regression check (THE ENHANCEMENT)

The walkthrough video is the artifact. The **regression check** is the assertion that specific bugs no longer reproduce. Both should ship together.

**Bug fingerprint format** (`bugs.yml` next to the specs):

```yaml
bugs:
  - id: A
    description: Music-note glyph in voice transcription textarea
    surface: QuizCreator (and 5 other voice flows)
    fingerprint:
      type: textarea_value
      page_route: /mobile/quizzes
      action: "tap Create + record + stop"
      assertion: "value MUST NOT match /^[♪♫\\[\\]Music\\s]*$/"
    fixed_in_commit: 0b6d56f6
    verification_spec: e2e/walk/bug_A.spec.ts

  - id: 2
    description: Stacked Cancel + ✕ Close in Schedule Request-edit modal
    surface: Schedule → Request edit → Job picker
    fingerprint:
      type: dom_overlap
      page_route: /mobile/schedule
      action: "open Request edit → tap job select"
      assertion: "no two clickable elements with text /^(Close|Cancel)$/ within 50px"
    fixed_in_commit: null

  - id: 4
    description: Documents tab counts All=N but Docs/Photos/Videos=0
    surface: Files screen
    fingerprint:
      type: tab_count_mismatch
      page_route: /mobile/files
      assertion: "if 'All ({n})' n>0, at least one of Docs/Photos/Videos must be >0"
```

Each bug gets a tiny dedicated spec (`bug_A.spec.ts`, `bug_2.spec.ts`, etc.) that drives the surface and runs the assertion. Run them as a **regression-check run** alongside the walkthrough:

```bash
npx playwright test e2e/walk/bug_*.spec.ts --reporter=list
```

The output IS the regression report. Failed bug specs = bug still reproduces. Passing bug specs = fix landed.

When the user asks "did we fix the bugs?", run the bug-spec suite and report:
```
Bug A — voice ♪ glyph: PASS (0b6d56f6 verified)
Bug 2 — Cancel/Close overlap: SKIP (surface unreachable in chromium)
Bug 4 — Docs tab count: FAIL — assertion failed at /mobile/files: All=172 / Docs=0 / Photos=0 / Videos=0
```

Bug specs that can't run in chromium (iOS-only surfaces) are SKIPped with a clear `test.skip(true, 'iOS-only')` and reason — so the regression report has three states: PASS, FAIL, SKIPPED-with-reason.

## Phase 8 — commit + handoff

The spec files + helpers + bug fingerprints get committed to the repo on a `<topic>-walkthrough-<date>` branch. Tester gets:
- The MP4 (link or attachment)
- The `action_log.md` (so they can verify nothing was missed)
- The `bugs.yml` regression status
- The branch SHA so they can re-run the suite

## Pitfalls — every one of these I hit while building this

- **Sandbox blocks on `sudo systemctl start docker`** — user has to run it themselves. Ship a one-line `! sudo systemctl start docker` instruction.
- **`npx playwright test` clears `test-results/` on each invocation** — combine all specs into one invocation, OR copy webms to `/tmp/` immediately after each run.
- **`preserveOutput: 'always'` is required** for keeping passing-test videos. Default deletes them.
- **Resend / Supabase edge function rejects payloads >40 MB**. Always check `len(b64)` before posting.
- **Bash argv too small** for >1 MB base64 payloads — switch to Python `urllib.request` for `pdfBase64` blobs.
- **Sandbox blocks emailing with PII** unless user has explicitly authorized. Ask first when local data has prod-equivalent customer info.
- **Don't `gotoHome()` between every step** — that's the structural cause of "80% of the video is home grid" complaints. Use `back()` (in-app back arrow) and stay in the section.
- **Modal focus traps + missing dismiss buttons** — when a modal opens that has no Close button in DOM, the test will hang for the entire timeout. Skip the entry tap; document it.
- **Prod-vs-local localStorage key mismatch** — supabase-js derives `sb-${hostname.split('.')[0]}-auth-token`. Local: `sb-127-auth-token`. Prod: `sb-<projectref>-auth-token`. Get this wrong and login does nothing.

## What you can't do (be honest with the user up front)

- iOS-native modals (`mailto:` handoff, system password prompts, App Switcher, dynamic island) — chromium can't reproduce them.
- ServiceWorker stale-cache bugs (the iOS WKWebView "Importing a module script failed") — chromium has a different SW model.
- Real microphone audio — chromium headless has no mic stream. Use `--use-fake-device-for-media-stream` if you need ANY audio at all, but you can't repro "I spoke and Whisper returned ♪".
- Pixel-perfect cursor / finger drag — Playwright clicks by selector. The user's finger path is gone.
- Multi-page swipeable home grids — chromium swipe is unreliable. Use direct routes.

## Templates included

- `templates/_helpers.ts` — login, tap, back, scroll, cleanFinish
- `templates/_inspect.spec.ts` — DOM inspector for selector discovery
- `templates/spec.template.ts` — single-video spec scaffold with all the right config
- `templates/bug_check.template.ts` — single-bug regression spec scaffold
- `validate.sh` — gate runner (G1-G4)
- `concat.sh` — webm → mp4 → concat pipeline
- `send.py` — Resend email-with-attachment

Adapt liberally. Don't be precious about templates — every project's selectors will differ.
