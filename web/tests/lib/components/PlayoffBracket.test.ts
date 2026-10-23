// web/tests/lib/components/PlayoffBracket.test.ts
//
// Tests for the PlayoffBracket component.
//
// Tested:
// - The header: the kicker, the H2 and the helper text
// - Desktop: 15 series in 7 titled columns, in every state's fixture; no zoom controls and no transform
// - Mobile: 15 series in 7 titled rows, each card at the grid-column of its span
// - Selection: nothing selected and no result panel while the Finals has no game; the Finals selected by default once it has one
// - A tap selects a series and moves the panel; a second tap on an unfinished series keeps it selected
// - A second tap on a complete series opens its full series page
// - An undecided series is not a button and a click on it changes nothing
// - The result panel: the headline, one cell per game, a game link only when the game is linked, and the Full series link
// - Mobile: a first tap opens the sheet, Close and Esc return the focus to the card, a second tap on a complete series opens its page
//
// What is covered:
// - The component with its real selection, no network and no layout (jsdom measures nothing)
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayoffBracket.test.ts
//
// SEE: web/src/lib/components/PlayoffBracket.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import PlayoffBracket from '../../../src/lib/components/PlayoffBracket.svelte';
import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import { BRACKET_GROUPS, treeSpan } from '../../../src/lib/playoffs/bracket-grid';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const seriesHref = (id: string) => `/playoffs/series?id=${id}` as ResolvedPathname;

const FIXTURES = [
	'playoffs-picture.json',
	'playoffs-playin.json',
	'playoffs-bracket.json',
	'playoffs-complete.json'
];

const TITLES = [
	'East R1',
	'East Semis',
	'East Finals',
	'NBA Finals',
	'West Finals',
	'West Semis',
	'West R1'
];

const bracketOf = (name = 'playoffs-bracket.json') =>
	toPlayoffsView(
		JSON.parse(
			readFileSync(join(__dirname, '..', 'feed', 'fixtures', name), 'utf8')
		) as PlayoffsFeed,
		null
	).bracket;

const show = (
	layout: 'desktop' | 'mobile' = 'desktop',
	name = 'playoffs-bracket.json',
	openSeries = vi.fn()
) =>
	render(PlayoffBracket, {
		props: { bracket: bracketOf(name), layout, gameHref, seriesHref, openSeries }
	});

const card = (name: string) => screen.getByRole('button', { name });
const finalsCard = () => screen.getByRole('button', { name: /NBA Finals/ });
const QXA_QXH = 'East · Round 1 · QXA · QXH';
const QXD_QXE = 'East · Round 1 · QXD · QXE';

afterEach(() => {
	vi.restoreAllMocks();
	document.body.style.overflow = '';
});

describe('PlayoffBracket header', () => {
	it('shows the kicker, the H2 and the helper text', () => {
		const { container } = show();
		expect(container.querySelector('.kicker')?.textContent).toBe('2027 NBA Playoffs');
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('Bracket');
		expect(container.querySelector('.help')?.textContent).toBe(
			'Tap a series for the result. Tap it again to open the full series.'
		);
	});
});

describe('PlayoffBracket map', () => {
	it('draws 15 series in 7 titled columns in every state', () => {
		for (const name of FIXTURES) {
			const { container, unmount } = show('desktop', name);
			expect(container.querySelectorAll('.series')).toHaveLength(15);
			const groups = [...container.querySelectorAll('.map > .group')];
			expect(groups.map((g) => g.querySelector('.title')?.textContent)).toEqual(TITLES);
			expect(groups.map((g) => g.querySelectorAll('.series').length)).toEqual([
				4, 2, 1, 1, 1, 2, 4
			]);
			unmount();
		}
	});

	it('is a labelled group with the Finals title in its own class', () => {
		const { container } = show();
		expect(screen.getByRole('group', { name: 'Bracket' })).toBeTruthy();
		expect(
			[...container.querySelectorAll('.title.finals')].map((title) => title.textContent)
		).toEqual(['NBA Finals']);
	});

	it('has no zoom or level controls and no transform', () => {
		const { container } = show();
		expect(container.querySelector('.controls, .viewport, .layer, svg')).toBeNull();
		expect(
			screen.queryByRole('button', { name: /Next series|Previous series|Series$/ })
		).toBeNull();
		expect(container.querySelectorAll('[style*="transform"]')).toHaveLength(0);
	});
});

describe('PlayoffBracket tree', () => {
	it('draws 15 series in 7 titled rows, each at the grid-column of its span', () => {
		const { container } = show('mobile');
		const rows = [...container.querySelectorAll('div.tree > section.row')];
		expect(rows.map((r) => r.querySelector('.label')?.textContent)).toEqual(TITLES);
		const slots = [...container.querySelectorAll<HTMLElement>('.slot')];
		expect(slots).toHaveLength(15);
		expect(slots.map((slot) => slot.style.gridColumn)).toEqual(
			BRACKET_GROUPS.flatMap((group) => group.ids).map((id) => treeSpan(id))
		);
		expect(container.querySelectorAll('.series.tree')).toHaveLength(15);
	});

	it('draws the tree in every state', () => {
		for (const name of FIXTURES) {
			const { container, unmount } = show('mobile', name);
			expect(container.querySelectorAll('.series')).toHaveLength(15);
			unmount();
		}
	});
});

describe('PlayoffBracket selection', () => {
	it('selects nothing and shows no result while the Finals has no game', () => {
		const { container } = show();
		expect(container.querySelectorAll('.series.selected')).toHaveLength(0);
		expect(container.querySelector('section.result')).toBeNull();
	});

	it('selects the Finals by default once it has a game, and shows its result', () => {
		const { container } = show('desktop', 'playoffs-complete.json');
		expect(container.querySelectorAll('.series.selected')).toHaveLength(1);
		expect(finalsCard().getAttribute('aria-pressed')).toBe('true');
		expect(container.querySelector('.result .headline')?.textContent).toBe('QXA wins 4–1');
		expect(container.querySelectorAll('.result .games .game')).toHaveLength(5);
	});

	it('moves the result to a tapped series, and keeps an unfinished one selected on a second tap', async () => {
		const openSeries = vi.fn();
		const { container } = show('desktop', 'playoffs-bracket.json', openSeries);
		await fireEvent.click(card(QXD_QXE));
		expect(card(QXD_QXE).getAttribute('aria-pressed')).toBe('true');
		expect(container.querySelector('.result .headline')?.textContent).toBe('Series tied 2–2');
		await fireEvent.click(card(QXA_QXH));
		expect(card(QXD_QXE).getAttribute('aria-pressed')).toBe('false');
		expect(container.querySelector('.result .headline')?.textContent).toBe('QXA wins 4–1');
		await fireEvent.click(card(QXD_QXE));
		await fireEvent.click(card(QXD_QXE));
		expect(card(QXD_QXE).getAttribute('aria-pressed')).toBe('true');
		expect(openSeries).not.toHaveBeenCalled();
	});

	it('opens the full series on a second tap of a complete series', async () => {
		const openSeries = vi.fn();
		show('desktop', 'playoffs-bracket.json', openSeries);
		await fireEvent.click(card(QXA_QXH));
		expect(openSeries).not.toHaveBeenCalled();
		await fireEvent.click(card(QXA_QXH));
		expect(openSeries).toHaveBeenCalledWith('east-r1-1');
	});

	it('opens the Finals on its first tap when it is complete and selected by default', async () => {
		const openSeries = vi.fn();
		show('desktop', 'playoffs-complete.json', openSeries);
		await fireEvent.click(finalsCard());
		expect(openSeries).toHaveBeenCalledWith('finals');
	});

	it('does not select an undecided series', async () => {
		const openSeries = vi.fn();
		const { container } = show('desktop', 'playoffs-bracket.json', openSeries);
		const undecided = [...container.querySelectorAll('.series')].filter(
			(node) => node.tagName !== 'BUTTON'
		);
		expect(undecided).toHaveLength(8);
		await fireEvent.click(undecided[0]);
		expect(container.querySelectorAll('.series.selected')).toHaveLength(0);
		expect(container.querySelector('section.result')).toBeNull();
		expect(openSeries).not.toHaveBeenCalled();
	});
});

describe('PlayoffBracket result panel', () => {
	it('links a game cell only when the game is linked, and Full series to the series page', async () => {
		const { container } = show();
		await fireEvent.click(card(QXD_QXE));
		expect(container.querySelectorAll('.result .games .game')).toHaveLength(5);
		expect(
			[...container.querySelectorAll('.result .games a')].map((a) => a.getAttribute('href'))
		).toEqual(['/game/b201', '/game/b202', '/game/b203', '/game/b204']);
		expect(screen.getByRole('link', { name: 'Full series →' }).getAttribute('href')).toBe(
			'/playoffs/series?id=east-r1-2'
		);
	});

	it('shows the round, the headline and both logos', async () => {
		const { container } = show();
		await fireEvent.click(card(QXA_QXH));
		expect(container.querySelector('.result .round')?.textContent).toBe('East · Round 1');
		expect(container.querySelectorAll('.result .lead-logo, .result .other-logo')).toHaveLength(2);
	});

	it('lists no cell for a series with no games', async () => {
		const { container } = show();
		await fireEvent.click(card('East · Round 1 · QXB · QXG'));
		expect(container.querySelector('.result .headline')?.textContent).toBe('—');
		expect(container.querySelectorAll('.result .games .game')).toHaveLength(0);
	});
});

describe('PlayoffBracket phone sheet', () => {
	it('opens the sheet on a first tap, with no result panel', async () => {
		const { container } = show('mobile');
		await fireEvent.click(card(QXD_QXE));
		expect(screen.getByRole('dialog', { name: 'East · Round 1' })).toBeTruthy();
		expect(container.querySelector('section.result')).toBeNull();
	});

	it('closes the sheet with the scrim and returns the focus to the card', async () => {
		show('mobile');
		await fireEvent.click(card(QXD_QXE));
		await fireEvent.click(document.querySelector('.scrim')!);
		expect(screen.queryByRole('dialog')).toBeNull();
		expect(document.activeElement).toBe(card(QXD_QXE));
	});

	it('closes the sheet with Esc', async () => {
		show('mobile');
		await fireEvent.click(card(QXD_QXE));
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('opens the full series on a second tap of a complete series', async () => {
		const openSeries = vi.fn();
		show('mobile', 'playoffs-bracket.json', openSeries);
		await fireEvent.click(card(QXA_QXH));
		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));
		expect(openSeries).not.toHaveBeenCalled();
		await fireEvent.click(card(QXA_QXH));
		expect(openSeries).toHaveBeenCalledWith('east-r1-1');
	});

	it('does not preselect the Finals on the phone', () => {
		const { container } = show('mobile', 'playoffs-complete.json');
		expect(container.querySelectorAll('.series.selected')).toHaveLength(0);
		expect(screen.queryByRole('dialog')).toBeNull();
	});
});
