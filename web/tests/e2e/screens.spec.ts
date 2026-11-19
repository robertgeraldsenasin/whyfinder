/**
 * Screenshots of every view, for reviewing a branch and for release notes (`npm run screens`).
 * Skipped in the normal e2e run; CI keeps the images as the `screens` artifact.
 */
import { expect, type Page, test } from '@playwright/test';

test.skip(!process.env.WHYFINDER_SCREENS, 'set WHYFINDER_SCREENS=1 (npm run screens)');

async function shot(page: Page, name: string): Promise<void> {
  const project = test.info().project.name;
  await page.screenshot({ path: `screens/${project}-${name}.png` });
}

async function ready(page: Page): Promise<void> {
  await page.goto('./');
  await expect(page.getByRole('button', { name: /Puzzles and stories/ })).toBeEnabled({ timeout: 30_000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
}

test('title, starfall frames, the pick, settings', async ({ page }) => {
  await ready(page);
  await shot(page, '01-title');
  await page.getByRole('button', { name: /Roguelike runs/ }).click();
  // Frames of the starfall, at these times after the click.
  let elapsed = 0;
  for (const [k, at] of [600, 900, 1500, 2600, 3600, 4300].entries()) {
    await page.waitForTimeout(at - elapsed);
    elapsed = at;
    await shot(page, `02-fall-${k}`);
  }
  await expect(page.getByRole('heading', { name: 'Because you love' })).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(1600);
  await shot(page, '03-picks');
  await page.getByRole('region', { name: 'Your picks' }).getByRole('button').nth(3).click();
  await page.waitForTimeout(900);
  await shot(page, '04-pick-4');
  await page.getByRole('button', { name: 'Settings' }).click();
  await page.waitForTimeout(300);
  await shot(page, '05-settings');
});

test('under the hood and architecture', async ({ page }) => {
  await ready(page);
  await page.getByRole('link', { name: 'Under the hood' }).click();
  await page.waitForTimeout(500);
  await shot(page, '06-hood-empty');
  await page.getByRole('button', { name: /Run it on FTL, Isaac and XCOM/ }).click();
  await expect(page.getByRole('heading', { name: 'Your history becomes a vector' })).toBeVisible();
  await page.getByRole('navigation', { name: 'Pipeline stages' }).getByRole('button').nth(2).click();
  await page.waitForTimeout(1200);
  await shot(page, '07-hood-push');
  await page.getByRole('link', { name: 'Architecture' }).click();
  await expect(page.getByRole('heading', { name: /7.8 million reviews/ })).toBeVisible();
  await page.waitForTimeout(600);
  await shot(page, '08-architecture');
});
