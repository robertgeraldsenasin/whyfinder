import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, test } from '@playwright/test';

async function ready(page: Page): Promise<void> {
  await page.goto('./');
  await expect(page.getByRole('button', { name: /Puzzles and stories/ })).toBeEnabled({ timeout: 30_000 });
}

async function axe(page: Page): Promise<void> {
  // Let entrance animations finish: axe measures contrast at the current opacity.
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => undefined))));
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

const picks = (page: Page) => page.getByRole('region', { name: 'Your picks' }).getByRole('button');

test('search, add three games and watch ten explained picks fall', async ({ page }) => {
  await ready(page);
  for (const title of ['Portal 2', 'Half-Life 2', 'Undertale']) {
    const search = page.getByRole('combobox', { name: 'Add a game you like' });
    await search.fill(title);
    await expect(page.getByRole('option').first()).toBeVisible();
    await page.getByRole('option', { name: new RegExp(`^${title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`) }).first().click();
  }
  await expect(page.getByRole('list', { name: 'Your games and hours played' }).getByRole('listitem')).toHaveCount(3);
  await page.getByRole('button', { name: 'Find my next game' }).click();
  await expect(picks(page)).toHaveCount(10, { timeout: 15_000 });
  // The hand: dealt Ace to 10, each card's suit naming the part of the model that carried it.
  await expect(picks(page).first()).toHaveAccessibleName(/^Ace of (hearts|clubs):/);
  await expect(picks(page).nth(9)).toHaveAccessibleName(/^10 of (hearts|clubs):/);
  await expect(page.getByText('Hearts: mostly players in common')).toBeVisible();
  await expect(page.getByText(/carried this pick, \d+% of the score/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Because you love' })).toBeVisible();
  await expect(page.getByText(/these shares are exact/i)).toBeVisible();
  await expect(page.getByText(/drops out of your ten/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'View on Steam' })).toHaveAttribute('href', /^https:\/\/store\.steampowered\.com\/app\/\d+$/);

  // Keyboard: move to the next pick with the arrow key.
  await picks(page).first().focus();
  await page.keyboard.press('ArrowRight');
  await expect(picks(page).nth(1)).toHaveAttribute('aria-pressed', 'true');
});

test('the starfall can be skipped', async ({ page }) => {
  await ready(page);
  await page.getByRole('button', { name: /Survival crews/ }).click();
  await page.getByRole('button', { name: 'Skip' }).click();
  await expect(picks(page)).toHaveCount(10);
  await expect(page.getByRole('heading', { name: 'Because you love' })).toBeVisible();
});

test('a preset sky flags picks kept for variety and shows what players say', async ({ page }) => {
  await ready(page);
  await page.getByRole('button', { name: /Roguelike runs/ }).click();
  await expect(picks(page)).toHaveCount(10, { timeout: 15_000 });
  await expect(page.getByText(/picked for variety/).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: /^(Players who also played .+ say|What players say)$/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: /^(Both communities talk about|Players talk about)$/ })).toBeVisible();
});

test('settings change the star colours and are remembered', async ({ page }) => {
  await ready(page);
  await page.getByRole('button', { name: 'Settings' }).click();
  const dialog = page.getByRole('dialog', { name: 'Settings' });
  await expect(dialog.getByRole('radio', { name: /Crimson and violet/ })).toBeChecked();
  await dialog.getByRole('radio', { name: /Star temperature/ }).check();
  await dialog.getByRole('radio', { name: /Reduced flashing/ }).check();
  await axe(page);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  const sound = page.getByRole('button', { name: 'Sound effects' });
  await expect(sound).toHaveAttribute('aria-pressed', 'true');
  await sound.click();
  await expect(sound).toHaveAttribute('aria-pressed', 'false');

  await page.reload();
  await ready(page);
  await expect(page.getByRole('button', { name: 'Sound effects' })).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('button', { name: 'Settings' }).click();
  await expect(page.getByRole('radio', { name: /Star temperature/ })).toBeChecked();
  await expect(page.getByRole('radio', { name: /Reduced flashing/ })).toBeChecked();
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

test('no WCAG 2.1 AA violations on any view', async ({ page }) => {
  await ready(page);
  await axe(page);
  await page.getByRole('button', { name: /Puzzles and stories/ }).click();
  await expect(picks(page)).toHaveCount(10, { timeout: 15_000 });
  await expect(page.getByRole('heading', { name: 'Because you love' })).toBeVisible();
  await axe(page);
  await page.getByRole('link', { name: 'Under the hood' }).click();
  await expect(page.getByRole('heading', { name: 'Your history becomes a vector' })).toBeVisible();
  await axe(page);
  await page.getByRole('link', { name: 'Architecture' }).click();
  await expect(page.getByRole('heading', { name: /7.8 million reviews/ })).toBeVisible();
  await axe(page);
});

test.describe('reduced motion', () => {
  test.use({ reducedMotion: 'reduce' });
  test('everything still works, and the picks appear in place', async ({ page }) => {
    await ready(page);
    await page.getByRole('button', { name: /Survival crews/ }).click();
    await expect(picks(page)).toHaveCount(10);
    await expect(page.getByRole('button', { name: 'Skip' })).toBeHidden();
    await expect(page.getByRole('heading', { name: 'Because you love' })).toBeVisible();
  });
});
