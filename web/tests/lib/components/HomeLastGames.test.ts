// web/tests/lib/components/HomeLastGames.test.ts
//
// Tests for the Last games section of the home with no games.
//
// Tested:
// - Desktop: one row per game with the label, both names, both scores and the dash
// - Mobile: one card per game with the label and two team rows
// - The header: kicker, title as the h2, count
// - Each row or card is one link to /game/{id} with no other link inside
// - The losing side and its score carry the loser class; the winner does not; none when no winner
// - The loser rule uses the loser opacity token
// - Each side's --side-accent is the feed color, or the neutral accent when null
// - A logo draws an img and a null logo the code monogram
// - Spoiler-free: Tap to reveal, no score, no loser class, in both layouts
// - Spanish copy of the reveal line
//
// What is covered:
// - Each state of both layouts; jsdom does not lay out, so classes and the source are asserted
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/HomeLastGames.test.ts
//
// SEE: web/src/lib/components/HomeLastGames.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { HomeLastGamesView } from '../../../src/lib/home/types';
import { preferLanguages } from '../../prefer-languages';

import HomeLastGames from '../../../src/lib/components/HomeLastGames.svelte';

const team = (code: string, name: string, logo?: { light: string; dark: string | null }) => ({
	code,
	name,
	city: `${name} City`,
	guest: false,
	...(logo ? { logo } : {})
});
const view: HomeLastGamesView = {
	title: 'Last night',
	count: '2 games',
	games: [
		{
			id: 'g1',
			label: 'Final',
			away: { team: team('NRT', 'Northerners'), score: 104, loser: true, accent: '#1D4E89' },
			home: {
				team: team('STH', 'Southerners', { light: 'https://example.com/sth.svg', dark: null }),
				score: 112,
				loser: false,
				accent: null
			}
		},
		{
			id: 'g2',
			label: 'First round · Game 3',
			away: { team: team('EST', 'Easterners'), score: 99, loser: false, accent: null },
			home: { team: team('WST', 'Westerners'), score: 99, loser: false, accent: null }
		}
	]
};
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('HomeLastGames', () => {
	it('draws the header', () => {
		render(HomeLastGames, { props: { view, layout: 'desktop', gameHref } });
		expect(screen.getByText('Last games')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('Last night');
		expect(screen.getByText('2 games')).toBeTruthy();
	});

	it('draws a desktop row per game with labels, names, scores and the dash', () => {
		const { container } = render(HomeLastGames, { props: { view, layout: 'desktop', gameHref } });
		expect(container.querySelector('.mobile')).toBeNull();
		const rows = container.querySelectorAll('a.game');
		expect(rows).toHaveLength(2);
		expect(rows[0].textContent).toContain('Final');
		expect(rows[0].textContent).toContain('Northerners');
		expect(rows[0].textContent).toContain('Southerners');
		expect(rows[0].querySelectorAll('.score')).toHaveLength(2);
		expect(rows[0].querySelector('.dash')?.textContent).toBe('–');
		expect(rows[1].textContent).toContain('First round · Game 3');
	});

	it('draws a mobile card per game with the label and two team rows', () => {
		const { container } = render(HomeLastGames, { props: { view, layout: 'mobile', gameHref } });
		expect(container.querySelector('section.last-games.mobile')).not.toBeNull();
		const cards = container.querySelectorAll('a.game');
		expect(cards).toHaveLength(2);
		expect(cards[0].querySelector('.label')?.textContent).toBe('Final');
		expect(cards[0].querySelectorAll('.team-row')).toHaveLength(2);
		expect(cards[0].querySelectorAll('.score')).toHaveLength(2);
	});

	it.each(['desktop', 'mobile'] as const)('links each %s game once to its page', (layout) => {
		const { container } = render(HomeLastGames, { props: { view, layout, gameHref } });
		const links = [...container.querySelectorAll('a')];
		expect(links.map((a) => a.getAttribute('href'))).toEqual(['/game/g1', '/game/g2']);
		expect(container.querySelectorAll('a a')).toHaveLength(0);
	});

	it.each(['desktop', 'mobile'] as const)('dims only the losing side in %s', (layout) => {
		const { container } = render(HomeLastGames, { props: { view, layout, gameHref } });
		const [first, second] = container.querySelectorAll('a.game');
		expect(first.querySelectorAll('.loser').length).toBeGreaterThan(0);
		for (const el of first.querySelectorAll('.loser')) {
			expect(el.textContent).toMatch(/Northerners|104/);
		}
		expect(first.textContent).toContain('112');
		expect(second.querySelector('.loser')).toBeNull();
	});

	it('reads the loser opacity from its token', () => {
		const source = readFileSync(
			join(import.meta.dirname, '../../../src/lib/components/HomeLastGames.svelte'),
			'utf8'
		);
		expect(source).toMatch(/\.loser\s*{[^}]*opacity: var\(--home-last-games-loser-opacity\)/);
	});

	it('sets the side accent from the feed or the neutral accent', () => {
		const { container } = render(HomeLastGames, { props: { view, layout: 'desktop', gameHref } });
		const sides = container
			.querySelectorAll<HTMLElement>('a.game')[0]
			.querySelectorAll<HTMLElement>('.side');
		expect(sides[0].style.getPropertyValue('--side-accent')).toBe('#1D4E89');
		expect(sides[1].style.getPropertyValue('--side-accent')).toBe('var(--identity-neutral-accent)');
	});

	it('draws a logo as an image and a missing logo as the code', () => {
		const { container } = render(HomeLastGames, { props: { view, layout: 'desktop', gameHref } });
		const first = container.querySelectorAll('a.game')[0];
		expect(first.querySelectorAll('img')).toHaveLength(1);
		expect(first.textContent).toContain('NRT');
	});

	it.each(['desktop', 'mobile'] as const)(
		'hides the scores and the dimming with spoiler-free in %s',
		(layout) => {
			const { container } = render(HomeLastGames, {
				props: { view, layout, spoilerFree: true, gameHref }
			});
			expect(screen.getAllByText('Tap to reveal')).toHaveLength(2);
			expect(container.querySelector('.score')).toBeNull();
			expect(container.querySelector('.loser')).toBeNull();
			expect(container.textContent).not.toContain('104');
		}
	);

	it('speaks Spanish', () => {
		preferLanguages(['es']);
		render(HomeLastGames, { props: { view, layout: 'desktop', spoilerFree: true, gameHref } });
		expect(screen.getAllByText('Toca para ver')).not.toHaveLength(0);
	});
});
