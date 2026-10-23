// web/tests/lib/components/SeriesPage.test.ts
//
// Tests for the SeriesPage component.
//
// Tested:
// - Ready: the nav row, the back link, the kicker, the h1 round label, both codes, seeds and scores
// - The losing side of a complete series is dimmed; the trailing score is muted
// - The glows, bars and rules carry the feed's accent, or the neutral accent for a null one
// - The status and dates lines, absent when the view has none
// - The game cards: one per game, a link and a chevron only when linked, the OT tag, the leader line, the rule
// - The team logo when the side has one, and the code tile when it has none
// - Loading is aria-busy; unavailable and not-found draw their message; the footer in every state
// - Spanish copy
//
// What is covered:
// - Each state the page shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SeriesPage.test.ts
//
// SEE: web/src/lib/components/SeriesPage.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../../../src/lib/contract/playoffs-finals';
import { toSeriesPageView } from '../../../src/lib/feed/playoffs-props';
import type { SeriesPageState, SeriesPageView } from '../../../src/lib/playoffs/types';
import { preferLanguages } from '../../prefer-languages';
import SeriesPage from '../../../src/lib/components/SeriesPage.svelte';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const BRACKET = '/playoffs#bracket' as ResolvedPathname;
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const UNAVAILABLE = "Data isn't available right now. Check back later.";

const read = <T>(file: string): T =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', file), 'utf8')) as T;

const viewOf = (
	id: string,
	change: (f: PlayoffsFeed) => void = () => {},
	finals: PlayoffsFinalsFeed | null = null
): SeriesPageView => {
	const feed = read<PlayoffsFeed>('playoffs-bracket.json');
	change(feed);
	return toSeriesPageView(feed, finals, id)!;
};

const ready = (view: SeriesPageView = viewOf('east-r1-1')): SeriesPageState => ({
	kind: 'ready',
	view
});

const show = (state: SeriesPageState) =>
	render(SeriesPage, {
		props: {
			state,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout: 'desktop' as const,
			bracketHref: BRACKET,
			gameHref
		}
	});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
});

describe('SeriesPage ready', () => {
	it('draws the nav row, the back link, the kicker and the round label', async () => {
		show(ready());
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		expect(screen.getByRole('link', { name: 'Playoffs' }).getAttribute('aria-current')).toBe(
			'page'
		);
		expect(screen.getByRole('link', { name: '← Bracket' }).getAttribute('href')).toBe(BRACKET);
		expect(screen.getByText('2027 NBA Playoffs')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('East · Round 1');
	});

	it('draws both codes, the seed lines and the scores', () => {
		const { container } = show(ready());
		expect([...container.querySelectorAll('.side .code')].map((e) => e.textContent)).toEqual([
			'QXA',
			'QXH'
		]);
		expect(screen.getByText('No. 1 seed')).toBeTruthy();
		expect(screen.getByText('No. 8 seed')).toBeTruthy();
		expect([...container.querySelectorAll('.scores .wins')].map((e) => e.textContent)).toEqual([
			'4',
			'1'
		]);
	});

	it('dims the losing side of a complete series and mutes the trailing score', () => {
		const { container } = show(ready());
		const sides = container.querySelectorAll('.side');
		expect(sides[0].classList.contains('loser')).toBe(false);
		expect(sides[1].classList.contains('loser')).toBe(true);
		const wins = container.querySelectorAll('.scores .wins');
		expect(wins[0].classList.contains('muted')).toBe(false);
		expect(wins[1].classList.contains('muted')).toBe(true);
	});

	it('dims nobody while the series is in progress', () => {
		const { container } = show(ready(viewOf('east-r1-2')));
		expect(container.querySelector('.side.loser')).toBeNull();
		expect(container.querySelector('.scores .muted')).toBeNull();
	});

	it("carries the feed's accent on the glows and bars, and the neutral accent for a null one", () => {
		const { container } = show(
			ready(
				viewOf('east-r1-1', (f) => {
					f.bracket.find((s) => s.id === 'east-r1-1')!.accent = { top: '#112233', bottom: null };
				})
			)
		);
		const glows = container.querySelectorAll<HTMLElement>('.glow');
		expect(glows[0].style.getPropertyValue('--side-accent')).toBe('#112233');
		expect(glows[1].style.getPropertyValue('--side-accent')).toBe('var(--identity-neutral-accent)');
		const sides = container.querySelectorAll<HTMLElement>('.side');
		expect(sides[0].style.getPropertyValue('--side-accent')).toBe('#112233');
		expect(sides[1].style.getPropertyValue('--side-accent')).toBe('var(--identity-neutral-accent)');
	});

	it('draws the status and the dates, and neither when the view has none', () => {
		const first = show(ready());
		expect(screen.getByText('QXA wins the series 4–1')).toBeTruthy();
		expect(screen.getByText('Apr 19 – Apr 28')).toBeTruthy();
		first.unmount();
		const view = viewOf('east-r1-1');
		view.status = null;
		view.dates = null;
		const { container } = show(ready(view));
		expect(container.querySelector('.status')).toBeNull();
		expect(container.querySelector('.dates')).toBeNull();
	});

	it('draws no seed line for a side without one', () => {
		const view = viewOf('east-r1-1');
		view.top.seed = null;
		const { container } = show(ready(view));
		expect(container.querySelectorAll('.seed')).toHaveLength(1);
	});

	it('draws a logo when the side has one, and the code tile when it has none', () => {
		const view = viewOf('east-r1-1');
		view.top.team.logo = { light: 'https://example.com/a-light.svg', dark: null };
		const { container } = show(ready(view));
		const sides = container.querySelectorAll('.side');
		expect(sides[0].querySelector('.logo img')).toBeTruthy();
		expect(sides[1].querySelector('.logo img')).toBeNull();
		expect(sides[1].querySelector('.logo .team-monogram')).toBeTruthy();
	});
});

describe('SeriesPage game cards', () => {
	it('draws "Game by game" as an h3 with one item per game', () => {
		const { container } = show(ready());
		expect(screen.getByRole('heading', { level: 3 }).textContent).toBe('Game by game');
		expect(container.querySelectorAll('ol > li')).toHaveLength(5);
	});

	it('links a card with a detail page and draws its chevron; an unlinked card has neither', () => {
		const first = show(ready());
		const cards = document.querySelectorAll('ol .card');
		expect(cards[0].tagName).toBe('A');
		expect(cards[0].getAttribute('href')).toBe('/game/b101');
		expect(cards[0].querySelector('svg.chevron')).toBeTruthy();
		first.unmount();
		const { container } = show(ready(viewOf('east-r1-3')));
		const card = container.querySelector('ol .card')!;
		expect(card.tagName).toBe('DIV');
		expect(card.querySelector('svg')).toBeNull();
	});

	it('draws the title, the meta, the codes and the scores of a card', () => {
		const { container } = show(ready());
		const card = container.querySelector('ol .card')!;
		expect(card.querySelector('.title')?.textContent).toBe('Game 1');
		expect(card.querySelector('.meta')?.textContent).toBe('Apr 19 · Example Arena');
		expect([...card.querySelectorAll('.game-code')].map((e) => e.textContent)).toEqual([
			'QXA',
			'QXH'
		]);
		expect([...card.querySelectorAll('.points')].map((e) => e.textContent)).toEqual(['105', '98']);
		const sides = card.querySelectorAll('.game-side');
		expect(sides[0].classList.contains('loser')).toBe(false);
		expect(sides[1].classList.contains('loser')).toBe(true);
	});

	it('draws the OT tag on the overtime game only', () => {
		const { container } = show(ready());
		const tags = [...container.querySelectorAll('ol .card')].map(
			(c) => c.querySelector('.ot')?.textContent ?? null
		);
		expect(tags).toEqual([null, null, 'OT', null, null]);
	});

	it('draws the leader line on Finals cards and none on a round 1 card', () => {
		const feed = read<PlayoffsFeed>('playoffs-complete.json');
		const finals = read<PlayoffsFinalsFeed>('playoffs-finals.json');
		const view = toSeriesPageView(feed, finals, 'finals')!;
		const first = show(ready(view));
		expect(first.container.querySelector('.leaders')?.textContent).toBe(
			'Bea Home1 27 PTS · Aaron Away1 25 PTS'
		);
		first.unmount();
		const { container } = show(ready());
		expect(container.querySelector('.leaders')).toBeNull();
	});

	it("draws the winner's rule with the accent, and none for a game with no winner", () => {
		const view = viewOf('east-r1-1', (f) => {
			f.bracket.find((s) => s.id === 'east-r1-1')!.accent = { top: '#112233', bottom: '#445566' };
		});
		const first = show(ready(view));
		const rule = first.container.querySelector<HTMLElement>('ol .card .rule')!;
		expect(rule.style.getPropertyValue('--side-accent')).toBe('#112233');
		first.unmount();
		const { container } = show(ready(viewOf('east-r1-3')));
		expect(container.querySelector('.rule')).toBeNull();
	});
});

describe('SeriesPage other states', () => {
	it('loading: the skeleton is aria-busy, with the back link and the footer', () => {
		const { container } = show({ kind: 'loading' });
		expect(container.querySelector('.skeleton')?.getAttribute('aria-busy')).toBe('true');
		expect(screen.getByRole('link', { name: '← Bracket' })).toBeTruthy();
		expect(container.querySelector('footer')).toBeTruthy();
	});

	it('unavailable: the message, no kicker, and the footer', () => {
		const { container } = show({ kind: 'unavailable' });
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(container.querySelector('.kicker')).toBeNull();
		expect(container.querySelector('footer')).toBeTruthy();
	});

	it('not-found: the message and a link back to the bracket', () => {
		const { container } = show({ kind: 'not-found' });
		expect(screen.getByText("This series isn't available.")).toBeTruthy();
		const links = screen.getAllByRole('link', { name: '← Bracket' });
		expect(links.length).toBeGreaterThanOrEqual(1);
		expect(links.every((l) => l.getAttribute('href') === BRACKET)).toBe(true);
		expect(container.querySelector('footer')).toBeTruthy();
	});

	it('ready: the footer is there', () => {
		const { container } = show(ready());
		expect(container.querySelector('footer')).toBeTruthy();
	});

	it('draws the Spanish copy', () => {
		preferLanguages(['es-ES']);
		const first = show(ready());
		expect(screen.getByText('Partido a partido')).toBeTruthy();
		expect(screen.getByRole('link', { name: '← Cuadro' })).toBeTruthy();
		first.unmount();
		show({ kind: 'not-found' });
		expect(screen.getByText('Esta serie no está disponible.')).toBeTruthy();
	});
});
