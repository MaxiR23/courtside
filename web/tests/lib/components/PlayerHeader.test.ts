// web/tests/lib/components/PlayerHeader.test.ts
//
// Tests for the PlayerHeader component.
//
// Tested:
// - The first name, the h1 last name, the line, the team tag and Active
// - Injured: the accent status tag and the injury card with comment and updated text
// - The photo with a URL; no photo block without one or after a load error
// - The four stat cells; no stats block with null stats
// - Loading: aria-busy and the bones; a null header shows only the nav row
// - The All-Star tag in the tags when the header has one, none without it, and it is not a link
// - The season tag when the header has one; the select on desktop and mobile, with no header, and its onChange; none without the prop
// - A null status draws no status tag
// - The team mark: the feed logo before the code tag, the monogram for a null logo and the season code of a past team, none without a team
//
// What is covered:
// - Each state, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayerHeader.test.ts
//
// SEE: web/src/lib/components/PlayerHeader.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import PlayerHeader from '../../../src/lib/components/PlayerHeader.svelte';
import type { PlayerHeaderView } from '../../../src/lib/player/types';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;

const header: PlayerHeaderView = {
	teamCode: 'OKC',
	team: null,
	status: { label: 'Active', injured: false },
	firstName: 'Shai',
	lastName: 'Gilgeous-Alexander',
	line: '#2 · Guard · Oklahoma City Thunder',
	allStarTag: null,
	injury: null,
	photo: 'https://example.com/players/p-2.png',
	stats: {
		label: '2025-26 · per game',
		cells: [
			{ label: 'Points', value: '31.8', sub: '1st in NBA' },
			{ label: 'Rebounds', value: '4.9', sub: null },
			{ label: 'Assists', value: '6.4', sub: '5th in NBA' },
			{ label: 'FG%', value: '47.3%', sub: '12th in NBA' }
		]
	}
};

const show = (props: { header: PlayerHeaderView | null; loading?: boolean }) =>
	render(PlayerHeader, {
		props: {
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout: 'desktop',
			...props
		}
	});

describe('PlayerHeader', () => {
	it('shows the names, the line, the team tag and Active', () => {
		show({ header });
		expect(screen.getByText('Shai')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'Gilgeous-Alexander' })).toBeTruthy();
		expect(screen.getByText('#2 · Guard · Oklahoma City Thunder')).toBeTruthy();
		expect(screen.getByText('OKC')).toBeTruthy();
		expect(screen.getByText('Active').classList.contains('out')).toBe(false);
	});

	it('shows the injury status in accent and the injury card', () => {
		show({
			header: {
				...header,
				status: { label: 'Questionable', injured: true },
				injury: {
					status: 'questionable',
					comment: 'Left ankle sprain',
					updated: 'Updated Oct 7 · 3:15 PM ET'
				}
			}
		});
		const tags = screen.getAllByText('Questionable');
		expect(tags).toHaveLength(2);
		expect(tags[0]?.classList.contains('out')).toBe(true);
		expect(screen.getByText('Left ankle sprain')).toBeTruthy();
		expect(screen.getByText('Updated Oct 7 · 3:15 PM ET')).toBeTruthy();
	});

	it('shows no comment line for a null comment', () => {
		const { container } = show({
			header: {
				...header,
				injury: { status: 'out', comment: null, updated: 'Updated Oct 7 · 3:15 PM ET' }
			}
		});
		expect(container.querySelector('.comment')).toBeNull();
	});

	it('renders the photo with a URL', () => {
		const { container } = show({ header });
		expect(container.querySelector('.photo img')?.getAttribute('src')).toBe(
			'https://example.com/players/p-2.png'
		);
	});

	it('renders no photo block without a URL', () => {
		const { container } = show({ header: { ...header, photo: null } });
		expect(container.querySelector('.photo')).toBeNull();
	});

	it('renders no photo block after the image fails to load', async () => {
		const { container } = show({ header });
		await fireEvent.error(container.querySelector('.photo img') as HTMLElement);
		expect(container.querySelector('.photo')).toBeNull();
	});

	it('shows the four stat cells with labels, values and sub-lines', () => {
		const { container } = show({ header });
		expect(screen.getByText('2025-26 · per game')).toBeTruthy();
		const cells = [...container.querySelectorAll('.stats .cell')];
		expect(cells.map((c) => c.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			'Points 31.8 1st in NBA',
			'Rebounds 4.9',
			'Assists 6.4 5th in NBA',
			'FG% 47.3% 12th in NBA'
		]);
	});

	it('shows no stats block with null stats', () => {
		const { container } = show({ header: { ...header, stats: null } });
		expect(container.querySelector('.stats')).toBeNull();
	});

	it('shows the skeleton with aria-busy while loading', () => {
		const { container } = show({ header: null, loading: true });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelectorAll('.bone').length).toBeGreaterThan(0);
	});

	it('shows only the nav row with a null header', async () => {
		const { container } = show({ header: null });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
		expect(container.querySelector('h1')).toBeNull();
		expect(container.querySelector('.bone')).toBeNull();
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		const cup = screen.getByRole('link', { name: 'Cup' });
		expect(cup.getAttribute('href')).toBe('/cup');
		expect(cup.getAttribute('aria-current')).toBeNull();
		expect(document.querySelector('[aria-current]')).toBeNull();
	});

	it('puts the nav links on their own row on a phone', () => {
		const { container } = render(PlayerHeader, {
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

describe('PlayerHeader with the All-Star tag', () => {
	it('shows the tag in the tags row', () => {
		const { container } = show({ header: { ...header, allStarTag: 'All-Star 2027' } });
		expect(container.querySelector('.tags')?.textContent).toContain('All-Star 2027');
		expect(container.querySelector('.allstar-tag')?.textContent).toBe('All-Star 2027');
	});

	it('shows no tag without it', () => {
		const { container } = show({ header });
		expect(container.querySelector('.allstar-mark')).toBeNull();
	});

	it('draws the tag as plain text, not a link', () => {
		const { container } = show({ header: { ...header, allStarTag: 'All-Star 2027' } });
		expect(container.querySelector('.allstar-mark a, .allstar-mark button')).toBeNull();
	});
});

describe('PlayerHeader season selector and tag', () => {
	const seasonSelect = (onChange: (season: number) => void = () => {}) => ({
		seasons: [
			{ season: 2027, seasonLabel: '2026-27' },
			{ season: 2005, seasonLabel: '2004-05' }
		],
		value: 2027,
		onChange
	});

	it('draws the season tag only when the header has one', () => {
		const { unmount } = render(PlayerHeader, {
			props: {
				header: { ...header, tag: 'Season 2004-05' },
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout: 'desktop'
			}
		});
		expect(screen.getByText('Season 2004-05')).toBeTruthy();
		unmount();
		render(PlayerHeader, {
			props: { header, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' as const }
		});
		expect(screen.queryByText('Season 2004-05')).toBeNull();
	});

	it('draws the select on desktop without the full class and calls onChange with the end year', () => {
		const calls: number[] = [];
		const onChange = (season: number) => calls.push(season);
		render(PlayerHeader, {
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
		render(PlayerHeader, {
			props: {
				...{ header, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' as const },
				layout: 'mobile',
				seasonSelect: seasonSelect()
			}
		});
		expect(screen.getByRole('combobox', { name: 'Season' }).classList.contains('full')).toBe(true);
	});

	it('draws the select with no header, loading or not', () => {
		render(PlayerHeader, {
			props: {
				...{ header, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' as const },
				header: null,
				seasonSelect: seasonSelect()
			}
		});
		expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
	});

	it('draws no select without the prop', () => {
		render(PlayerHeader, {
			props: { header, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop' as const }
		});
		expect(screen.queryByRole('combobox')).toBeNull();
	});
});

describe('PlayerHeader with no status', () => {
	it('draws the team tag and no status tag', () => {
		show({ header: { ...header, status: null } });
		expect(screen.getByText('OKC')).toBeTruthy();
		expect(screen.queryByText('Active')).toBeNull();
	});
});

describe('PlayerHeader team mark', () => {
	const team = { code: 'OKC', name: 'Thunder', city: 'Oklahoma City', guest: false };
	const logo = {
		light: 'https://example.com/okc-light.svg',
		dark: 'https://example.com/okc-dark.svg'
	};

	it('draws the team logo before the code tag, hidden', () => {
		const { container } = show({ header: { ...header, team: { ...team, logo } } });
		const mark = container.querySelector('.tags .team-monogram.inline');
		expect(mark?.querySelector('img')?.getAttribute('src')).toBe(
			'https://example.com/okc-dark.svg'
		);
		expect(mark?.nextElementSibling?.textContent).toBe('OKC');
	});

	it('draws the monogram of a team with a null logo, and of a past team its season code', () => {
		const plain = show({ header: { ...header, team } });
		expect(plain.container.querySelector('.tags .team-monogram')?.textContent).toBe('OKC');
		plain.unmount();
		const past = show({ header: { ...header, team: { ...team, historicalCode: 'SEA' } } });
		expect(past.container.querySelector('.tags .team-monogram')?.textContent).toBe('SEA');
	});

	it('draws no mark without a team', () => {
		const { container } = show({ header });
		expect(container.querySelector('.tags .team-monogram')).toBeNull();
	});
});
