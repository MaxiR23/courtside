// web/tests/lib/components/TeamHeader.test.ts
//
// Tests for the TeamHeader component.
//
// Tested:
// - The h1, city, conference line, record, win percentage, the season of the record and cells
// - The two halves of the color strip carry the feed colors as inline backgrounds; a historical identity (null colors) draws the season code and no strip (ADR 0054)
// - The box draws the feed logo in the team size with the strip still drawn; a null logo draws the code
// - The season tag stays on the unavailable state (no header, a seasonTag) and the skeleton wins while loading
// - Only the nav row with no header; the skeleton and aria-busy while loading
// - The Cup line after the conference line, linking to the Cup page; none without the mark
// - Every title after the Cup line, one or more, none for null titles, never a link
// - The season tag when the header has one; the select on desktop and mobile, with no header, and its onChange; none without the prop
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
	team: { code: 'OKC', name: 'Thunder', city: 'Oklahoma City', guest: false },
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

	it('draws the season code in the box and no strip for a historical identity', () => {
		const { container } = render(TeamHeader, {
			props: {
				header: { ...header, team: { ...header.team, historicalCode: 'SEA' }, colors: null },
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'desktop'
			}
		});
		expect(container.querySelector('.team-monogram')?.textContent).toBe('SEA');
		expect(container.querySelector('.strip')).toBeNull();
	});

	it('keeps the season tag with no header when a season tag is given', () => {
		render(TeamHeader, {
			props: {
				header: null,
				seasonTag: 'Season 2022-23',
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'desktop'
			}
		});
		expect(screen.getByText('Season 2022-23')).toBeTruthy();
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

describe('TeamHeader season selector and tag', () => {
	const seasonSelect = (onChange: (season: number) => void = () => {}) => ({
		seasons: [
			{ season: 2027, seasonLabel: '2026-27' },
			{ season: 2005, seasonLabel: '2004-05' }
		],
		value: 2027,
		onChange
	});

	it('draws the season tag only when the header has one', () => {
		const { unmount } = render(TeamHeader, {
			props: {
				header: { ...header, tag: 'Season 2004-05' },
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'desktop'
			}
		});
		expect(screen.getByText('Season 2004-05')).toBeTruthy();
		unmount();
		render(TeamHeader, {
			props: { header, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' as const }
		});
		expect(screen.queryByText('Season 2004-05')).toBeNull();
	});

	it('draws the select on desktop without the full class and calls onChange with the end year', () => {
		const calls: number[] = [];
		const onChange = (season: number) => calls.push(season);
		render(TeamHeader, {
			props: {
				...{ header, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' as const },
				layout: 'desktop',
				seasonSelect: seasonSelect(onChange)
			}
		});
		const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
		expect([...select.options].map((option) => option.textContent)).toEqual(['2026-27', '2004-05']);
		expect(select.classList.contains('full')).toBe(false);
		select.value = '2005';
		select.dispatchEvent(new Event('change', { bubbles: true }));
		expect(calls).toEqual([2005]);
	});

	it('draws the select full width on mobile', () => {
		render(TeamHeader, {
			props: {
				...{ header, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' as const },
				layout: 'mobile',
				seasonSelect: seasonSelect()
			}
		});
		expect(screen.getByRole('combobox', { name: 'Season' }).classList.contains('full')).toBe(true);
	});

	it('draws the select with no header, loading or not', () => {
		render(TeamHeader, {
			props: {
				...{ header, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' as const },
				header: null,
				seasonSelect: seasonSelect()
			}
		});
		expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
	});

	it('draws no select without the prop', () => {
		render(TeamHeader, {
			props: { header, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' as const }
		});
		expect(screen.queryByRole('combobox')).toBeNull();
	});
});

describe('TeamHeader logo', () => {
	const show = (view: TeamHeaderView) =>
		render(TeamHeader, {
			props: { header: view, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' }
		});

	it('draws the logo in the team box, hidden, and keeps the strip', () => {
		const logo = {
			light: 'https://example.com/okc-light.svg',
			dark: 'https://example.com/okc-dark.svg'
		};
		const { container } = show({ ...header, team: { ...header.team, logo } });
		const box = container.querySelector('.team-monogram.team');
		expect(box?.querySelector('img')?.getAttribute('src')).toBe('https://example.com/okc-dark.svg');
		expect(box?.querySelector('img')?.getAttribute('aria-hidden')).toBe('true');
		expect(container.querySelectorAll('.strip .half')).toHaveLength(2);
	});

	it('draws the code with a null logo', () => {
		const { container } = show(header);
		const box = container.querySelector('.team-monogram.team');
		expect(box?.querySelector('img')).toBeNull();
		expect(box?.textContent).toBe('OKC');
	});
});
