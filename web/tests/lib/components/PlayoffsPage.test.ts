// web/tests/lib/components/PlayoffsPage.test.ts
//
// Tests for the PlayoffsPage component.
//
// Tested:
// - Ready: each of the five states draws its sections in the design's order
// - The bracket is in every state with its 15 series
// - A click on a game in the Finals card selects that game in the series section and scrolls to it
// - Without the finals feed only the four finals sections go
// - Loading: the header and the skeleton are aria-busy
// - Unavailable: the unavailable row under the nav; the footer in every state
// - Spanish copy
//
// What is covered:
// - Each state the page shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayoffsPage.test.ts
//
// SEE: web/src/lib/components/PlayoffsPage.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed, PlayoffsState } from '../../../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../../../src/lib/contract/playoffs-finals';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import type { PlayoffsPageState } from '../../../src/lib/playoffs/types';
import { preferLanguages } from '../../prefer-languages';
import PlayoffsPage from '../../../src/lib/components/PlayoffsPage.svelte';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const UNAVAILABLE = "Data isn't available right now. Check back later.";

const read = <T>(file: string): T =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', file), 'utf8')) as T;

const ready = (
	state: PlayoffsState,
	withFinals = true,
	change: (f: PlayoffsFeed) => void = () => {}
): PlayoffsPageState => {
	const source = read<PlayoffsFeed>(
		state === 'picture' ? 'playoffs-picture.json' : 'playoffs-complete.json'
	);
	source.state = state;
	if (state !== 'complete') source.champion = null;
	change(source);
	const finals = withFinals ? read<PlayoffsFinalsFeed>('playoffs-finals.json') : null;
	return { kind: 'ready', view: toPlayoffsView(source, finals) };
};

const show = (state: PlayoffsPageState) =>
	render(PlayoffsPage, {
		props: {
			state,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout: 'desktop' as const,
			teamHref,
			gameHref
		}
	});
const ids = (container: HTMLElement) =>
	[...container.querySelectorAll('.sections > section')].map((s) => s.id);

beforeEach(() => {
	vi.stubGlobal(
		'matchMedia',
		vi.fn(() => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} }))
	);
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
});

describe('PlayoffsPage', () => {
	it('ready: draws the sections of the picture state', () => {
		const { container } = show(ready('picture'));
		expect(ids(container)).toEqual(['picture', 'bracket', 'play-in', 'leaders', 'awards']);
		expect(container.querySelectorAll('.table-block')).toHaveLength(2);
		expect(screen.getAllByRole('table')).toHaveLength(2);
		expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
			'East',
			'West',
			'Bracket',
			'Play-In',
			'Leaders',
			'Awards'
		]);
	});

	it('ready: draws the bracket first in the play-in and playoffs states', () => {
		for (const state of ['playin', 'playoffs'] as const) {
			const { container, unmount } = show(ready(state, false));
			expect(ids(container)).toEqual(['bracket', 'play-in', 'leaders', 'awards']);
			unmount();
		}
	});

	it('ready: draws the hype sections before the leaders in the finals state', () => {
		const { container } = show(ready('finals'));
		expect(ids(container)).toEqual([
			'bracket',
			'play-in',
			'finals-mvp',
			'series',
			'road',
			'head-to-head',
			'leaders',
			'awards'
		]);
	});

	it('ready: draws the complete state with the hero and the hype sections first', () => {
		const { container } = show(ready('complete'));
		expect(ids(container)).toEqual([
			'finals-mvp',
			'series',
			'road',
			'head-to-head',
			'leaders',
			'bracket',
			'play-in',
			'awards'
		]);
		expect(screen.getByRole('heading', { level: 1, name: 'Champions' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Relive the series' })).toBeTruthy();
	});

	it('ready: the bracket is in every state with its 15 series', () => {
		for (const state of ['picture', 'playin', 'playoffs', 'finals', 'complete'] as const) {
			const { container, unmount } = show(ready(state, state === 'finals' || state === 'complete'));
			const section = container.querySelector('#bracket');
			expect(section?.querySelector('h2')?.textContent).toBe('Bracket');
			expect(section?.querySelectorAll('.series')).toHaveLength(15);
			expect(section?.querySelector('.bracket-placeholder')).toBeNull();
			unmount();
		}
	});

	it('ready: a click on a Finals game in the bracket selects it in the series section', async () => {
		const scrollIntoView = vi.fn();
		Element.prototype.scrollIntoView = scrollIntoView;
		const { container } = show(ready('complete'));
		const tabs = () => [...container.querySelectorAll('#series .tab')];
		expect(tabs()[0]?.getAttribute('aria-pressed')).toBe('true');
		await fireEvent.click(
			container.querySelector('#bracket .series.champion, #bracket .series:nth-child(1)')!
		);
		await fireEvent.click(screen.getByRole('button', { name: /NBA Finals/ }));
		const rows = [...container.querySelectorAll('#bracket .games .game-button')];
		expect(rows).toHaveLength(5);
		await fireEvent.click(rows[3]);
		expect(tabs()[3]?.getAttribute('aria-pressed')).toBe('true');
		expect(tabs()[0]?.getAttribute('aria-pressed')).toBe('false');
		expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto', block: 'start' });
		delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView;
	});

	it('ready: collapses the play-in after round 1 starts', () => {
		const picture = show(ready('picture'));
		expect(picture.container.querySelectorAll('.game.collapsed')).toHaveLength(0);
		picture.unmount();
		const playoffs = show(ready('playoffs', false));
		expect(playoffs.container.querySelectorAll('.game.collapsed')).toHaveLength(6);
	});

	it('ready: without the finals feed only the four finals sections go and the hero stays', () => {
		const { container } = show(ready('complete', false));
		expect(ids(container)).toEqual(['leaders', 'bracket', 'play-in', 'awards']);
		expect(screen.getByRole('heading', { level: 1, name: 'Champions' })).toBeTruthy();
		expect(screen.queryByRole('button', { name: 'Relive the series' })).toBeNull();
		expect(screen.getByRole('button', { name: 'Full bracket' })).toBeTruthy();
	});

	it('loading: the header and the skeleton are aria-busy', () => {
		const { container } = show({ kind: 'loading' });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.table-skeleton')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('footer')).not.toBeNull();
	});

	it('unavailable: the unavailable row under the nav and the footer', () => {
		const { container } = show({ kind: 'unavailable' });
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Playoffs' }).getAttribute('aria-current')).toBe(
			'page'
		);
		expect(container.querySelector('.stage-strip')).toBeNull();
		expect(container.querySelector('footer')).not.toBeNull();
	});

	it('shows Spanish copy', () => {
		preferLanguages(['es-ES']);
		show(ready('picture'));
		expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
			'Este',
			'Oeste',
			'Cuadro',
			'Play-In',
			'Líderes',
			'Premios'
		]);
	});
});
