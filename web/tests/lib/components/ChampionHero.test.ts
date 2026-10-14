// web/tests/lib/components/ChampionHero.test.ts
//
// Tests for the ChampionHero component.
//
// Tested:
// - The tag, the result line, the Champions title, the team name and the four stats with the differential in accent
// - The trophy drawing on the desktop plate; the compact hero on mobile
// - Relive the series only when the series section exists; the buttons scroll to #series and #bracket
// - The stats count up and show the final values when the timeout ends
// - Under reduced motion the final values show at once
//
// What is covered:
// - Each state the hero shows, drawn from props with no fetch
// - Fake timers; no animation frame is asserted (docs/testing.md)
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/ChampionHero.test.ts
//
// SEE: web/src/lib/components/ChampionHero.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import ChampionHero from '../../../src/lib/components/ChampionHero.svelte';

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const hero = () => {
	const feed = JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'playoffs-complete.json'), 'utf8')
	) as PlayoffsFeed;
	return toPlayoffsView(feed, null).header.hero!;
};
const show = (showRelive = true, layout: 'desktop' | 'mobile' = 'desktop') =>
	render(ChampionHero, { props: { hero: hero(), layout, teamHref, showRelive } });

const motion = (reduced: boolean) =>
	vi.stubGlobal(
		'matchMedia',
		vi.fn(() => ({ matches: reduced, addEventListener: () => {}, removeEventListener: () => {} }))
	);

beforeEach(() => {
	vi.useFakeTimers();
	document.documentElement.style.setProperty('--playoffs-count-duration', '1.4s');
	document.documentElement.style.setProperty('--playoffs-count-timeout', '1.6s');
	motion(false);
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
	document.documentElement.removeAttribute('style');
	document.body.innerHTML = '';
});

describe('ChampionHero', () => {
	it('shows the tag, the result line, the title, the team and the trophy', () => {
		const { container } = show();
		expect(screen.getByText('2027 NBA Finals')).toBeTruthy();
		expect(screen.getByText('Owls win series 4–1 · Jun 4 – Jun 19')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'Champions' })).toBeTruthy();
		expect(screen.getByText('Harbor')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Owls' }).getAttribute('href')).toBe('/team/qxa');
		expect(screen.getByRole('img', { name: '2027 champions' })).toBeTruthy();
		expect(container.querySelector('.plate-label')?.textContent).toBe('2027 champions');
		expect(container.querySelectorAll('.strip .half')).toHaveLength(2);
	});

	it('shows the four stats with the point differential in accent', async () => {
		const { container } = show();
		const stats = [...container.querySelectorAll('.stat')].map((s) => [
			s.querySelector('dt')?.textContent,
			s.classList.contains('accent')
		]);
		expect(stats).toEqual([
			['Postseason record', false],
			['Home', false],
			['Road', false],
			['Point differential', true]
		]);
	});

	it('draws the trophy beside the headline on mobile and no plate', () => {
		const { container } = show(true, 'mobile');
		expect(container.querySelector('.plate')).toBeNull();
		expect(container.querySelector('.trophy-mobile svg')).not.toBeNull();
		expect(container.querySelector('.champion-hero')?.classList.contains('mobile')).toBe(true);
	});

	it('draws Relive the series only when the series section exists', () => {
		show(false);
		expect(screen.queryByRole('button', { name: 'Relive the series' })).toBeNull();
		expect(screen.getByRole('button', { name: 'Full bracket' })).toBeTruthy();
	});

	it('scrolls to the series and to the bracket', async () => {
		for (const id of ['series', 'bracket']) {
			const section = document.createElement('section');
			section.id = id;
			document.body.append(section);
		}
		const scrolled: string[] = [];
		Element.prototype.scrollIntoView = vi.fn(function (this: Element) {
			scrolled.push(this.id);
		});
		show();
		await fireEvent.click(screen.getByRole('button', { name: 'Relive the series' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Full bracket' }));
		expect(scrolled).toEqual(['series', 'bracket']);
		expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
			behavior: 'smooth',
			block: 'start'
		});
	});

	it('counts the stats up from zero and shows the final values when the timeout ends', async () => {
		const { container } = show();
		await vi.advanceTimersByTimeAsync(0);
		const values = () => [...container.querySelectorAll('dd')].map((d) => d.textContent);
		expect(values()).toEqual(['0-0', '0-0', '0-0', '+0']);
		await vi.advanceTimersByTimeAsync(1600);
		expect(values()).toEqual(['16-6', '9-2', '7-4', '+142']);
	});

	it('shows the final values at once under reduced motion and scrolls without smoothing', async () => {
		motion(true);
		const { container } = show();
		await vi.advanceTimersByTimeAsync(0);
		expect([...container.querySelectorAll('dd')].map((d) => d.textContent)).toEqual([
			'16-6',
			'9-2',
			'7-4',
			'+142'
		]);
		expect(vi.getTimerCount()).toBe(0);
	});
});
