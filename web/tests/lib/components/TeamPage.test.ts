// web/tests/lib/components/TeamPage.test.ts
//
// Tests for the TeamPage component.
//
// Tested:
// - Ready: every section in order, the tab ids matching the section ids, the mini text, the record head with its season meta
// - A view with no leaders, roster or schedule renders no such sections and no such tabs
// - Loading: aria-busy and the section skeleton
// - The unavailable state of a past season keeps the Season tag; the current season's has none (ADR 0054)
// - Unavailable: the unavailable row and the nav row
// - Not found: "Team not found." and two All games links
// - The footer in every state
// - Links to the leader and roster player pages, with no nested interactive element
// - The season select reaches the header in every state, and is absent without the prop
// - A past view without a roster and leaders renders no such section or tab
// - A past view hides Overview, Injuries and the roster status column; no-team shows "No team this season."
// - The names timeline renders under the header with four runs and not with none
// - The hero logo on both layouts with the strip kept, the code for a null logo
//
// What is covered:
// - Each page state, drawn from props with no fetch; the view comes from the recorded team feed
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamPage.test.ts
//
// SEE: web/src/lib/components/TeamPage.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamPage from '../../../src/lib/components/TeamPage.svelte';
import type { TeamFeed } from '../../../src/lib/contract/team';
import { toTeamView } from '../../../src/lib/feed/team-props';
import type { TeamPageState } from '../../../src/lib/team/types';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;

const feed = (): TeamFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'team.json'), 'utf8')
	) as TeamFeed;

const show = (state: TeamPageState, layout: 'desktop' | 'mobile' = 'desktop') =>
	render(TeamPage, {
		props: {
			state,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout,
			gameHref,
			playerHref
		}
	});

const ready = (source: TeamFeed = feed()): TeamPageState => ({
	kind: 'ready',
	view: toTeamView(source)
});

describe('TeamPage ready', () => {
	it('links the leaders and the roster to the player pages, with nothing nested', () => {
		const { container } = show(ready());
		const hrefs = screen.getAllByRole('link').map((a) => a.getAttribute('href'));
		expect(hrefs).toContain('/player/p-sga');
		expect(hrefs).toContain('/player/p-holmgren');
		expect(container.querySelectorAll('a a, button a, a button')).toHaveLength(0);
	});

	it('shows the season of the record in its section head', () => {
		const { container } = show(ready());
		expect(container.querySelector('#record .meta')?.textContent).toBe('2025-26 · regular season');
	});

	it('renders every section in order, matching the tabs', () => {
		const { container } = show(ready());
		const sectionIds = [...container.querySelectorAll('.sections > section')].map((s) => s.id);
		expect(sectionIds).toEqual(['overview', 'record', 'leaders', 'roster', 'injuries', 'schedule']);
		const tabHrefs = screen
			.getAllByRole('link')
			.map((a) => a.getAttribute('href'))
			.filter((href) => href?.startsWith('#'));
		expect(tabHrefs).toEqual(sectionIds.map((id) => `#${id}`));
		expect(container.querySelector('.mini-score')?.textContent).toBe('OKC 57–25');
	});

	it('renders the h1, the section heads and the footer', () => {
		const { container } = show(ready());
		expect(screen.getByRole('heading', { level: 1, name: 'Thunder' })).toBeTruthy();
		expect([...container.querySelectorAll('h2')].map((h) => h.textContent)).toEqual([
			'Overview',
			'Record',
			'Team leaders',
			'Roster',
			'Injuries',
			'Schedule'
		]);
		expect(container.querySelector('footer')).toBeTruthy();
	});

	it('renders no leaders, roster or schedule section, nor their tabs, without data', () => {
		const source = feed();
		source.leaders = { season: '2025-26', points: null, rebounds: null, assists: null };
		source.roster = [];
		source.schedule = null;
		const { container } = show(ready(source));
		expect([...container.querySelectorAll('.sections > section')].map((s) => s.id)).toEqual([
			'overview',
			'record',
			'injuries'
		]);
		expect(screen.queryByRole('link', { name: 'Roster' })).toBeNull();
		expect(screen.queryByRole('link', { name: 'Schedule' })).toBeNull();
		expect(screen.queryByRole('link', { name: 'Leaders' })).toBeNull();
	});
});

describe('TeamPage other states', () => {
	it('shows the skeleton while loading', () => {
		const { container } = show({ kind: 'loading' });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.section-skeleton')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('footer')).toBeTruthy();
	});

	it('keeps the Season tag on the unavailable state of a past season, and has none on the current one', () => {
		const { unmount } = showWith({ kind: 'unavailable' }, { seasonTag: 'Season 2022-23' });
		expect(screen.getByText('Season 2022-23')).toBeTruthy();
		unmount();
		showWith({ kind: 'unavailable' });
		expect(screen.queryByText(/^Season /)).toBeNull();
	});

	it('shows the unavailable row under the nav row', () => {
		const { container } = show({ kind: 'unavailable' });
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
		expect(screen.getAllByRole('link', { name: 'All games' })).toHaveLength(1);
		expect(container.querySelector('footer')).toBeTruthy();
	});

	it('shows Team not found. with a link back to all games', () => {
		const { container } = show({ kind: 'not-found' });
		expect(screen.getByText('Team not found.')).toBeTruthy();
		expect(screen.getAllByRole('link', { name: 'All games' })).toHaveLength(2);
		expect(container.querySelector('footer')).toBeTruthy();
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

const pastFeed = (): TeamFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'team-past.json'), 'utf8')
	) as TeamFeed;

const seasonHref = (season: number) => `/team/okc?season=${season}`;

const showWith = (state: TeamPageState, extra: Record<string, unknown> = {}) =>
	render(TeamPage, {
		props: {
			state,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout: 'desktop',
			gameHref,
			playerHref,
			...extra
		}
	});

describe('TeamPage season selector', () => {
	it.each([
		['ready', ready()],
		['loading', { kind: 'loading' } as TeamPageState],
		['unavailable', { kind: 'unavailable' } as TeamPageState],
		['not-found', { kind: 'not-found' } as TeamPageState],
		['no-team', { kind: 'no-team' } as TeamPageState]
	])('draws the select in the %s state', (_name, state) => {
		showWith(state, { seasonSelect });
		expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
	});

	it('draws no select without the prop', () => {
		show(ready());
		expect(screen.queryByRole('combobox')).toBeNull();
	});
});

describe('TeamPage past season', () => {
	const past: TeamPageState = { kind: 'ready', view: toTeamView(pastFeed(), { past: true }) };

	it('renders no Overview and no Injuries section, and no such tabs', () => {
		const { container } = showWith(past);
		const ids = [...container.querySelectorAll('.sections > section')].map((s) => s.id);
		expect(ids).toEqual(['record', 'leaders', 'roster', 'schedule']);
		expect(container.querySelector('#overview')).toBeNull();
		expect(container.querySelector('#injuries')).toBeNull();
		const tabHrefs = screen
			.getAllByRole('link')
			.map((a) => a.getAttribute('href'))
			.filter((href) => href?.startsWith('#'));
		expect(tabHrefs).toEqual(ids.map((id) => `#${id}`));
	});

	it('renders no leaders or roster section, nor their tabs, on a past season without them', () => {
		const source: TeamFeed = { ...pastFeed(), roster: null, leaders: null, colors: null };
		const state: TeamPageState = { kind: 'ready', view: toTeamView(source, { past: true }) };
		const { container } = showWith(state);
		const ids = [...container.querySelectorAll('.sections > section')].map((s) => s.id);
		expect(ids).toEqual(['record', 'schedule']);
		expect(container.querySelector('#leaders')).toBeNull();
		expect(container.querySelector('#roster')).toBeNull();
		const tabHrefs = screen
			.getAllByRole('link')
			.map((a) => a.getAttribute('href'))
			.filter((href) => href?.startsWith('#'));
		expect(tabHrefs).toEqual(['#record', '#schedule']);
	});

	it('renders the roster without the status column', () => {
		showWith(past);
		const headers = screen.getAllByRole('columnheader').map((cell) => cell.textContent);
		expect(headers).not.toContain('Status');
	});

	it('shows the season tag', () => {
		showWith(past);
		expect(screen.getByText('Season 2004-05')).toBeTruthy();
	});

	it('shows No team this season. with the select on no-team', () => {
		showWith({ kind: 'no-team' }, { seasonSelect });
		expect(screen.getByText('No team this season.')).toBeTruthy();
		expect(screen.getByRole('combobox')).toBeTruthy();
	});
});

describe('TeamPage names timeline', () => {
	it('renders the timeline under the header with four runs', () => {
		const state: TeamPageState = { kind: 'ready', view: toTeamView(pastFeed(), { past: true }) };
		const { container } = showWith(state, { seasonHref });
		expect(screen.getByText('Names')).toBeTruthy();
		expect(container.querySelectorAll('.runs li')).toHaveLength(4);
		const header = container.querySelector('header');
		const names = container.querySelector('.names');
		expect(header && names && header.compareDocumentPosition(names)).toBe(
			Node.DOCUMENT_POSITION_FOLLOWING
		);
	});

	it('renders no timeline when the view has no names', () => {
		showWith(ready(), { seasonHref });
		expect(screen.queryByText('Names')).toBeNull();
	});

	it('renders no timeline without seasonHref', () => {
		showWith({ kind: 'ready', view: toTeamView(pastFeed(), { past: true }) });
		expect(screen.queryByText('Names')).toBeNull();
	});
});

describe('TeamPage logo', () => {
	it('draws the feed logo in the team box of the hero on both layouts, keeping the strip', () => {
		const source = feed();
		source.logo = {
			light: 'https://example.com/a-light.svg',
			dark: 'https://example.com/a-dark.svg'
		};
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = show(ready(source), layout);
			const box = container.querySelector('.team-monogram.team');
			expect(box?.querySelector('img')?.getAttribute('src')).toBe('https://example.com/a-dark.svg');
			expect(container.querySelectorAll('.strip .half').length).toBeGreaterThan(0);
			unmount();
		}
	});

	it('draws the code in the team box with a null logo', () => {
		const { container } = show(ready());
		expect(container.querySelector('.team-monogram.team')?.textContent).toBe('OKC');
	});
});
