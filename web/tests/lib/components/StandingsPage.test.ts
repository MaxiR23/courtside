// web/tests/lib/components/StandingsPage.test.ts
//
// Tests for the StandingsPage component.
//
// Tested:
// - Ready: Conference view by default, Eastern then Western, then the key
// - Toggling to Division shows the divisions in the feed's order with no lines, and back
// - Loading: the table skeleton is aria-busy
// - Unavailable: the unavailable row under the nav
// - The footer in every state
// - Spanish copy
// - The season select reaches the header in the ready, loading and unavailable states, and is absent without the prop
// - The team logos on both layouts: the feed logo in a row's box, the code for a null logo
//
// What is covered:
// - Each page state, drawn from props with no fetch; the view comes from the recorded feed
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/StandingsPage.test.ts
//
// SEE: web/src/lib/components/StandingsPage.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import StandingsPage from '../../../src/lib/components/StandingsPage.svelte';
import type { StandingsFeed } from '../../../src/lib/contract/standings';
import { toStandingsView } from '../../../src/lib/feed/standings-props';
import type { StandingsPageState } from '../../../src/lib/standings/types';
import { preferLanguages } from '../../prefer-languages';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

const feed = (): StandingsFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'standings.json'), 'utf8')
	) as StandingsFeed;

const ready = (): StandingsPageState => ({ kind: 'ready', view: toStandingsView(feed()) });

const show = (state: StandingsPageState) =>
	render(StandingsPage, {
		props: {
			state,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout: 'desktop',
			teamHref
		}
	});

const headings = () => screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);

afterEach(() => {
	vi.restoreAllMocks();
});

describe('StandingsPage', () => {
	it('links Cup in the nav to /cup without marking it current', async () => {
		show(ready());
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		const cup = screen.getByRole('link', { name: 'Cup' });
		expect(cup.getAttribute('href')).toBe('/cup');
		expect(cup.getAttribute('aria-current')).toBeNull();
	});

	it('ready: Conference view by default, Eastern then Western, then the key', () => {
		const { container } = show(ready());
		expect(headings()).toEqual(['Eastern Conference', 'Western Conference']);
		expect(screen.getByRole('button', { name: 'Conference' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		const last = container.querySelector('.groups')?.lastElementChild;
		expect(last?.classList.contains('standings-key')).toBe(true);
	});

	it('toggling to Division shows the divisions in feed order with no lines, and back', async () => {
		const { container } = show(ready());
		expect(container.querySelectorAll('.line').length).toBeGreaterThan(0);
		await fireEvent.click(screen.getByRole('button', { name: 'Division' }));
		expect(headings()).toEqual(['Atlantic', 'Southeast', 'Central', 'Pacific', 'Northwest']);
		expect(container.querySelectorAll('.line')).toHaveLength(0);
		await fireEvent.click(screen.getByRole('button', { name: 'Conference' }));
		expect(headings()).toEqual(['Eastern Conference', 'Western Conference']);
	});

	it('loading: the table skeleton is aria-busy', () => {
		const { container } = show({ kind: 'loading' });
		expect(container.querySelector('.table-skeleton')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
	});

	it('unavailable: the unavailable row under the nav', () => {
		show({ kind: 'unavailable' });
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
	});

	it('renders the footer in every state', () => {
		for (const state of [ready(), { kind: 'loading' }, { kind: 'unavailable' }] as const) {
			const { unmount } = show(state);
			expect(screen.getByRole('contentinfo')).toBeTruthy();
			unmount();
		}
	});

	it('renders every string in Spanish', () => {
		preferLanguages(['es-ES']);
		show(ready());
		expect(screen.getByRole('heading', { level: 1, name: 'Clasificación' })).toBeTruthy();
		expect(headings()).toEqual(['Conferencia Este', 'Conferencia Oeste']);
		expect(screen.getByText('Leyenda')).toBeTruthy();
		expect(screen.getByText('Temporada regular · 1180 partidos jugados')).toBeTruthy();
	});
});

const seasonSelect = {
	seasons: [
		{ season: 2027, seasonLabel: '2026-27' },
		{ season: 2005, seasonLabel: '2004-05' }
	],
	value: 2027,
	onChange: () => {}
};

describe('StandingsPage season selector', () => {
	const withSelect = (state: StandingsPageState) =>
		render(StandingsPage, {
			props: {
				state,
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'desktop',
				teamHref,
				seasonSelect
			}
		});

	it.each([
		['ready', ready()],
		['loading', { kind: 'loading' } as StandingsPageState],
		['unavailable', { kind: 'unavailable' } as StandingsPageState]
	])('draws the select in the %s state', (_name, state) => {
		withSelect(state);
		expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
	});

	it('draws no select without the prop', () => {
		show(ready());
		expect(screen.queryByRole('combobox')).toBeNull();
	});
});

describe('StandingsPage logos', () => {
	it('draws the feed logo of a row in its box on both layouts, and the code for the others', () => {
		const source = feed();
		source.conferences[0]!.teams[0]!.logo = {
			light: 'https://example.com/a-light.svg',
			dark: 'https://example.com/a-dark.svg'
		};
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = render(StandingsPage, {
				props: {
					state: { kind: 'ready', view: toStandingsView(source) },
					allGamesHref: HOME,
					standingsHref: STANDINGS,
					layout,
					teamHref
				}
			});
			const boxes = [...container.querySelectorAll('.row.body .team-monogram.standings')];
			expect(boxes[0]!.querySelector('img')?.getAttribute('src')).toBe(
				'https://example.com/a-dark.svg'
			);
			expect(boxes[1]!.querySelector('img')).toBeNull();
			unmount();
		}
	});
});
