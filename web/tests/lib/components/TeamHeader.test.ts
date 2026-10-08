// web/tests/lib/components/TeamHeader.test.ts
//
// Tests for the TeamHeader component.
//
// Tested:
// - The h1, city, conference line, record, win percentage and cells
// - The two halves of the color strip carry the feed colors as inline backgrounds
// - Only the nav row with no header; the skeleton and aria-busy while loading
//
// What is covered:
// - Each state the header shows
// - Colors are read from the inline style; jsdom does not lay anything out
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamHeader.test.ts
//
// SEE: web/src/lib/components/TeamHeader.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamHeader from '../../../src/lib/components/TeamHeader.svelte';
import type { TeamHeaderView } from '../../../src/lib/team/types';

const HOME = '/' as ResolvedPathname;

const header: TeamHeaderView = {
	code: 'OKC',
	city: 'Oklahoma City',
	name: 'Thunder',
	conferenceLine: 'Western Conference · Northwest Division',
	colors: { primary: '#007AC1', secondary: '#EF3B24' },
	record: '57–25',
	winPct: '69.5%',
	cells: [
		{ label: 'Conference', value: '1st West', sub: null },
		{ label: 'Streak', value: 'W3', sub: null },
		{ label: 'Last 10', value: '8–2', sub: null },
		{ label: 'Playoffs', value: '1st seed', sub: null }
	]
};

describe('TeamHeader', () => {
	it('shows the name as the h1 with the city and conference line', () => {
		render(TeamHeader, { props: { header, allGamesHref: HOME } });
		expect(screen.getByRole('heading', { level: 1, name: 'Thunder' })).toBeTruthy();
		expect(screen.getByText('Oklahoma City')).toBeTruthy();
		expect(screen.getByText('Western Conference · Northwest Division')).toBeTruthy();
		expect(screen.getByText('OKC')).toBeTruthy();
	});

	it('shows the record, win percentage and the cells', () => {
		const { container } = render(TeamHeader, { props: { header, allGamesHref: HOME } });
		expect(container.querySelector('.record')?.textContent).toBe('57–25');
		expect(container.querySelector('.win-pct')?.textContent).toBe('69.5%');
		const cells = [...container.querySelectorAll('.cell')].map((cell) =>
			[...cell.querySelectorAll('span')].map((span) => span.textContent)
		);
		expect(cells).toEqual([
			['Conference', '1st West'],
			['Streak', 'W3'],
			['Last 10', '8–2'],
			['Playoffs', '1st seed']
		]);
	});

	it('draws the color strip with the feed colors as inline backgrounds', () => {
		const { container } = render(TeamHeader, { props: { header, allGamesHref: HOME } });
		const halves = [...container.querySelectorAll<HTMLElement>('.strip .half')];
		expect(halves.map((half) => half.style.backgroundColor)).toEqual([
			'rgb(0, 122, 193)',
			'rgb(239, 59, 36)'
		]);
	});

	it('shows only the nav row with no header', () => {
		const { container } = render(TeamHeader, { props: { header: null, allGamesHref: HOME } });
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
		expect(container.querySelector('h1')).toBeNull();
		expect(container.querySelector('.skeleton')).toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
	});

	it('shows the skeleton and aria-busy while loading', () => {
		const { container } = render(TeamHeader, {
			props: { header: null, allGamesHref: HOME, loading: true }
		});
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.skeleton')?.getAttribute('aria-hidden')).toBe('true');
		expect(container.querySelectorAll('.skeleton .bone').length).toBeGreaterThan(0);
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
	});

	it('is not busy once the header is there', () => {
		const { container } = render(TeamHeader, {
			props: { header, allGamesHref: HOME, loading: true }
		});
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
	});
});
