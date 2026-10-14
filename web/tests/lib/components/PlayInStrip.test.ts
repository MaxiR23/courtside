// web/tests/lib/components/PlayInStrip.test.ts
//
// Tests for the PlayInStrip component.
//
// Tested:
// - One card per conference with three games each
// - To be decided with the regular season place and the Currently line before play
// - Scores and outcomes after a game; the date and time before it
// - A game link only when the game is linked
// - Collapsed: titles and outcome lines only
//
// What is covered:
// - Each state a game can show, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayInStrip.test.ts
//
// SEE: web/src/lib/components/PlayInStrip.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import PlayInStrip from '../../../src/lib/components/PlayInStrip.svelte';

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const feed = (file: string) =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', file), 'utf8')) as PlayoffsFeed;
const show = (file: string, collapsed = false, change: (f: PlayoffsFeed) => void = () => {}) => {
	const source = feed(file);
	change(source);
	return render(PlayInStrip, {
		props: {
			playIn: toPlayoffsView(source, null).playIn,
			collapsed,
			layout: 'desktop' as const,
			teamHref,
			gameHref
		}
	});
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('PlayInStrip', () => {
	it('draws one card per conference with three games each', () => {
		const { container } = show('playoffs-picture.json');
		expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
			'East · Play-In',
			'West · Play-In'
		]);
		expect(container.querySelectorAll('.game')).toHaveLength(6);
		expect(
			[...container.querySelectorAll('.game-title')].slice(0, 3).map((t) => t.textContent)
		).toEqual(['7th vs 8th', '9th vs 10th', '8th seed game']);
	});

	it('draws To be decided with the place and the Currently line before play', () => {
		const { container } = show('playoffs-picture.json');
		const first = container.querySelector('.game')!;
		const text = first.textContent ?? '';
		expect(text).toContain('To be decided');
		expect(text).toContain('7th');
		expect(text).toContain('Currently QXG');
		expect(container.querySelectorAll('.game')[2]?.textContent).toContain('Loser of 7th vs 8th');
		expect(container.querySelectorAll('.game')[2]?.textContent).toContain('Winner of 9th vs 10th');
	});

	it('draws scores and outcomes after a game, and the date and time before it', () => {
		const { container } = show('playoffs-playin.json');
		const games = [...container.querySelectorAll('.game')];
		expect([...games[0]!.querySelectorAll('.score')].map((s) => s.textContent)).toEqual([
			'108',
			'101'
		]);
		expect(games[0]!.querySelector('.outcome')?.textContent).toBe('QXG → No. 7');
		expect(games[1]!.querySelector('.outcome')?.textContent).toBe('QXI out');
		expect(games[2]!.querySelector('.when')?.textContent).toMatch(/^Apr 17 · /);
		expect(games[2]!.querySelector('.score')).toBeNull();
	});

	it('links a game only when it is linked', () => {
		show('playoffs-playin.json', false, (f) => {
			f.playIn[0].games[0].game!.detailAvailable = true;
		});
		const links = screen.getAllByRole('link', { name: 'Game page →' });
		expect(links).toHaveLength(1);
		expect(links[0]?.getAttribute('href')).toBe('/game/g1');
	});

	it('collapses to the titles and the outcome lines', () => {
		const { container } = show('playoffs-playin.json', true, (f) => {
			f.playIn[0].games[0].game!.detailAvailable = true;
		});
		const games = [...container.querySelectorAll('.game')];
		expect(games[0]!.classList.contains('collapsed')).toBe(true);
		expect(games[0]!.querySelector('.slot')).toBeNull();
		expect(games[0]!.querySelector('.score')).toBeNull();
		expect(games[0]!.querySelector('.when')).toBeNull();
		expect(games[0]!.querySelector('a')).toBeNull();
		expect(games[0]!.textContent).toContain('7th vs 8th');
		expect(games[0]!.textContent).toContain('QXG → No. 7');
	});
});
