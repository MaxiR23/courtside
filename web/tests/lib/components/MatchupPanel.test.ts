// web/tests/lib/components/MatchupPanel.test.ts
//
// Tests for the MatchupPanel component.
//
// Tested:
// - Loading: a busy dialog with skeleton bones; unavailable: the unavailable line
// - Ready: the header with and without a game, Final/OT, the game page link only when it exists
// - The path links, the injuries and the none line, the starters marked, the leaders in the accent class
// - The championship note only for the final
// - A roster row opens the player card, Previous and Next step through that side, and closing it returns the focus to the row
// - Close calls onClose and has the focus on open
// - The mobile sheet class and aria-modal
// - Spanish copy
//
// What is covered:
// - Each state the panel shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/MatchupPanel.test.ts
//
// SEE: web/src/lib/components/MatchupPanel.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import MatchupPanel from '../../../src/lib/components/MatchupPanel.svelte';
import MatchupPanelHarness from './MatchupPanelHarness.svelte';
import type { CupMatchupFeed } from '../../../src/lib/contract/cup-matchup';
import type { MatchupPanelState } from '../../../src/lib/cup/types';
import { toMatchupView } from '../../../src/lib/feed/cup-matchup-props';
import { preferLanguages } from '../../prefer-languages';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;

const feed = (): CupMatchupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'cup-matchup.json'), 'utf8')
	) as CupMatchupFeed;

const ready = (source = feed()): MatchupPanelState => ({
	kind: 'ready',
	view: toMatchupView(source)
});

const show = (state: MatchupPanelState, extra: Record<string, unknown> = {}) =>
	render(MatchupPanel, {
		props: {
			state,
			layout: 'desktop',
			gameHref,
			playerHref,
			card: null,
			onCard: () => {},
			onClose: () => {},
			...extra
		}
	});

afterEach(() => {
	vi.restoreAllMocks();
	document.body.style.overflow = '';
});

describe('MatchupPanel states', () => {
	it('is a busy dialog with skeleton bones while loading', () => {
		const { container } = show({ kind: 'loading' });
		const dialog = screen.getByRole('dialog', { name: 'Loading matchup' });
		expect(dialog.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelectorAll('.bone').length).toBeGreaterThan(0);
	});

	it('shows the unavailable line and keeps Close', () => {
		show({ kind: 'unavailable' });
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Close' })).toBeTruthy();
	});

	it('closes from Close, which has the focus on open', async () => {
		const onClose = vi.fn();
		show({ kind: 'loading' }, { onClose });
		const close = screen.getByRole('button', { name: 'Close' });
		expect(document.activeElement).toBe(close);
		await fireEvent.click(close);
		expect(onClose).toHaveBeenCalledTimes(1);
	});
});

describe('MatchupPanel ready', () => {
	it('shows the header of the final with its facts and the game page link', () => {
		show(ready());
		expect(screen.getByRole('dialog', { name: 'Championship' })).toBeTruthy();
		expect(screen.getByRole('heading', { name: 'Championship', level: 2 })).toBeTruthy();
		expect(screen.getByText('Dec 16')).toBeTruthy();
		expect(screen.getByText('Harbor Arena')).toBeTruthy();
		expect(screen.getByText('Courtside TV')).toBeTruthy();
		expect(screen.getByText('Neutral site')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Game page →' }).getAttribute('href')).toBe(
			'/game/9100004'
		);
	});

	it('shows both teams with their scores and Final/OT', () => {
		const { container } = show(ready());
		expect([...container.querySelectorAll('.team-name')].map((n) => n.textContent)).toEqual([
			'Herons',
			'Sailors'
		]);
		expect([...container.querySelectorAll('.team-line .score')].map((n) => n.textContent)).toEqual([
			'124',
			'120'
		]);
		expect(container.querySelector('.status')?.textContent?.trim()).toBe('Final/OT');
	});

	it('shows no game page link when the page does not exist, and Final after regulation', () => {
		const f = feed();
		if (!f.game) throw new Error('fixture');
		f.game.detailAvailable = false;
		f.game.period = 4;
		const { container } = show(ready(f));
		expect(screen.queryByRole('link', { name: 'Game page →' })).toBeNull();
		expect(container.querySelector('.status')?.textContent?.trim()).toBe('Final');
	});

	it('shows only the round and vs when there is no game', () => {
		const f = feed();
		f.game = null;
		const { container } = show(ready(f));
		expect(container.querySelector('.facts')?.children).toHaveLength(0);
		expect(container.querySelector('.status')?.textContent?.trim()).toBe('vs');
		expect(container.querySelectorAll('.team-line .score')).toHaveLength(0);
	});

	it('links the path rows that have a page and lists the injuries', () => {
		const { container } = show(ready());
		const links = container.querySelectorAll('a.path-row');
		expect(links).toHaveLength(4);
		expect(screen.getByText('Ankle sprain')).toBeTruthy();
		expect(screen.getByText('No injuries reported.')).toBeTruthy();
	});

	it('marks the starters of both teams and the leaders in the accent class', () => {
		const { container } = show(ready());
		expect(screen.getAllByRole('img', { name: 'Starting five' })).toHaveLength(4);
		expect(container.querySelectorAll('td.leader').length).toBe(6);
	});

	it('shows the championship note only for the final', () => {
		show(ready());
		expect(
			screen.getByText('The Championship game does not count toward the regular-season record.')
		).toBeTruthy();
	});

	it('shows no note for a semifinal', () => {
		const f = feed();
		f.round = 'semifinals';
		f.conference = 'east';
		show(ready(f));
		expect(screen.queryByText(/does not count/)).toBeNull();
		expect(screen.getByRole('heading', { name: 'East · Semifinals' })).toBeTruthy();
	});
});

describe('MatchupPanel player card', () => {
	it('asks to open the card of the clicked row with its side and index', async () => {
		const onCard = vi.fn();
		show(ready(), { onCard });
		await fireEvent.click(screen.getByRole('button', { name: 'Gus Hale' }));
		expect(onCard).toHaveBeenCalledWith({ side: 1, index: 1 });
	});

	it('shows the card of the open row, with that side roster to step through', () => {
		show(ready(), { card: { side: 1, index: 1 } });
		expect(screen.getByRole('dialog', { name: 'Gus Hale' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Player page' }).getAttribute('href')).toBe(
			'/player/p202'
		);
	});

	it('steps to the next player of the same side and closes', async () => {
		const onCard = vi.fn();
		show(ready(), { card: { side: 1, index: 1 }, onCard });
		await fireEvent.click(screen.getByRole('button', { name: 'Next player' }));
		expect(onCard).toHaveBeenLastCalledWith({ side: 1, index: 2 });
		const closes = screen.getAllByRole('button', { name: 'Close' });
		await fireEvent.click(closes[closes.length - 1]!);
		expect(onCard).toHaveBeenLastCalledWith(null);
	});

	it('returns the focus to the row when the card closes', async () => {
		render(MatchupPanelHarness, { props: { state: ready(), gameHref, playerHref } });
		const row = screen.getByRole('button', { name: 'Bo Keller' });
		await fireEvent.click(row);
		expect(screen.getByRole('dialog', { name: 'Bo Keller' })).toBeTruthy();
		const closes = screen.getAllByRole('button', { name: 'Close' });
		await fireEvent.click(closes[closes.length - 1]!);
		expect(screen.queryByRole('dialog', { name: 'Bo Keller' })).toBeNull();
		expect(document.activeElement).toBe(row);
	});
});

describe('MatchupPanel on a phone', () => {
	it('is a modal sheet that locks the page scroll', () => {
		const { container, unmount } = show(ready(), { layout: 'mobile' });
		expect(container.querySelector('.panel.mobile')).not.toBeNull();
		expect(screen.getByRole('dialog', { name: 'Championship' }).getAttribute('aria-modal')).toBe(
			'true'
		);
		expect(document.body.style.overflow).toBe('hidden');
		unmount();
		expect(document.body.style.overflow).toBe('');
	});

	it('is not modal on desktop', () => {
		show(ready());
		expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBeNull();
		expect(document.body.style.overflow).toBe('');
	});
});

describe('MatchupPanel in Spanish', () => {
	it('writes the labels in Spanish', () => {
		preferLanguages(['es']);
		show(ready());
		expect(screen.getAllByText('Plantilla')).toHaveLength(2);
		expect(screen.getAllByText('Recorrido')).toHaveLength(2);
		expect(screen.getByRole('link', { name: 'Página del partido →' })).toBeTruthy();
		expect(screen.getByText('Sede neutral')).toBeTruthy();
	});
});
