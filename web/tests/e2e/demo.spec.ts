import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, test } from '@playwright/test';

async function ready(page: Page): Promise<void> {
  await page.goto('./');
  await expect(page.getByText('Engine live in your browser')).toBeVisible({ timeout: 30_000 });
}

async function axe(page: Page): Promise<void> {
  // Let entrance animations finish: axe measures contrast at the current opacity.
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => undefined))));
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

test('search, add three games and get ten explained picks', async ({ page }) => {
  await ready(page);
  const search = page.getByRole('combobox', { name: 'Add a game you like' });
  for (const title of ['Portal 2', 'Half-Life 2', 'Undertale']) {
    await search.fill(title);
    await expect(page.getByRole('option').first()).toBeVisible();
    await page.getByRole('option', { name: new RegExp(`^${title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`) }).first().click();
  }
  await expect(page.getByRole('list', { name: 'Your games and hours played' }).getByRole('listitem')).toHaveCount(3);
  await page.getByRole('button', { name: 'Find my picks' }).click();
  const picks = page.getByRole('region', { name: 'Your picks' }).getByRole('button');
  await expect(picks).toHaveCount(10);
  await expect(page.getByText('What drove it')).toBeVisible();
  await expect(page.getByText(/shares are exact/i)).toBeVisible();
  await expect(page.getByText(/drops out of your top 10|Only removing your whole list/)).toBeVisible();

  // Keyboard: move to the next pick with the arrow key.
  await picks.first().focus();
  await page.keyboard.press('ArrowRight');
  await expect(picks.nth(1)).toHaveAttribute('aria-pressed', 'true');
});

test('a constellation preset runs and flags picks kept for variety', async ({ page }) => {
  await ready(page);
  await page.getByRole('button', { name: /Roguelike runs/ }).click();
  await expect(page.getByRole('region', { name: 'Your picks' }).getByRole('button')).toHaveCount(10);
  await expect(page.getByText('Kept for variety').first()).toBeVisible();
});

test('under the hood replays every stage on your history', async ({ page }) => {
  await ready(page);
  await page.getByRole('link', { name: 'Under the hood' }).click();
  await page.getByRole('button', { name: /Run it on FTL, Isaac and XCOM/ }).click();
  await expect(page.getByRole('heading', { name: 'Your history becomes a vector' })).toBeVisible();
  const stages = [
    'EASE^R: a closed-form co-play model',
    'PageRank by forward push',
    'One additive blend',
    'Drop what you own, shortlist 100',
    'DPP: variety without losing relevance',
    'Exact reasons, smallest counterfactual',
  ];
  for (const [k, title] of stages.entries()) {
    await page.getByRole('navigation', { name: 'Pipeline stages' }).getByRole('button').nth(k + 1).click();
    await expect(page.getByRole('heading', { name: title })).toBeVisible();
  }
  await expect(page.getByText(/\|Δ\| = /)).toBeVisible();
  await expect(page.getByText(/pick gone/i).first()).toBeVisible();
});

test('architecture replays a request with live timings', async ({ page }) => {
  await ready(page);
  await page.getByRole('link', { name: 'Architecture' }).click();
  await expect(page.getByRole('heading', { name: /7.8 million reviews/ })).toBeVisible();
  await page.getByRole('button', { name: 'Replay a request' }).click();
  await expect(page.getByRole('button', { name: /^explain \d+ re-runs/ })).toBeVisible({ timeout: 20_000 });
  await page.getByRole('button', { name: /^parse / }).click();
  await expect(page.getByRole('complementary').getByText('7,793,069 lines')).toBeVisible();
});

for (const [theme, scheme] of [
  ['Deep Field', 'dark'],
  ['Atlas Paper', 'light'],
] as const) {
  test.describe(theme, () => {
    test.use({ colorScheme: scheme });
    test(`no WCAG 2.1 AA violations in ${theme}`, async ({ page }) => {
      await ready(page);
      await expect(page.locator('html')).toHaveAttribute('data-theme', scheme === 'dark' ? 'deep-field' : 'atlas-paper');
      await axe(page);
      await page.getByRole('button', { name: /Puzzles & stories/ }).click();
      await expect(page.getByRole('region', { name: 'Your picks' }).getByRole('button')).toHaveCount(10);
      await axe(page);
      await page.getByRole('link', { name: 'Under the hood' }).click();
      await expect(page.getByRole('heading', { name: 'Your history becomes a vector' })).toBeVisible();
      await axe(page);
      await page.getByRole('link', { name: 'Architecture' }).click();
      await expect(page.getByRole('heading', { name: /7.8 million reviews/ })).toBeVisible();
      await axe(page);
    });
  });
}

test('the theme toggle switches and is remembered', async ({ page }) => {
  await ready(page);
  const before = await page.locator('html').getAttribute('data-theme');
  await page.getByRole('button', { name: /^Switch to/ }).click();
  const after = await page.locator('html').getAttribute('data-theme');
  expect(after).not.toBe(before);
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', after!);
});

test.describe('reduced motion', () => {
  test.use({ reducedMotion: 'reduce' });
  test('everything still works without animation', async ({ page }) => {
    await ready(page);
    await page.getByRole('button', { name: /Survival crews/ }).click();
    await expect(page.getByRole('region', { name: 'Your picks' }).getByRole('button')).toHaveCount(10);
    await expect(page.getByText('What drove it')).toBeVisible();
  });
});
