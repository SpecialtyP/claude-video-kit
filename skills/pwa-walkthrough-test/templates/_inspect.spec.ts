/**
 * One-shot DOM inspector. Run BEFORE authoring walkthrough specs to discover
 * the actual selectors on each screen. Output: copy/paste-able selectors.
 *
 * Usage:
 *   npx playwright test e2e/walk/_inspect.spec.ts --reporter=list
 */
import { test } from '@playwright/test';
import { BASE_URL, login, pause } from './_helpers';

test.use({
  viewport: { width: 393, height: 852 },
  hasTouch: true,
  isMobile: true,
});

const ROUTES_TO_INSPECT = [
  '/mobile/home',
  '/mobile/projects',
  // add the routes you'll visit in the walkthrough
];

for (const route of ROUTES_TO_INSPECT) {
  test(`inspect ${route}`, async ({ page }) => {
    await login(page);
    await page.goto(`${BASE_URL}${route}`, { waitUntil: 'domcontentloaded' });
    await pause(page, 2500);

    const info = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button')).slice(0, 40);
      return {
        url: window.location.pathname,
        clickables: buttons.map((el: any) => ({
          text: (el.textContent || '').trim().slice(0, 50),
          ariaLabel: el.getAttribute('aria-label')?.slice(0, 50) || null,
          svgClass: el.querySelector('svg')?.getAttribute('class')?.slice(0, 60) || null,
        })),
        // tabs
        tabs: Array.from(document.querySelectorAll('[role="tab"], [role="tablist"] button')).map(
          (el: any) => (el.textContent || '').trim()
        ),
        // headings (helps identify modals)
        headings: Array.from(document.querySelectorAll('h1, h2, h3, [role="heading"]'))
          .slice(0, 10)
          .map((el: any) => (el.textContent || '').trim()),
        // page-indicator dots (multi-page home grids)
        dotCount: document.querySelectorAll('[class*="dot"], [aria-label*="page" i]').length,
      };
    });

    console.log(`\n=== ${route} ===`);
    console.log(JSON.stringify(info, null, 2));
  });
}
