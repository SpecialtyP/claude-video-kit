/**
 * Single-flow walkthrough spec scaffold. Copy + rename for each video/flow.
 *
 * Naming convention:
 *   e2e/walk/v{N}.spec.ts   — one spec per source recording
 *   e2e/walk/<flow>.spec.ts — for ad-hoc flows
 */
import { test, expect } from '@playwright/test';
import { BASE_URL, login, tap, back, pause, scroll, cleanFinish, READ } from './_helpers';

test.use({
  viewport: { width: 393, height: 852 },               // iPhone 16 logical
  userAgent:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  hasTouch: true,
  isMobile: true,
  permissions: ['microphone', 'geolocation'],
  video: { mode: 'on', size: { width: 393, height: 852 } },
});

test('flow: <name>', async ({ page }) => {
  test.setTimeout(5 * 60 * 1000);                       // generous; aim for <90s actual

  page.on('pageerror', (err) => console.log('PAGE ERROR:', err.message));

  await login(page);
  await page.goto(`${BASE_URL}/mobile/<starting-route>`, { waitUntil: 'domcontentloaded' });
  await pause(page, 2000);

  // ─── Action sequence (paste from action_log.md) ────────────────────
  // [00:01-04] Tile X → drill into screen
  await tap(page, 'X');
  await pause(page, READ);

  // [00:04-08] Tab toggle inside section
  await tap(page, 'Tab A');
  await pause(page, READ);

  // [00:08-12] Form field interaction
  // await typeChar(page, 'input[placeholder*="search" i]', 'query');

  // [00:12-15] Open and dismiss a modal via in-app Cancel
  // (NEVER open modals that have no programmatic dismiss — they hang the test)
  // await tap(page, 'Open something');
  // await tap(page, 'Cancel');

  // ─── Always last: leaves recording on a stable home grid ───────────
  await cleanFinish(page);
  expect(true).toBe(true);
});
