// web/tests/lib/components/PlayInStrip.test.ts
//
// Tests for the PlayInStrip component.
//
// Tested:
// - The Play-in H3 above two conference columns (a label, not a heading) of three game cards each
// - To be decided with the regular season place and the Currently line before play
// - Codes, points and the loser row after a game; the seed note in the accent class and the out note muted
// - The date and time before a game
// - A game link only when the game is linked
// - Collapsed: titles and notes only
// - Spanish notes
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
import { preferLanguages } from '../../prefer-languages';

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
	it('draws the Play-in heading above two conference columns of three games each', () => {
		const { container } = show('playoffs-picture.json');
		expect(screen.getAllByRole('heading').map((h) => [h.tagName, h.textContent])).toEqual([
			['H3', 'Play-in']
		]);
		expect(
			[...container.querySelectorAll('.conference > .label')].map((l) => l.textContent)
		).toEqual(['East', 'West']);
		expect(container.querySelectorAll('.conference')).toHaveLength(2);
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

	it('draws the codes and points after a game, with the loser row marked', () => {
		const { container } = show('playoffs-playin.json');
		const games = [...container.querySelectorAll('.game')];
		expect([...games[0]!.querySelectorAll('.slot-name')].map((n) => n.textContent)).toEqual([
			'QXG',
			'QXH'
		]);
		expect([...games[0]!.querySelectorAll('.score')].map((s) => s.textContent)).toEqual([
			'108',
			'101'
		]);
		expect(
			[...games[0]!.querySelectorAll('.slot')].map((s) => s.classList.contains('loser'))
		).toEqual([false, true]);
		expect(games[2]!.querySelector('.slot.loser')).toBeNull();
	});

	it('marks a seed note in the accent class and an out note as muted', () => {
		const { container } = show('playoffs-playin.json');
		const games = [...container.querySelectorAll('.game')];
		const seed = games[0]!.querySelector('.note')!;
		expect(seed.textContent).toBe('QXG → No. 7');
		expect(seed.classList.contains('seed')).toBe(true);
		const out = games[1]!.querySelector('.note')!;
		expect(out.textContent).toBe('QXI out');
		expect(out.classList.contains('seed')).toBe(false);
	});

	it('draws the date and time of a game that is not final, and no score', () => {
		const { container } = show('playoffs-playin.json');
		const game = container.querySelectorAll('.game')[2]!;
		expect(game.querySelector('.when')?.textContent).toMatch(/^Apr 17 · /);
		expect(game.querySelector('.score')).toBeNull();
	});

	it('links a game only when it is linked', () => {
		show('playoffs-playin.json', false, (f) => {
			f.playIn![0].games[0].game!.detailAvailable = true;
		});
		const links = screen.getAllByRole('link', { name: 'Game page →' });
		expect(links).toHaveLength(1);
		expect(links[0]?.getAttribute('href')).toBe('/game/g1');
	});

	it('collapses to the titles and the notes', () => {
		const { container } = show('playoffs-playin.json', true, (f) => {
			f.playIn![0].games[0].game!.detailAvailable = true;
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

	it('writes the notes and the heading in Spanish', () => {
		preferLanguages(['es-ES']);
		const { container } = show('playoffs-playin.json');
		expect(screen.getByRole('heading', { level: 3 }).textContent).toBe('Play-in');
		expect(
			[...container.querySelectorAll('.conference > .label')].map((l) => l.textContent)
		).toEqual(['Este', 'Oeste']);
		expect(container.querySelector('.note')?.textContent).toMatch(/^QXG → /);
	});
});
