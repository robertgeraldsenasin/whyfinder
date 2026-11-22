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

test('the deal can be skipped', async ({ page }) => {
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

test('a description deals a hand that keeps every filter (FR-18, FR-23)', async ({ page }) => {
  await ready(page);
  await page.getByLabel('Or describe it').fill('like Portal 2, co-op, under $15, blorp');
  await page.getByRole('button', { name: 'Apply' }).click();
  await expect(picks(page).first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/Not understood: “blorp”/)).toBeVisible();
  const chips = page.getByRole('list', { name: 'Filters' }).getByRole('button');
  await expect(chips).toHaveCount(2);
  await expect(page.getByRole('heading', { name: 'Because you love' })).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('.facts span').last()).toHaveText(/^(Free|\$([0-9]|1[0-4])\.\d\d|\$15\.00)$/);

  // A filter no game can pass: the hand is empty and says why.
  await page.getByLabel('Describe what you want').fill('free, before 1999');
  await page.getByRole('button', { name: 'Apply' }).click();
  await page.getByRole('button', { name: /Update my picks/ }).click();
  await expect(page.getByText(/No game among the 500 passes every filter/)).toBeVisible({ timeout: 15_000 });
  await chips.filter({ hasText: /or earlier/ }).click();
  await expect(chips).toHaveCount(2);
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

  await page.getByRole('navigation', { name: 'Pipeline stages' }).getByRole('button').nth(7).click();
  await expect(page.getByRole('heading', { name: 'Grounded words, checked' })).toBeVisible();
  await expect(page.getByText(/^A1/).first()).toBeVisible();
  const next = page.getByRole('button', { name: 'Next step' });
  await next.click();
  await expect(page.getByText(/is the biggest driver of this pick \(\d+%\)/)).toBeVisible();
  await next.click();
  await expect(page.getByText(/^All \d sentences pass/)).toBeVisible();
  await next.click();
  await expect(page.getByText(/^Rejected\./)).toBeVisible();
  await expect(page.getByText(/names a game outside the pick and the history/)).toBeVisible();
  await expect(page.getByText(/matches no cited share/)).toBeVisible();
  await axe(page);
});

test('live mode asks a running API for its sentences about the same pick', async ({ page }) => {
  const cors = { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'content-type', 'access-control-allow-methods': 'POST' };
  const asked: { liked_game_ids: string[]; game_id: string }[] = [];
  await page.route('http://api.test/explain', async (route) => {
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors });
    const body = route.request().postDataJSON() as { liked_game_ids: string[]; game_id: string };
    asked.push(body);
    return route.fulfill({
      status: 200,
      headers: cors,
      json: {
        game_id: body.game_id,
        title: 'a pick',
        rank: 2,
        claims: [{ text: 'XCOM: Enemy Unknown counted for most of it.', evidence: [{ type: 'attribution', game_id: '200510', share: 0.5 }] }],
        checker: { passed: true, fallback_used: false, reasons: ['first try: 70% matches no cited share'] },
        model_version: 'blend-slice-1',
      },
    });
  });
  await page.goto('./?api=http://api.test/');
  await expect(page.getByRole('button', { name: /Puzzles and stories/ })).toBeEnabled({ timeout: 30_000 });
  await page.getByRole('link', { name: 'Under the hood' }).click();
  await page.getByRole('button', { name: /Run it on FTL, Isaac and XCOM/ }).click();
  await page.getByRole('navigation', { name: 'Pipeline stages' }).getByRole('button').nth(7).click();
  for (let k = 0; k < 4; k++) await page.getByRole('button', { name: 'Next step' }).click();
  await expect(page.getByText('A model wrote these, and the checker passed them', { exact: false })).toBeVisible();
  await expect(page.getByText('XCOM: Enemy Unknown counted for most of it.')).toBeVisible();
  await expect(page.getByText(/Turned down first: first try: 70% matches no cited share/)).toBeVisible();
  expect(asked.at(-1)?.liked_game_ids).toHaveLength(3);

  await page.unroute('http://api.test/explain');
  await page.route('http://api.test/explain', (route) => route.abort());
  await page.getByRole('button', { name: /^Pick 2:/ }).click();
  await expect(page.getByText(/could not reach http:\/\/api\.test/)).toBeVisible();
});

test('without ?api= the last Words step explains how to run one', async ({ page }) => {
  await ready(page);
  await page.getByRole('link', { name: 'Under the hood' }).click();
  await page.getByRole('button', { name: /Run it on FTL, Isaac and XCOM/ }).click();
  await page.getByRole('navigation', { name: 'Pipeline stages' }).getByRole('button').nth(7).click();
  for (let k = 0; k < 4; k++) await page.getByRole('button', { name: 'Next step' }).click();
  await expect(page.getByText('docker run -p 8000:8000 ghcr.io/robertgeraldsenasin/whyfinder-api')).toBeVisible();
  await expect(page.getByRole('link', { name: /open this page with \?api=/ })).toHaveAttribute('href', '?api=http://localhost:8000#/hood');
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
