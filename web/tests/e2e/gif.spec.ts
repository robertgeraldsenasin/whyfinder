/**
 * The README's demo GIF (`npm run gif`, then the demo-gif workflow turns the video into a GIF).
 * Skipped in the normal e2e run. Records one session: describe what you want, watch the hand
 * dealt, open a pick and read why.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

test.skip(!process.env.WHYFINDER_GIF, 'set WHYFINDER_GIF=1 (npm run gif)');
test.use({ viewport: { width: 1280, height: 800 }, video: { mode: 'on', size: { width: 1280, height: 800 } } });

test('the README demo', async ({ page }) => {
  const opened = Date.now();
  await page.goto('./');
  await expect(page.getByRole('button', { name: /Puzzles and stories/ })).toBeEnabled({ timeout: 30_000 });
  await page.evaluate(() => document.fonts.ready);
  // The GIF starts here: everything before is loading.
  mkdirSync('test-results', { recursive: true });
  writeFileSync('test-results/gif-start.txt', ((Date.now() - opened) / 1000).toFixed(2));
  await page.waitForTimeout(900);
  const describe = page.getByLabel('Or describe it');
  await describe.click();
  await describe.pressSequentially('like Portal 2, co-op, under $20', { delay: 55 });
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: 'Apply' }).click();
  const picks = page.getByRole('region', { name: 'Your picks' }).getByRole('button');
  await expect(picks.first()).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(4800); // the deal
  await picks.nth(1).click();
  await page.waitForTimeout(2600);
  await page.mouse.wheel(0, 420);
  await page.waitForTimeout(2600);
  await page.mouse.wheel(0, -420);
  await page.waitForTimeout(1200);
});
