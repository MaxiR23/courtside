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
		props: { state, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop', teamHref }
	});

const headings = () => screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);

afterEach(() => {
	vi.restoreAllMocks();
});

describe('StandingsPage', () => {
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
