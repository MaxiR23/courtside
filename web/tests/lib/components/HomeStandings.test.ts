// web/tests/lib/components/HomeStandings.test.ts
//
// Tests for the compact standings and the Finals path of the home with no games.
//
// Tested:
// - Standings: the h2, the East button pressed and six rows with seed, team, record and GB
// - The play-in footnote lists rows 7 to 10 with their seeds; West has none
// - Clicking West shows West's rows, presses West and un-presses East
// - The Full standings link goes to /standings; the Finals path has no such link
// - A logo draws an img and a null logo the code monogram
// - Finals path: two finalist buttons, three rows with round, opponent, result and Won
// - Switching to the second finalist shows its three opponents
// - Each opponent's --side-accent is the feed color, or the neutral accent when null
// - A lost series shows Lost with the lost class
// - No link inside a button
// - Spanish copy; the mobile class
// - The title is drawn by SectionHead at the home size and names the section
//
// What is covered:
// - Both view kinds and both layouts; jsdom does not lay out, so classes are asserted
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/HomeStandings.test.ts
//
// SEE: web/src/lib/components/HomeStandings.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import HomeStandings from '../../../src/lib/components/HomeStandings.svelte';
import type { HomeFeed } from '../../../src/lib/contract/home';
import type { StandingsFeed } from '../../../src/lib/contract/standings';
import { toHomeStandingsView } from '../../../src/lib/feed/home-props';
import { preferLanguages } from '../../prefer-languages';

const fixture = <T>(name: string): T =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', name), 'utf8')) as T;
const standingsView = () => {
	const feed = fixture<StandingsFeed>('standings.json');
	feed.conferences[0].teams[1].logo = { light: 'https://example.com/nyk.svg', dark: null };
	return toHomeStandingsView(null, feed)!;
};
const finalsView = () => toHomeStandingsView(fixture<HomeFeed>('home-finals-preview.json'), null)!;
const href = '/standings' as ResolvedPathname;

const mount = (view = standingsView(), layout: 'desktop' | 'mobile' = 'desktop') =>
	render(HomeStandings, { props: { view, layout, standingsHref: href } });

afterEach(() => {
	vi.restoreAllMocks();
});

describe('HomeStandings with the compact standings', () => {
	it('draws the title through SectionHead at the home size and names the section by it', () => {
		const { container } = mount();
		const h2 = container.querySelector('.section-head h2');
		expect(h2?.classList.contains('home')).toBe(true);
		expect(container.querySelector('.titled')).toBeNull();
		expect(container.querySelector('section')?.getAttribute('aria-labelledby')).toBe(h2?.id);
	});

	it('shows the h2, East pressed and six rows', () => {
		const { container } = mount();
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('Standings');
		expect(screen.getByRole('button', { name: 'East' }).getAttribute('aria-pressed')).toBe('true');
		expect(screen.getByRole('button', { name: 'West' }).getAttribute('aria-pressed')).toBe('false');
		const rows = container.querySelectorAll('tbody tr');
		expect(rows).toHaveLength(6);
		const second = within(rows[1] as HTMLElement);
		expect(second.getByText('2')).toBeTruthy();
		expect(rows[1].textContent).toContain('–');
		expect(rows[0].textContent).toContain('—');
	});

	it('lists the play-in teams with their seeds', () => {
		const { container } = mount();
		const note = container.querySelector('.play-in') as HTMLElement;
		expect(note.textContent).toContain('Play-In');
		const teams = [...note.querySelectorAll('.play-in-team')].map((t) => t.textContent?.trim());
		expect(teams).toEqual(['7 MIA', '8 PHI', '9 CHI', '10 ATL']);
	});

	it('switches to West, presses it and hides the footnote', async () => {
		const { container } = mount();
		await fireEvent.click(screen.getByRole('button', { name: 'West' }));
		expect(screen.getByRole('button', { name: 'West' }).getAttribute('aria-pressed')).toBe('true');
		expect(screen.getByRole('button', { name: 'East' }).getAttribute('aria-pressed')).toBe('false');
		expect(container.querySelectorAll('tbody tr')).toHaveLength(2);
		expect(container.querySelector('.play-in')).toBeNull();
	});

	it('links Full standings to /standings', () => {
		mount();
		expect(screen.getByRole('link', { name: 'Full standings →' }).getAttribute('href')).toBe(
			'/standings'
		);
	});

	it('draws a logo as an img and a null logo as the code monogram', () => {
		const { container } = mount();
		const rows = container.querySelectorAll('tbody tr');
		expect(rows[1].querySelector('img')).not.toBeNull();
		expect(rows[0].querySelector('img')).toBeNull();
		expect(rows[0].textContent).toContain('BOS');
	});

	it('has no link inside a button', () => {
		const { container } = mount();
		expect(container.querySelector('button a')).toBeNull();
	});

	it('uses Spanish copy', () => {
		preferLanguages(['es']);
		mount(standingsView());
		expect(screen.getByRole('link', { name: 'Clasificación completa →' })).toBeTruthy();
	});

	it('takes the mobile class', () => {
		const { container } = mount(standingsView(), 'mobile');
		expect(container.querySelector('section.home-standings.mobile')).not.toBeNull();
	});
});

describe('HomeStandings with the Finals path', () => {
	it('shows the two finalists and the first one path', () => {
		const { container } = mount(finalsView());
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('Road to the Finals');
		expect(screen.getByRole('button', { name: /Easterners/ }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getByRole('button', { name: /Westerners/ })).toBeTruthy();
		expect(screen.queryByRole('link', { name: /Full standings/ })).toBeNull();
		const rows = container.querySelectorAll('tbody tr');
		expect(rows).toHaveLength(3);
		expect(rows[0].textContent).toContain('First round');
		expect(rows[0].textContent).toContain('Northerners');
		expect(rows[0].textContent).toContain('4–1');
		expect(rows[0].textContent).toContain('Won');
	});

	it('switches to the second finalist', async () => {
		const { container } = mount(finalsView());
		await fireEvent.click(screen.getByRole('button', { name: /Westerners/ }));
		const text = [...container.querySelectorAll('tbody tr')].map((r) => r.textContent);
		expect(text).toHaveLength(3);
		expect(text[0]).toContain('Mountaineers');
		expect(text[1]).toContain('Pacifics');
		expect(text[2]).toContain('Desert');
	});

	it('sets the accent to the feed color or the neutral accent', () => {
		const { container } = mount(finalsView());
		const accents = [...container.querySelectorAll<HTMLElement>('.opponent')].map((o) =>
			o.style.getPropertyValue('--side-accent')
		);
		expect(accents).toEqual(['#1D4E89', 'var(--identity-neutral-accent)', '#B5332E']);
	});

	it('shows Lost with the lost class for a lost series', () => {
		const view = finalsView();
		if (view.kind !== 'finalsPath') throw new Error('expected finalsPath');
		view.tabs[0].series[0].won = false;
		const { container } = mount(view);
		const lost = container.querySelector('.status.lost') as HTMLElement;
		expect(lost.textContent?.trim()).toBe('Lost');
		expect(container.querySelectorAll('.lost')).toHaveLength(1);
	});

	it('has no link inside a button', () => {
		const { container } = mount(finalsView());
		expect(container.querySelector('button a')).toBeNull();
	});

	it('uses Spanish copy', () => {
		preferLanguages(['es']);
		const view = toHomeStandingsView(fixture<HomeFeed>('home-finals-preview.json'), null)!;
		const { container } = mount(view);
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('Camino a las Finales');
		expect(container.querySelector('tbody tr')?.textContent).toContain('Ganada');
	});
});
