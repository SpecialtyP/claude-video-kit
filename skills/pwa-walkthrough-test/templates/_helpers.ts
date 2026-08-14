/**
 * Shared helpers for PWA walkthrough specs. Copy to <repo>/e2e/walk/_helpers.ts
 * and adjust BASE_URL / SUPABASE_REF / login() to your project.
 */
import type { Page } from '@playwright/test';

export const BASE_URL = `http://localhost:${process.env.E2E_PORT || '5208'}`;
export const SUPABASE_URL = process.env.E2E_SUPABASE_URL || 'http://127.0.0.1:54321';
export const SUPABASE_KEY =
  process.env.E2E_SUPABASE_KEY || ''; // local publishable key from `supabase status`
export const SUPABASE_REF = process.env.E2E_SUPABASE_REF || '127';
export const LOGIN_EMAIL = process.env.E2E_LOGIN_EMAIL || '';
export const LOGIN_PASSWORD = process.env.E2E_LOGIN_PASSWORD || '';

export const TAP_TIMEOUT = 1500;
export const SETTLE = 700;
export const READ = 1500;

export async function pause(page: Page, ms: number) {
  await page.waitForTimeout(ms);
}

/**
 * Authenticate via Supabase REST + inject session into localStorage.
 *
 * The localStorage key is `sb-${ref}-auth-token` where `ref` is the first
 * segment of the URL hostname:
 *   - prod   <projectref>.supabase.co  →  sb-<projectref>-auth-token
 *   - local  127.0.0.1                 →  sb-127-auth-token
 * Get this wrong and the session is set under a key the app doesn't read,
 * so login appears to succeed but the app stays unauthenticated.
 */
export async function login(page: Page) {
  const credentials =
    LOGIN_EMAIL ? { email: LOGIN_EMAIL, password: LOGIN_PASSWORD }
                : { phone: process.env.E2E_LOGIN_PHONE, password: LOGIN_PASSWORD };
  const resp = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY },
    body: JSON.stringify(credentials),
  });
  if (!resp.ok) throw new Error(`Auth failed: ${resp.status} ${await resp.text()}`);
  const session = await resp.json();
  await page.goto(BASE_URL, { waitUntil: 'commit' });
  const storageKey = `sb-${SUPABASE_REF}-auth-token`;
  const storageValue = JSON.stringify({
    access_token: session.access_token,
    refresh_token: session.refresh_token,
    expires_in: session.expires_in,
    expires_at: session.expires_at,
    token_type: session.token_type,
    user: session.user,
  });
  await page.evaluate(([k, v]) => localStorage.setItem(k, v), [storageKey, storageValue]);
}

/**
 * Tap by exact visible text. Returns false if missing — never throws —
 * so the spec keeps moving instead of timing out on every miss.
 */
export async function tap(page: Page, label: string, settle = SETTLE): Promise<boolean> {
  const re = new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`, 'i');
  const target = page.locator('a, button, [role="button"]').filter({ hasText: re }).first();
  try {
    await target.waitFor({ state: 'visible', timeout: TAP_TIMEOUT });
    await target.click({ delay: 60 });
    await pause(page, settle);
    return true;
  } catch {
    console.log(`  · skip tap "${label}" — not visible`);
    return false;
  }
}

/** Tap by partial text match (looser than `tap`). */
export async function tapContains(page: Page, text: string, settle = SETTLE): Promise<boolean> {
  const target = page.locator('a, button, [role="button"]').filter({ hasText: new RegExp(text, 'i') }).first();
  try {
    await target.waitFor({ state: 'visible', timeout: TAP_TIMEOUT });
    await target.click({ delay: 60 });
    await pause(page, settle);
    return true;
  } catch {
    return false;
  }
}

/**
 * Prefer the in-app back arrow (no SPA reload) over page.goBack.
 * Reduces home-grid dead time by ~1.5s per call vs page.goto(home).
 */
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

export async function scroll(page: Page, dy: number, settle = 700) {
  await page.evaluate((y) => window.scrollBy({ top: y, behavior: 'smooth' }), dy);
  await pause(page, settle);
}

/** Type into a field by selector, character-by-character with realistic delay. */
export async function typeChar(page: Page, selector: string, text: string, settle = 500) {
  try {
    const el = page.locator(selector).first();
    await el.waitFor({ state: 'visible', timeout: 1500 });
    await el.click();
    await el.fill('');
    await el.type(text, { delay: 70 });
    await pause(page, settle);
    return true;
  } catch {
    return false;
  }
}

/**
 * Run this LAST in every spec. Guarantees:
 *   1. Any open modal is dismissed (Escape × 3)
 *   2. The page lands on a stable home grid
 *   3. The recording's final frame is NOT a frozen mid-action state
 *
 * Without this, tests that hit their timeout cap leave the recording
 * frozen on whatever modal was open when chromium got killed.
 */
export async function cleanFinish(page: Page) {
  for (let i = 0; i < 3; i++) {
    await page.keyboard.press('Escape').catch(() => {});
    await pause(page, 250);
  }
  await page.goto(`${BASE_URL}/mobile/home`, { waitUntil: 'domcontentloaded' });
  await pause(page, 1500);
}
