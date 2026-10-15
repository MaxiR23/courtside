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
// - Four stages draw a four-column strip
// - Spanish copy
//
// What is covered:
// - Each state the header shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayoffsHeader.test.ts
//
// SEE: web/src/lib/components/PlayoffsHeader.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
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
	it('draws the nav with Playoffs current', () => {
		show({ header: header('playoffs-picture.json') });
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
			[...li.querySelectorAll('span')].map((s) => s.textContent)
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
		show({ header: header('playoffs-complete.json'), showRelive: true });
		expect(screen.getByRole('heading', { level: 1, name: 'Champions' })).toBeTruthy();
		expect(screen.queryByRole('heading', { level: 1, name: 'Playoffs' })).toBeNull();
		expect(screen.getByRole('button', { name: 'Relive the series' })).toBeTruthy();
		expect(screen.getAllByText('Complete').length).toBeGreaterThan(0);
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
});
