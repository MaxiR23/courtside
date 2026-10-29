// web/tests/lib/components/PlayoffsHeader.test.ts
//
// Tests for the PlayoffsHeader component.
//
// Tested:
// - The nav with Playoffs as the current page
// - The season tag, the state line and the five stages with dates, TBD and status labels
// - The Playoffs title in every state but complete; the champion hero instead of it in complete
// - Loading: bones and aria-busy; a null header shows only the nav and the title
// - The season tag when the header has one; the select on desktop and mobile (full), its onChange; none without the prop
// - With the hero: no season line above it; the hero's first line holds the season and the state text, and the selector is beside it
// - One season tag: the past tag replaces the season, with and without the hero
// - Four stages draw a four-column strip
// - Spanish copy
// - The first line is inside the page header's .first-line in every state; with the hero the stage strip comes after the band
//
// What is covered:
// - Each state the header shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayoffsHeader.test.ts
//
// SEE: web/src/lib/components/PlayoffsHeader.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import { preferLanguages } from '../../prefer-languages';
import PlayoffsHeader from '../../../src/lib/components/PlayoffsHeader.svelte';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const feed = (file: string) =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', file), 'utf8')) as PlayoffsFeed;
const header = (file: string) => toPlayoffsView(feed(file), null).header;
const show = (props: Record<string, unknown>) =>
	render(PlayoffsHeader, {
		props: {
			header: null,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout: 'desktop' as const,
			teamHref,
			...props
		}
	});

afterEach(() => {
	vi.restoreAllMocks();
});

describe('PlayoffsHeader', () => {
	it('draws the nav with Playoffs current', async () => {
		show({ header: header('playoffs-picture.json') });
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		const link = screen.getByRole('link', { name: 'Playoffs' });
		expect(link.getAttribute('aria-current')).toBe('page');
		expect(link.getAttribute('href')).toBe('/playoffs');
	});

	it('shows the season tag, the state line, the title and the five stages', () => {
		const { container } = show({ header: header('playoffs-picture.json') });
		expect(screen.getByText('2026-27')).toBeTruthy();
		expect(screen.getByText('Playoff picture')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'Playoffs' })).toBeTruthy();
		const items = [...container.querySelectorAll('.stage-strip li')].map((li) =>
			[...li.querySelectorAll('.label, .dates, .status')].map((s) => s.textContent)
		);
		expect(items).toEqual([
			['Play-In', 'TBD', 'Next'],
			['Round 1', 'TBD', 'Upcoming'],
			['Conf. semis', 'TBD', 'Upcoming'],
			['Conf. finals', 'TBD', 'Upcoming'],
			['Finals', 'TBD', 'Upcoming']
		]);
		expect(container.querySelector('.stage-strip')?.classList.contains('five')).toBe(true);
	});

	it('shows stage dates and the status classes of a state with a stage in progress', () => {
		const { container } = show({ header: header('playoffs-playin.json') });
		const items = [...container.querySelectorAll('.stage-strip li')];
		expect(items[0]?.textContent).toContain('Apr 14 – Apr 17');
		expect(items[0]?.classList.contains('current')).toBe(true);
	});

	it('draws the champion hero instead of the title in the complete state', () => {
		const { container } = show({ header: header('playoffs-complete.json'), linkSeries: true });
		const hero = container.querySelector('.band')!;
		expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Harbor');
		expect(screen.queryByRole('heading', { level: 1, name: 'Playoffs' })).toBeNull();
		expect(container.querySelector('a.strip')).not.toBeNull();
		expect(screen.getAllByText('Complete').length).toBeGreaterThan(0);
		expect(container.querySelectorAll('header')).toHaveLength(1);
		const before = (a: Element, b: Element) =>
			Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
		expect(container.querySelector('.season-line')).toBeNull();
		expect(container.querySelector('.season-row')).toBeNull();
		expect(hero.querySelector('.first-line .label-row')?.textContent).toContain('Complete');
		expect(before(hero, container.querySelector('.stage-strip')!)).toBe(true);
	});

	it('shows the bones and aria-busy while loading', () => {
		const { container } = show({ loading: true });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.bones')).not.toBeNull();
		expect(screen.getByRole('heading', { level: 1, name: 'Playoffs' })).toBeTruthy();
	});

	it('shows only the nav and the title with no header', () => {
		const { container } = show({});
		expect(container.querySelector('.stage-strip')).toBeNull();
		expect(container.querySelector('.bones')).toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
		expect(screen.getByRole('heading', { level: 1, name: 'Playoffs' })).toBeTruthy();
	});

	it('shows Spanish copy', () => {
		preferLanguages(['es-ES']);
		show({ header: header('playoffs-picture.json') });
		expect(screen.getByText('Panorama de playoffs')).toBeTruthy();
		expect(screen.getAllByText('Por definir').length).toBe(5);
	});
});

describe('PlayoffsHeader season selector and tag', () => {
	const seasonSelect = (onChange = vi.fn()) => ({
		seasons: [
			{ season: 2027, seasonLabel: '2026-27' },
			{ season: 2025, seasonLabel: '2024-25' }
		],
		value: 2027,
		onChange
	});

	it('draws the season tag only when the header has one', () => {
		const tagged = { ...header('playoffs-picture.json'), tag: 'Season 2024-25' };
		const { unmount } = show({ header: tagged });
		expect(screen.getByText('Season 2024-25')).toBeTruthy();
		unmount();
		show({ header: header('playoffs-picture.json') });
		expect(screen.queryByText('Season 2024-25')).toBeNull();
	});

	it('draws one tag: the past tag replaces the season, with and without the hero', () => {
		const picture = { ...header('playoffs-picture.json'), tag: 'Season 2024-25' };
		const { unmount } = show({ header: picture });
		expect(screen.getByText('Season 2024-25')).toBeTruthy();
		expect(screen.queryByText('2026-27')).toBeNull();
		unmount();
		const done = { ...header('playoffs-complete.json'), tag: 'Season 2024-25' };
		show({ header: done });
		expect(screen.getByText('Season 2024-25')).toBeTruthy();
		expect(screen.queryByText(done.season)).toBeNull();
	});

	it('with the hero draws one select: on the first-line row on desktop, below the stage strip on mobile', () => {
		const complete = header('playoffs-complete.json');
		const desktop = show({ header: complete, seasonSelect: seasonSelect() });
		expect(screen.getAllByRole('combobox')).toHaveLength(1);
		const place = screen.getByRole('combobox').closest('.season-select');
		expect(place?.classList.contains('floating')).toBe(true);
		expect(place?.parentElement?.classList.contains('main')).toBe(true);
		expect(place?.parentElement?.querySelector('.lead .first-line .label-row')).not.toBeNull();
		expect(
			desktop.container.querySelector('.label-row')?.contains(screen.getByRole('combobox'))
		).toBe(false);
		desktop.unmount();
		const mobile = show({ header: complete, layout: 'mobile', seasonSelect: seasonSelect() });
		const box = screen.getByRole('combobox');
		expect(screen.getAllByRole('combobox')).toHaveLength(1);
		expect(mobile.container.querySelector('.band')?.contains(box)).toBe(false);
		expect(box.closest('.season-row')).not.toBeNull();
		expect(
			Boolean(
				mobile.container.querySelector('.stage-strip')!.compareDocumentPosition(box) &
				Node.DOCUMENT_POSITION_FOLLOWING
			)
		).toBe(true);
	});

	it('draws the select on desktop and calls onChange with the end year', () => {
		const onChange = vi.fn();
		show({ header: header('playoffs-picture.json'), seasonSelect: seasonSelect(onChange) });
		const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
		expect(select.classList.contains('full')).toBe(false);
		select.value = '2025';
		select.dispatchEvent(new Event('change', { bubbles: true }));
		expect(onChange).toHaveBeenCalledWith(2025);
	});

	it('draws the select full width on mobile', () => {
		show({
			header: header('playoffs-picture.json'),
			layout: 'mobile',
			seasonSelect: seasonSelect()
		});
		expect(screen.getByRole('combobox', { name: 'Season' }).classList.contains('full')).toBe(true);
	});

	it('draws no select without the prop', () => {
		show({ header: header('playoffs-picture.json') });
		expect(screen.queryByRole('combobox')).toBeNull();
	});

	it('draws a four-column strip when the header has four stages', () => {
		const four = header('playoffs-picture.json');
		const { container } = show({ header: { ...four, stages: four.stages.slice(0, 4) } });
		expect(container.querySelector('.stage-strip')?.classList.contains('five')).toBe(false);
	});

	it('draws a five-column strip with five stages', () => {
		const { container } = show({ header: header('playoffs-picture.json') });
		expect(container.querySelector('.stage-strip')?.classList.contains('five')).toBe(true);
	});

	it('puts the first line under the nav on mobile', () => {
		const first = (c: HTMLElement) => c.querySelector('header .first-line');
		const a = show({ layout: 'mobile', header: header('playoffs-bracket.json') });
		expect(a.container.querySelector('header')?.classList.contains('mobile')).toBe(true);
		expect(first(a.container)?.querySelector('.season-line')).not.toBeNull();
		expect(first(a.container)?.querySelector('h1')).toBeNull();
		a.unmount();
		const b = show({ layout: 'mobile', header: null });
		expect(first(b.container)?.querySelector('h1')).not.toBeNull();
		b.unmount();
		const c = show({ layout: 'mobile', header: null, seasonTag: 'Season 2022-23' });
		expect(first(c.container)?.querySelector('h1')).not.toBeNull();
		expect(first(c.container)?.querySelector('.season-line')).toBeNull();
		expect(c.container.querySelector('.lead .season-line')).not.toBeNull();
		c.unmount();
		const d = show({ layout: 'mobile', header: header('playoffs-complete.json') });
		expect(first(d.container)?.querySelector('.label-row')).not.toBeNull();
		expect(d.container.querySelector('.band .stage-strip')).toBeNull();
		expect(d.container.querySelector('.after-inner .stage-strip')).not.toBeNull();
		d.unmount();
		const e = show({ layout: 'desktop', header: header('playoffs-bracket.json') });
		expect(e.container.querySelector('header')?.classList.contains('mobile')).toBe(false);
	});
});
