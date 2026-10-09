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
	status: { label: 'Active', injured: false },
	firstName: 'Shai',
	lastName: 'Gilgeous-Alexander',
	line: '#2 · Guard · Oklahoma City Thunder',
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
		props: { allGamesHref: HOME, standingsHref: STANDINGS, layout: 'desktop', ...props }
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

	it('shows only the nav row with a null header', () => {
		const { container } = show({ header: null });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
		expect(container.querySelector('h1')).toBeNull();
		expect(container.querySelector('.bone')).toBeNull();
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
		expect(document.querySelector('[aria-current]')).toBeNull();
	});

	it('puts the nav links on their own row on a phone', () => {
		const { container } = render(PlayerHeader, {
			props: { header: null, allGamesHref: HOME, standingsHref: STANDINGS, layout: 'mobile' }
		});
		expect(container.querySelector('nav')?.classList.contains('mobile')).toBe(true);
	});
});
