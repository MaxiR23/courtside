// web/tests/lib/components/PlayoffsPage.test.ts
//
// Tests for the PlayoffsPage component.
//
// Tested:
// - Ready: each of the five states draws its sections in the design's order
// - The bracket is in every state with its 15 series
// - The complete state selects the Finals in the bracket and shows its result panel; the play-in heading is an H3
// - Without the finals feed only the four finals sections go
// - Loading: the header and the skeleton are aria-busy
// - The unavailable state of a past season keeps the Season tag; the current season's has none (ADR 0054)
// - Unavailable: the unavailable row under the nav; the footer in every state
// - Spanish copy
// - The Finals MVP section: the Finals card and both conference cards, and each missing winner hides only its card
// - The Finals MVP columns: the mobile class from mvpLayout, and the 2-column and 1-column rules in the stylesheet
// - The team logos: the champion logo in the hero, a playoff picture row's logo, the code for a null logo
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
const seriesHref = (id: string) => `/playoffs/series?id=${id}` as ResolvedPathname;
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

const show = (state: PlayoffsPageState, mvpLayout: 'desktop' | 'mobile' = 'desktop') =>
	render(PlayoffsPage, {
		props: {
			state,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout: 'desktop' as const,
			bracketLayout: 'desktop' as const,
			mvpLayout,
			teamHref,
			gameHref,
			seriesHref,
			openSeries: vi.fn()
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
		expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Harbor');
		expect(container.querySelector('a.strip[href="#series"]')).not.toBeNull();
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

	it('ready: the complete state selects the Finals in the bracket and shows its result', () => {
		const { container } = show(ready('complete'));
		const section = container.querySelector('#bracket')!;
		expect(section.querySelectorAll('.series.selected')).toHaveLength(1);
		expect(section.querySelector('section.result .headline')?.textContent).toBe('QXA wins 4–1');
		expect(container.querySelectorAll('#series .tab')[0]?.getAttribute('aria-pressed')).toBe(
			'true'
		);
	});

	it('ready: the play-in has an H3 and no section heading', () => {
		const { container } = show(ready('picture'));
		expect(
			[...container.querySelectorAll('#play-in h2, #play-in h3')].map(
				(h) => h.tagName + h.textContent
			)
		).toEqual(['H3Play-in']);
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
		expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Harbor');
		expect(container.querySelector('a.strip')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Full bracket' })).toBeNull();
	});

	it('loading: the header and the skeleton are aria-busy', () => {
		const { container } = show({ kind: 'loading' });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.table-skeleton')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('footer')).not.toBeNull();
	});

	it('keeps the Season tag on the unavailable state of a past season, and has none on the current one', () => {
		const props = {
			state: { kind: 'unavailable' } as PlayoffsPageState,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout: 'desktop' as const,
			bracketLayout: 'desktop' as const,
			mvpLayout: 'desktop' as const,
			teamHref,
			gameHref,
			seriesHref,
			openSeries: vi.fn()
		};
		const { unmount } = render(PlayoffsPage, { props: { ...props, seasonTag: 'Season 2022-23' } });
		expect(screen.getByText('Season 2022-23')).toBeTruthy();
		unmount();
		render(PlayoffsPage, { props });
		expect(screen.queryByText(/^Season /)).toBeNull();
	});

	it('unavailable: the unavailable row under the nav and the footer', async () => {
		const { container } = show({ kind: 'unavailable' });
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
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
			'Líderes',
			'Premios'
		]);
	});
});

describe('PlayoffsPage team logos', () => {
	const logo = {
		light: 'https://example.com/a-light.svg',
		dark: 'https://example.com/a-dark.svg'
	};

	it('draws the champion logo in the champion hero, and the code for a null logo', () => {
		const state = ready('complete');
		if (state.kind !== 'ready') throw new Error('not ready');
		state.view.header.hero!.team.logo = logo;
		const { container } = show(state);
		const box = container.querySelector('.band .logo .team-monogram');
		expect(box?.querySelector('img')?.getAttribute('src')).toBe('https://example.com/a-dark.svg');
		const plain = show(ready('complete')).container.querySelectorAll('.band .logo .team-monogram');
		expect(plain[plain.length - 1]!.querySelector('img')).toBeNull();
	});

	it('draws the logo of a row of the playoff picture', () => {
		const state = ready('picture');
		if (state.kind !== 'ready') throw new Error('not ready');
		state.view.picture[0]!.rows[0]!.team.logo = logo;
		const { container } = show(state);
		const boxes = [...container.querySelectorAll('.row.body .team-monogram.standings')];
		expect(boxes[0]!.querySelector('img')?.getAttribute('src')).toBe(
			'https://example.com/a-dark.svg'
		);
		expect(boxes[1]!.querySelector('img')).toBeNull();
	});
});

describe('PlayoffsPage Finals MVP section', () => {
	const section = (
		change: (f: PlayoffsFeed, finals: PlayoffsFinalsFeed) => void = () => {}
	): HTMLElement => {
		const feed = read<PlayoffsFeed>('playoffs-complete.json');
		const finals = read<PlayoffsFinalsFeed>('playoffs-finals.json');
		change(feed, finals);
		const { container } = show({ kind: 'ready', view: toPlayoffsView(feed, finals) });
		return container.querySelector<HTMLElement>('#finals-mvp') ?? document.createElement('div');
	};
	const without = (feed: PlayoffsFeed, ...codes: string[]) => {
		feed.awards = feed.awards!.filter((a) => !codes.includes(a.code));
	};

	it('draws the Finals MVP card and both conference cards with all three winners', () => {
		const el = section();
		expect(el.querySelectorAll('.finals-mvp')).toHaveLength(1);
		expect(el.querySelectorAll('.conference-slot')).toHaveLength(2);
		const h2 = el.querySelector('h2');
		expect(h2?.textContent).toBe('Finals MVP');
		expect(h2?.classList.contains('mvp')).toBe(true);
	});

	it('draws two columns at 900px and wider and one below', () => {
		const feed = read<PlayoffsFeed>('playoffs-complete.json');
		const finals = read<PlayoffsFinalsFeed>('playoffs-finals.json');
		const state: PlayoffsPageState = { kind: 'ready', view: toPlayoffsView(feed, finals) };
		const wide = show(state, 'desktop');
		expect(wide.container.querySelector('#finals-mvp .mvps')?.classList.contains('mobile')).toBe(
			false
		);
		wide.unmount();
		const narrow = show(state, 'mobile');
		expect(narrow.container.querySelector('#finals-mvp .mvps')?.classList.contains('mobile')).toBe(
			true
		);
	});

	it('takes its columns from the MVP breakpoint rule', () => {
		const style =
			readFileSync(
				join(__dirname, '..', '..', '..', 'src/lib/components/PlayoffsPage.svelte'),
				'utf8'
			)
				.match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1]!
				.replace(/\/\*[\s\S]*?\*\//g, '') ?? '';
		const columns = (selector: string): string | undefined => {
			for (const m of style.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
				if (m[1]!.trim() !== selector) continue;
				const found = m[2]!.match(/grid-template-columns:\s*([^;]+);/);
				if (found) return found[1]!.trim();
			}
			return undefined;
		};
		expect(style.length).toBeGreaterThan(0);
		expect(columns('.mvps')).toBe('repeat(2, minmax(0, 1fr))');
		expect(columns('.mvps.mobile')).toBe('minmax(0, 1fr)');
		expect(style).not.toContain('--playoffs-mvp-column-min');
	});

	it('hides only the Finals MVP card with no Finals MVP', () => {
		const el = section((_, finals) => (finals.finalsMvp = null));
		expect(el.querySelector('.finals-mvp')).toBeNull();
		expect(el.querySelectorAll('.conference-slot')).toHaveLength(2);
	});

	it('hides only the East card with no East finals MVP', () => {
		const el = section((f) => without(f, 'east_finals_mvp'));
		expect(el.querySelectorAll('.conference-slot')).toHaveLength(1);
		expect(el.textContent).toContain('West Finals MVP');
		expect(el.textContent).not.toContain('East Finals MVP');
		expect(el.querySelector('.finals-mvp')).not.toBeNull();
	});

	it('hides only the West card with no West finals MVP', () => {
		const el = section((f) => without(f, 'west_finals_mvp'));
		expect(el.querySelectorAll('.conference-slot')).toHaveLength(1);
		expect(el.textContent).toContain('East Finals MVP');
		expect(el.textContent).not.toContain('West Finals MVP');
		expect(el.querySelector('.finals-mvp')).not.toBeNull();
	});

	it('hides the conference column with neither conference MVP', () => {
		const el = section((f) => without(f, 'east_finals_mvp', 'west_finals_mvp'));
		expect(el.querySelector('.conference-mvps')).toBeNull();
		expect(el.querySelector('.finals-mvp')).not.toBeNull();
	});

	it('hides the section with no winner at all', () => {
		const feed = read<PlayoffsFeed>('playoffs-complete.json');
		const finals = read<PlayoffsFinalsFeed>('playoffs-finals.json');
		finals.finalsMvp = null;
		without(feed, 'east_finals_mvp', 'west_finals_mvp');
		const { container } = show({ kind: 'ready', view: toPlayoffsView(feed, finals) });
		expect(container.querySelector('#finals-mvp')).toBeNull();
	});
});
