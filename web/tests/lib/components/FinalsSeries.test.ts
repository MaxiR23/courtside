// web/tests/lib/components/FinalsSeries.test.ts
//
// Tests for the FinalsSeries component.
//
// Tested:
// - One tab per game with the game number, the winner, the score and OT; the champion's wins in accent
// - The first tab pressed; a click selects its game
// - The highlight thumbnail, then the player on click; Highlights not available without a video
// - No chart for a game without a curve, the score line, the leaders and the link still shown
// - No game link when the game is not linked
// - A bound selected index from the parent shows that game, and a tab click updates it
//
// What is covered:
// - Each state the section shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/FinalsSeries.test.ts
//
// SEE: web/src/lib/components/FinalsSeries.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../../../src/lib/contract/playoffs-finals';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import FinalsSeries from '../../../src/lib/components/FinalsSeries.svelte';

const read = <T>(file: string): T =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', file), 'utf8')) as T;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const show = (change: (f: PlayoffsFinalsFeed) => void = () => {}) => {
	const finals = read<PlayoffsFinalsFeed>('playoffs-finals.json');
	change(finals);
	const games = toPlayoffsView(read<PlayoffsFeed>('playoffs-complete.json'), finals).series;
	return render(FinalsSeries, { props: { games, layout: 'desktop' as const, teamHref, gameHref } });
};
const tabs = () =>
	screen.getAllByRole('button', { pressed: undefined }).filter((b) => b.classList.contains('tab'));

afterEach(() => {
	vi.restoreAllMocks();
});

describe('FinalsSeries', () => {
	it('draws one tab per game with the number, winner, score and OT', () => {
		show();
		expect(tabs().map((t) => t.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			'G1 QXA 112–104',
			'G2 QXA 107–98',
			'G3 QXA 110–101',
			'G4 QYA 102–99 OT',
			'G5 QXA 106–94'
		]);
	});

	it('marks the winner in accent only when the champion won the game', () => {
		const { container } = show();
		expect(
			[...container.querySelectorAll('.winner')].map((w) => w.classList.contains('champion'))
		).toEqual([true, true, true, false, true]);
	});

	it('presses the first tab and selects another game on click', async () => {
		show();
		expect(tabs().map((t) => t.getAttribute('aria-pressed'))).toEqual([
			'true',
			'false',
			'false',
			'false',
			'false'
		]);
		expect(screen.getByText('QYA 104 – 112 QXA')).toBeTruthy();
		await fireEvent.click(tabs()[3]!);
		expect(tabs()[3]?.getAttribute('aria-pressed')).toBe('true');
		expect(screen.getByText('QXA 99 – 102 QYA')).toBeTruthy();
	});

	it('shows Highlights not available without a video, with the chart, leaders and link', () => {
		const { container } = show();
		expect(screen.getByText('Highlights not available')).toBeTruthy();
		expect(container.querySelector('svg[role="img"]')).not.toBeNull();
		expect(screen.getByText('Aaron Away1')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Game page →' }).getAttribute('href')).toBe(
			'/game/g101'
		);
	});

	it('shows the highlight thumbnail, then the player after a click', async () => {
		const { container } = show();
		await fireEvent.click(tabs()[2]!);
		expect(screen.queryByText('Highlights not available')).toBeNull();
		expect(container.querySelector('iframe')).toBeNull();
		expect(container.querySelector('.thumb img')?.getAttribute('src')).toBe(
			'https://video.example.com/t/3.jpg'
		);
		await fireEvent.click(container.querySelector('.thumb')!);
		const frame = container.querySelector('iframe');
		expect(frame?.getAttribute('src')).toContain('https://video.example.com/embed/3');
		expect(frame?.getAttribute('title')).toBe('Example highlights G3');
	});

	it('draws no chart without a curve while the score, the leaders and the link stay', async () => {
		const { container } = show();
		await fireEvent.click(tabs()[1]!);
		expect(container.querySelector('svg[role="img"]')).toBeNull();
		expect(screen.getByText('QYA 98 – 107 QXA')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Game page →' })).toBeTruthy();
		expect(container.querySelector('.leaders')).not.toBeNull();
	});

	it('draws no leaders for a game without them', async () => {
		const { container } = show();
		await fireEvent.click(tabs()[4]!);
		expect(container.querySelector('.leaders')).toBeNull();
	});

	it('draws no game link when the game is not linked', () => {
		show((f) => (f.games[0]!.game.detailAvailable = false));
		expect(screen.queryByRole('link', { name: 'Game page →' })).toBeNull();
	});

	it('gives the tabs the mobile class on a phone', () => {
		const finals = read<PlayoffsFinalsFeed>('playoffs-finals.json');
		const games = toPlayoffsView(read<PlayoffsFeed>('playoffs-complete.json'), finals).series;
		const { container } = render(FinalsSeries, {
			props: { games, layout: 'mobile' as const, teamHref, gameHref }
		});
		expect(container.querySelector('.finals-series')?.classList.contains('mobile')).toBe(true);
	});
});

describe('FinalsSeries bound selection', () => {
	it('shows the game the parent selects and reports a tab click back to it', async () => {
		const finals = read<PlayoffsFinalsFeed>('playoffs-finals.json');
		const games = toPlayoffsView(read<PlayoffsFeed>('playoffs-complete.json'), finals).series;
		let selected = 2;
		render(FinalsSeries, {
			props: {
				games,
				layout: 'desktop' as const,
				teamHref,
				gameHref,
				get selected() {
					return selected;
				},
				set selected(value: number) {
					selected = value;
				}
			}
		});
		expect(tabs()[2]?.getAttribute('aria-pressed')).toBe('true');
		await fireEvent.click(tabs()[4]!);
		expect(selected).toBe(4);
	});
});
