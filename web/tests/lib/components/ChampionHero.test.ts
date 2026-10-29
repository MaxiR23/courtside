// web/tests/lib/components/ChampionHero.test.ts
//
// Tests for the ChampionHero component.
//
// Tested:
// - The label, the h1 with the city and the team link, the subline
// - One strip column per final Finals game, 4-1 and 4-3 series, with .loss on the lost games
// - The logo in the .logo box (hidden from assistive technology), the code for a null logo
// - The trophy drawing hidden from assistive technology
// - The glow color: the accent of the feed, the neutral accent for null
// - No buttons, stats or plate, and no timers
// - The strip links to #series and scrolls (smooth, or at once under reduced motion) only when the series section exists
// - The first row: trophy, label, one season tag (the past tag replaces the season), the state line
// - The desktop selector is the page header's, beside the first line at the right edge; on mobile it is full width after the band
// - The strip link has no label of its own: it reads "Game {n}, {score}, won/lost" per column; the group keeps its name
// - The first row on mobile is two lines (title, then tag and state); the rules that do it
// - The mobile layout keeps the logo, the trophy and the strip
// - The label row is the first line on both layouts and the header carries mobile
// - The band holds the label row and the strip, and the after rows come after the band
// - The art is before the copy on mobile and in the right column on desktop
//
// What is covered:
// - Each state the hero shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/ChampionHero.test.ts
//
// SEE: web/src/lib/components/ChampionHero.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createRawSnippet } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import ChampionHero from '../../../src/lib/components/ChampionHero.svelte';
import type { SeasonControl } from '../../../src/lib/season/types';
import type { ChampionHeroView } from '../../../src/lib/playoffs/types';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

// The complete fixture with scores: the champion QXA wins G1, G2, G4, G5 and loses G3.
const hero = (games = 5, accent: string | null = '#1d4e89'): ChampionHeroView => {
	const feed = JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'playoffs-complete.json'), 'utf8')
	) as PlayoffsFeed;
	const finals = feed.bracket.find((series) => series.conference === null)!;
	const results = [
		[105, 95],
		[110, 100],
		[98, 101],
		[99, 90],
		[102, 97]
	];
	finals.games.forEach((game, i) => {
		const [champion, opponent] = results[i];
		const home = game.home.code === 'QXA';
		game.score = home ? { home: champion, away: opponent } : { away: champion, home: opponent };
		game.winner = champion > opponent ? (home ? 'home' : 'away') : home ? 'away' : 'home';
	});
	if (games === 7) {
		(finals.games as unknown[]).push(
			{ ...finals.games[2]!, id: 'g106', number: 6 },
			{ ...finals.games[2]!, id: 'g107', number: 7 }
		);
		feed.champion!.losses = 3;
	}
	feed.champion!.accent = accent;
	return toPlayoffsView(feed, null).header.hero!;
};
const show = (
	options: {
		linkSeries?: boolean;
		layout?: 'desktop' | 'mobile';
		view?: ChampionHeroView;
		tag?: string | null;
		seasonSelect?: SeasonControl | null;
	} = {}
) =>
	render(ChampionHero, {
		props: {
			hero: options.view ?? hero(),
			layout: options.layout ?? 'desktop',
			teamHref,
			linkSeries: options.linkSeries ?? true,
			season: '2026-27',
			tag: options.tag ?? null,
			stateLine: 'Complete',
			seasonSelect: options.seasonSelect ?? null,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			after: createRawSnippet(() => ({ render: () => '<p class="stages">Stages</p>' }))
		}
	});

const motion = (reduced: boolean) =>
	vi.stubGlobal(
		'matchMedia',
		vi.fn(() => ({ matches: reduced, addEventListener: () => {}, removeEventListener: () => {} }))
	);

beforeEach(() => {
	vi.useFakeTimers();
	motion(false);
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
	document.body.innerHTML = '';
});

describe('ChampionHero', () => {
	it('shows the label, the headline, the subline and a column per game of a 4-1 series', () => {
		const { container } = show();
		expect(container.querySelector('.label')?.textContent).toBe('2027 NBA Champions');
		const h1 = screen.getByRole('heading', { level: 1 });
		expect(h1.textContent).toContain('Harbor');
		expect(screen.getByRole('link', { name: 'Owls' }).getAttribute('href')).toBe('/team/qxa');
		expect(screen.getByText('Won the series 4–1 over Summit · Jun 4 – Jun 19')).toBeTruthy();
		const games = [...container.querySelectorAll('.strip .game')];
		expect(
			games.map((g) => [g.querySelector('.n')?.textContent, g.querySelector('.score')?.textContent])
		).toEqual([
			['G1', '105–95'],
			['G2', '110–100'],
			['G3', '98–101'],
			['G4', '99–90'],
			['G5', '102–97']
		]);
		expect(games.map((g) => g.classList.contains('loss'))).toEqual([
			false,
			false,
			true,
			false,
			false
		]);
	});

	it('draws seven columns and the 4-3 subline for a seven game series', () => {
		const { container } = show({ view: hero(7) });
		expect(container.querySelectorAll('.strip .game')).toHaveLength(7);
		expect(container.querySelectorAll('.strip .game.loss')).toHaveLength(3);
		expect(screen.getByText('Won the series 4–3 over Summit · Jun 4 – Jun 19')).toBeTruthy();
	});

	it('draws the trophy hidden from assistive technology', () => {
		const { container } = show();
		const trophy = container.querySelector('.trophy');
		expect(trophy?.getAttribute('aria-hidden')).toBe('true');
		expect(trophy?.querySelector('svg')).not.toBeNull();
	});

	it('sets the glow color from the accent, and the neutral accent for null', () => {
		const first = show();
		expect(
			first.container.querySelector<HTMLElement>('.art')?.style.getPropertyValue('--side-accent')
		).toBe('#1d4e89');
		first.unmount();
		const plain = show({ view: hero(5, null) });
		expect(
			plain.container.querySelector<HTMLElement>('.art')?.style.getPropertyValue('--side-accent')
		).toBe('var(--identity-neutral-accent)');
	});

	it('has no buttons, stats or plate and starts no timer', () => {
		const { container } = show();
		expect(container.querySelectorAll('.band button')).toHaveLength(0);
		expect(container.querySelector('.stats')).toBeNull();
		expect(container.querySelector('dl')).toBeNull();
		expect(container.querySelector('.plate')).toBeNull();
		expect(vi.getTimerCount()).toBe(0);
	});

	it('keeps the logo, the trophy and the strip on mobile', () => {
		const { container } = show({ layout: 'mobile' });
		expect(container.querySelector('header')?.classList.contains('mobile')).toBe(true);
		expect(container.querySelector('.logo .team-monogram')).not.toBeNull();
		expect(container.querySelector('.trophy svg')).not.toBeNull();
		expect(container.querySelectorAll('.strip .game')).toHaveLength(5);
		const art = container.querySelector('.art') as Node;
		expect(container.querySelector('.aside')).toBeNull();
		expect(art.compareDocumentPosition(container.querySelector('.copy') as Node)).toBe(
			Node.DOCUMENT_POSITION_FOLLOWING
		);
	});

	it('puts the art in the right column on desktop', () => {
		const { container } = show();
		expect(container.querySelector('.aside > .art')).not.toBeNull();
		expect(container.querySelector('.copy')?.closest('.lead')).not.toBeNull();
	});

	it('draws the band with the label row and the strip, and the after rows below it', () => {
		const { container } = show();
		const band = container.querySelector('.band')!;
		expect(band.querySelector('.first-line > .label-row')).not.toBeNull();
		expect(band.querySelector('.strip')).not.toBeNull();
		const after = screen.getByText('Stages');
		expect(band.contains(after)).toBe(false);
		expect(band.compareDocumentPosition(after)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
	});
});

describe('ChampionHero strip', () => {
	const addSeries = () => {
		const section = document.createElement('section');
		section.id = 'series';
		document.body.append(section);
	};

	it('links to the series and scrolls smoothly on a click', async () => {
		addSeries();
		const scrolled: string[] = [];
		Element.prototype.scrollIntoView = vi.fn(function (this: Element) {
			scrolled.push(this.id);
		});
		show();
		const link = screen.getByRole('link', { name: /Game 1, 105–95, won/ });
		expect(link.getAttribute('href')).toBe('#series');
		await fireEvent.click(link);
		expect(scrolled).toEqual(['series']);
		expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
			behavior: 'smooth',
			block: 'start'
		});
	});

	it('scrolls at once under reduced motion', async () => {
		motion(true);
		addSeries();
		Element.prototype.scrollIntoView = vi.fn();
		show();
		await fireEvent.click(screen.getByRole('link', { name: /Game 1, 105–95, won/ }));
		expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
			behavior: 'auto',
			block: 'start'
		});
	});

	it('draws the same strip with no link without the series section', () => {
		show({ linkSeries: false });
		expect(screen.queryByRole('link', { name: /Game 1/ })).toBeNull();
		expect(document.querySelector('a.strip')).toBeNull();
		const group = screen.getByRole('group', { name: 'Finals game scores' });
		expect(group.querySelectorAll('.game')).toHaveLength(5);
	});
});

describe('ChampionHero first row and strip name', () => {
	const select = (onChange = vi.fn()) => ({
		seasons: [
			{ season: 2027, seasonLabel: '2026-27' },
			{ season: 2025, seasonLabel: '2024-25' }
		],
		value: 2027,
		onChange
	});

	it('puts the label, one season tag and the state text in the first line', () => {
		const { container } = show();
		const row = container.querySelector('.label-row')!;
		expect(container.querySelector('.first-line > .label-row')).toBe(row);
		expect(row.querySelector('.label')?.textContent).toBe('2027 NBA Champions');
		expect(row.textContent).toContain('2026-27');
		expect(row.textContent).toContain('Complete');
	});

	it('draws only the past tag on a past season', () => {
		const { container } = show({ tag: 'Season 2025-26' });
		expect(screen.getByText('Season 2025-26')).toBeTruthy();
		expect(screen.queryByText('2026-27')).toBeNull();
		expect(container.querySelector('.label-row')?.textContent).toContain('Season 2025-26');
	});

	it('draws the selector on the first-line row on desktop and none on mobile', () => {
		const onChange = vi.fn();
		const { container, unmount } = show({ seasonSelect: select(onChange) });
		const box = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
		expect(container.querySelector('.season-select')?.contains(box)).toBe(true);
		expect(container.querySelector('.label-row')?.contains(box)).toBe(false);
		expect(container.querySelector('.first-line')?.contains(box)).toBe(false);
		box.value = '2025';
		box.dispatchEvent(new Event('change', { bubbles: true }));
		expect(onChange).toHaveBeenCalledWith(2025);
		unmount();
		const phone = show({ layout: 'mobile', seasonSelect: select() });
		expect(phone.container.querySelector('.season-select')).toBeNull();
		expect(phone.container.querySelector('.after-inner select.full')).not.toBeNull();
	});

	it('names the strip link from its columns and hides the visible text', () => {
		const { container } = show();
		const link = container.querySelector('a.strip')!;
		expect(link.hasAttribute('aria-label')).toBe(false);
		expect(screen.getByRole('link', { name: /Game 3, 98–101, lost/ })).toBeTruthy();
		expect(screen.getByRole('link', { name: /Game 1, 105–95, won/ })).toBeTruthy();
		for (const el of container.querySelectorAll('.strip .n, .strip .score')) {
			expect(el.getAttribute('aria-hidden')).toBe('true');
		}
	});
});

describe('ChampionHero logo', () => {
	it('draws the champion logo in the logo box, and the code for a null logo', () => {
		const withLogo = hero();
		withLogo.team.logo = {
			light: 'https://example.com/x-light.svg',
			dark: 'https://example.com/x-dark.svg'
		};
		const first = show({ view: withLogo });
		const box = first.container.querySelector('.logo');
		expect(box?.getAttribute('aria-hidden')).toBe('true');
		expect(box?.querySelector('img')?.getAttribute('src')).toBe('https://example.com/x-dark.svg');
		first.unmount();
		const plain = show().container.querySelector('.logo');
		expect(plain?.querySelector('img')).toBeNull();
		expect(plain?.textContent).toContain('QXA');
	});
});

describe('ChampionHero first row lines', () => {
	const select = () => ({
		seasons: [{ season: 2027, seasonLabel: '2026-27' }],
		value: 2027,
		onChange: vi.fn()
	});

	it.each([
		['2026-27', null],
		['Season 2025-26', 'Season 2025-26']
	])('splits the first row into two lines on mobile (%s)', (tagText, tag) => {
		const { container } = show({ layout: 'mobile', tag });
		const lines = container.querySelectorAll('.label-row > .line');
		expect(lines).toHaveLength(2);
		expect(lines[0]!.querySelector('.trophy')).not.toBeNull();
		expect(lines[0]!.querySelector('.label')?.textContent).toBe('2027 NBA Champions');
		expect(lines[0]!.textContent).not.toContain(tagText);
		expect(lines[1]!.textContent).toContain(tagText);
		expect(lines[1]!.querySelector('.state-line')?.textContent).toBe('Complete');
		expect(lines[1]!.querySelector('.label')).toBeNull();
		expect(container.querySelector('header')?.classList.contains('mobile')).toBe(true);
	});

	it('keeps one row beside the selector column on desktop', () => {
		const { container } = show({ seasonSelect: select() });
		const row = container.querySelector('.label-row')!;
		expect(row.querySelectorAll(':scope > .line')).toHaveLength(2);
		expect(row.querySelector('select')).toBeNull();
		expect(container.querySelector('.main > .season-select.floating select')).not.toBeNull();
		expect(container.querySelector('header')?.classList.contains('mobile')).toBe(false);
	});

	it('lays the lines out only on mobile', () => {
		const style = (
			readFileSync(
				join(__dirname, '..', '..', '..', 'src/lib/components/ChampionHero.svelte'),
				'utf8'
			).match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1] ?? ''
		).replace(/\/\*[\s\S]*?\*\//g, '');
		const declarations = (selector: string): string[] =>
			[...style.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
				.filter((m) => m[1]!.trim() === selector)
				.flatMap((m) =>
					m[2]!
						.split(';')
						.map((d) => d.trim().replace(/\s+/g, ' '))
						.filter(Boolean)
				);
		expect(style.length).toBeGreaterThan(0);
		expect(declarations('.line')).toEqual(['display: contents']);
		expect(declarations('.label-row.mobile')).toContain('flex-direction: column');
		expect(declarations('.label-row.mobile .line')).toEqual(
			expect.arrayContaining(['display: flex', 'white-space: nowrap'])
		);
	});

	it('puts the label row first in the lead column and the header carries mobile', () => {
		const a = show({ layout: 'mobile' });
		expect(a.container.querySelector('header')?.classList.contains('mobile')).toBe(true);
		expect(a.container.querySelector('.lead')?.firstElementChild?.matches('.first-line')).toBe(
			true
		);
		a.unmount();
		const b = show({ layout: 'desktop' });
		expect(b.container.querySelector('header')?.classList.contains('mobile')).toBe(false);
	});
});
