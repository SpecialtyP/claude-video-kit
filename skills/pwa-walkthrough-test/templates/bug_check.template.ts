/**
 * Single-bug regression check. One spec per bug.
 *
 * Naming: e2e/walk/bug_<id>.spec.ts
 *
 * Pattern: drive the surface where the bug lived → assert the fingerprint
 *          (something measurable in the DOM that proves the bug is fixed
 *          OR still present).
 *
 * Run them together:
 *   npx playwright test e2e/walk/bug_*.spec.ts --reporter=list
 *
 * The output IS the regression report:
 *   ✓ bug_A — voice ♪ glyph     (fix landed)
 *   ✘ bug_4 — Documents tab    (bug still reproduces)
 *   ⏭ bug_2 — Cancel/Close     (skipped — iOS-only surface)
 */
import { test, expect } from '@playwright/test';
import { BASE_URL, login, tap, pause } from './_helpers';

test.use({
  viewport: { width: 393, height: 852 },
  hasTouch: true,
  isMobile: true,
  permissions: ['microphone', 'geolocation'],
});

test('bug_<ID>: <one-line description>', async ({ page }) => {
  test.setTimeout(2 * 60 * 1000);

  // (Optional) skip if surface isn't reproducible in chromium
  // test.skip(true, 'iOS-only — mailto: handoff');

  await login(page);
  await page.goto(`${BASE_URL}/mobile/<route>`, { waitUntil: 'domcontentloaded' });
  await pause(page, 2000);

  // ─── Drive the surface to the buggy state ──────────────────────────
  // await tap(page, 'Some tile');
  // await pause(page, 1500);

  // ─── ASSERT THE FINGERPRINT ────────────────────────────────────────
  // Examples:

  // (a) "Textarea must NOT contain Whisper non-speech glyphs"
  //   const tt = page.locator('textarea[name*="transcription" i]');
  //   await expect(tt).not.toHaveValue(/^[♪♫\[\]Music\s]*$/);

  // (b) "All ({n}) and Docs/Photos/Videos tab counts must be consistent"
  //   const all  = await page.locator('button:has-text("All (")').textContent();
  //   const docs = await page.locator('button:has-text("Docs (")').textContent();
  //   const allN  = parseInt(all?.match(/\((\d+)\)/)?.[1] ?? '0', 10);
  //   const docsN = parseInt(docs?.match(/\((\d+)\)/)?.[1] ?? '0', 10);
  //   if (allN > 0) expect(docsN).toBeGreaterThan(0);

  // (c) "No two clickable elements with text Cancel/Close within 50px"
  //   const els = await page.locator('button').filter({ hasText: /^(Cancel|Close)$/i }).boundingBoxes(...);
  //   // (custom geometry check — write a helper if you find yourself reusing this)

  // (d) "Toast must show real error text, not a generic message"
  //   const toast = page.locator('[data-sonner-toast]').first();
  //   await expect(toast).toContainText(/specific error keyword/);
});
