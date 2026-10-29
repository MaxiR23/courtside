// web/tests/lib/components/AwardCard.test.ts
//
// Tests for the AwardCard component.
//
// Tested:
// - A player award: the code chip, the photo or initials, the award name, the winner and the team
// - No code chip for the Twyman-Stokes award
// - A team award: the name and a row per winner, fewer than five
//
// What is covered:
// - Each state a card can show, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AwardCard.test.ts
//
// SEE: web/src/lib/components/AwardCard.svelte
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import AwardCard from '../../../src/lib/components/AwardCard.svelte';

const awards = () =>
	toPlayoffsView(
		JSON.parse(
			readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'playoffs-complete.json'), 'utf8')
		) as PlayoffsFeed,
		null
	).awards;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('AwardCard', () => {
	it('draws a player award with its code, initials, name, winner and team', () => {
		const { container } = render(AwardCard, { props: { award: awards()[0]! } });
		expect(container.querySelector('.tag')?.textContent).toBe('MVP');
		expect(screen.getByRole('img', { name: 'Ada Byrne' }).textContent).toBe('AB');
		expect(screen.getByRole('heading', { name: 'Most Valuable Player' })).toBeTruthy();
		expect(screen.getByText('Ada Byrne', { selector: '.winner-name' })).toBeTruthy();
		expect(screen.getByText('QXA')).toBeTruthy();
	});

	it('draws the photo when the winner has one', () => {
		const { container } = render(AwardCard, { props: { award: awards()[1]! } });
		expect(container.querySelector('.tag')?.textContent).toBe('FMVP');
		expect(container.querySelector('img')?.getAttribute('src')).toBe(
			'https://cdn.example.com/p/a6.png'
		);
	});

	it('draws no code chip for the Twyman-Stokes award', () => {
		const { container } = render(AwardCard, { props: { award: awards()[4]! } });
		expect(screen.getByRole('heading', { name: 'Twyman-Stokes Teammate Award' })).toBeTruthy();
		expect(container.querySelector('.tag')).toBeNull();
	});

	it('draws a team award as a list of rows', () => {
		const { container } = render(AwardCard, { props: { award: awards()[5]! } });
		expect(screen.getByRole('heading', { name: 'All-NBA 1st Team' })).toBeTruthy();
		expect(container.querySelectorAll('li')).toHaveLength(5);
		expect(container.querySelector('li .winner-team')?.textContent).toBe('QXA');
	});

	it('draws the rows a team award has when it has fewer than five', () => {
		const award = { ...awards()[5]!, winners: awards()[5]!.winners.slice(0, 3) };
		const { container } = render(AwardCard, { props: { award } });
		expect(container.querySelectorAll('li')).toHaveLength(3);
	});
});
