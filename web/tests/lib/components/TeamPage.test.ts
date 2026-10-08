// web/tests/lib/components/TeamPage.test.ts
//
// Tests for the TeamPage component.
//
// Tested:
// - Ready: every section in order, the tab ids matching the section ids, the mini text
// - A view with no leaders, roster or schedule renders no such sections and no such tabs
// - Loading: aria-busy and the section skeleton
// - Unavailable: the unavailable row and the nav row
// - Not found: "Team not found." and two All games links
// - The footer in every state
// - Links to the leader and roster player pages, with no nested interactive element
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
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;

const feed = (): TeamFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'team.json'), 'utf8')
	) as TeamFeed;

const show = (state: TeamPageState, layout: 'desktop' | 'mobile' = 'desktop') =>
	render(TeamPage, { props: { state, allGamesHref: HOME, layout, gameHref, playerHref } });

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
