// web/tests/lib/components/TeamHeader.test.ts
//
// Tests for the TeamHeader component.
//
// Tested:
// - The h1, city, conference line, record, win percentage, the season of the record and cells
// - The two halves of the color strip carry the feed colors as inline backgrounds
// - Only the nav row with no header; the skeleton and aria-busy while loading
// - The Cup line after the conference line, linking to the Cup page; none without the mark
// - Every title after the Cup line, one or more, none for null titles, never a link
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
const STANDINGS = '/standings' as ResolvedPathname;

const header: TeamHeaderView = {
	code: 'OKC',
	city: 'Oklahoma City',
	name: 'Thunder',
	conferenceLine: 'Western Conference · Northwest Division',
	cupLine: null,
	titles: null,
	colors: { primary: '#007AC1', secondary: '#EF3B24' },
	record: '57–25',
	winPct: '69.5%',
	recordSeason: '2025-26 record',
	cells: [
		{ label: 'Conference', value: '1st West', sub: null },
		{ label: 'Streak', value: 'W3', sub: null },
		{ label: 'Last 10', value: '8–2', sub: null },
		{ label: 'Playoffs', value: '1st seed', sub: null }
	]
};

describe('TeamHeader', () => {
	it('shows the name as the h1 with the city and conference line', () => {
		render(TeamHeader, {
			props: {
				header,
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'desktop'
			}
		});
		expect(screen.getByRole('heading', { level: 1, name: 'Thunder' })).toBeTruthy();
		expect(screen.getByText('Oklahoma City')).toBeTruthy();
		expect(screen.getByText('Western Conference · Northwest Division')).toBeTruthy();
		expect(screen.getByText('OKC')).toBeTruthy();
	});

	it('shows the record, win percentage and the cells', () => {
		const { container } = render(TeamHeader, {
			props: {
				header,
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'desktop'
			}
		});
		expect(container.querySelector('.record')?.textContent).toBe('57–25');
		expect(container.querySelector('.win-pct')?.textContent).toBe('69.5%');
		expect(container.querySelector('.record-season')?.textContent).toBe('2025-26 record');
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
		const { container } = render(TeamHeader, {
			props: {
				header,
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'desktop'
			}
		});
		const halves = [...container.querySelectorAll<HTMLElement>('.strip .half')];
		expect(halves.map((half) => half.style.backgroundColor)).toEqual([
			'rgb(0, 122, 193)',
			'rgb(239, 59, 36)'
		]);
	});

	it('shows only the nav row with no header', () => {
		const { container } = render(TeamHeader, {
			props: {
				header: null,
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'desktop'
			}
		});
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
		const cup = screen.getByRole('link', { name: 'Cup' });
		expect(cup.getAttribute('href')).toBe('/cup');
		expect(cup.getAttribute('aria-current')).toBeNull();
		expect(document.querySelector('[aria-current]')).toBeNull();
		expect(container.querySelector('h1')).toBeNull();
		expect(container.querySelector('.skeleton')).toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
	});

	it('shows the skeleton and aria-busy while loading', () => {
		const { container } = render(TeamHeader, {
			props: {
				header: null,
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'desktop',
				loading: true
			}
		});
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.skeleton')?.getAttribute('aria-hidden')).toBe('true');
		expect(container.querySelectorAll('.skeleton .bone').length).toBeGreaterThan(0);
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
	});

	it('is not busy once the header is there', () => {
		const { container } = render(TeamHeader, {
			props: {
				header,
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'desktop',
				loading: true
			}
		});
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
	});

	it('puts the nav links on their own row on a phone', () => {
		const { container } = render(TeamHeader, {
			props: {
				header: null,
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'mobile'
			}
		});
		expect(container.querySelector('nav')?.classList.contains('mobile')).toBe(true);
	});
});

describe('TeamHeader with the Cup mark', () => {
	const props = { allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' as const };

	it('shows the Cup line after the conference line, linking to the Cup page', () => {
		const { container } = render(TeamHeader, {
			props: { ...props, header: { ...header, cupLine: { group: 'West Group B', record: '2-2' } } }
		});
		expect(screen.getByRole('link', { name: 'West Group B · 2-2' }).getAttribute('href')).toBe(
			'/cup'
		);
		const classes = [...(container.querySelector('.identity')?.children ?? [])].map(
			(child) => child.getAttribute('class')?.split(' ')[0]
		);
		expect(classes.slice(-2)).toEqual(['conference-line', 'cup-line']);
	});

	it('shows no Cup line and keeps the identity in order without the mark', () => {
		const { container } = render(TeamHeader, { props: { ...props, header } });
		expect(container.querySelector('.cup-line')).toBeNull();
		expect(screen.queryByRole('link', { name: /Group/ })).toBeNull();
		const classes = [...(container.querySelector('.identity')?.children ?? [])].map(
			(child) => child.getAttribute('class')?.split(' ')[0]
		);
		expect(classes).toEqual(['code-box', 'city', 'name', 'conference-line']);
	});
});

describe('TeamHeader with titles', () => {
	const props = { allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' as const };
	const titles = [
		{ text: '2027 NBA Champions', solid: true },
		{ text: 'West Champions', solid: false }
	];

	it('shows every title after the Cup line, as plain text', () => {
		const { container } = render(TeamHeader, {
			props: {
				...props,
				header: { ...header, cupLine: { group: 'West Group B', record: '2-2' }, titles }
			}
		});
		const badges = [...container.querySelectorAll('.team-titles .title-badge')];
		expect(badges.map((badge) => badge.textContent)).toEqual([
			'2027 NBA Champions',
			'West Champions'
		]);
		expect(container.querySelector('.team-titles a')).toBeNull();
		const classes = [...(container.querySelector('.identity')?.children ?? [])].map(
			(child) => child.getAttribute('class')?.split(' ')[0]
		);
		expect(classes.slice(-2)).toEqual(['cup-line', 'team-titles']);
	});

	it('shows one title', () => {
		const { container } = render(TeamHeader, {
			props: { ...props, header: { ...header, titles: [titles[1]] } }
		});
		expect(container.querySelectorAll('.title-badge').length).toBe(1);
	});

	it('shows no title for null titles and keeps the Cup line in place', () => {
		const { container } = render(TeamHeader, {
			props: { ...props, header: { ...header, cupLine: { group: 'West Group B', record: '2-2' } } }
		});
		expect(container.querySelector('.team-titles')).toBeNull();
		const classes = [...(container.querySelector('.identity')?.children ?? [])].map(
			(child) => child.getAttribute('class')?.split(' ')[0]
		);
		expect(classes.slice(-2)).toEqual(['conference-line', 'cup-line']);
	});
});
