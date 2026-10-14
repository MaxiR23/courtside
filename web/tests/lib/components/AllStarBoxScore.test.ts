// web/tests/lib/components/AllStarBoxScore.test.ts
//
// Tests for the AllStarBoxScore component.
//
// Tested:
// - A tab per All-Star team, the active tab, and switching calls onTab
// - The columns on desktop, and the mobile column order with the sticky player column
// - The starter square, the player name linking to the player, the league monogram linking to /team/{code}
// - No monogram and no team link for a player with no league team
// - The top points accent, the negative plus-minus muted, the totals row
// - The mobile hint, the sticky column class and the short name with the meta line
// - No link for the All-Star team itself
//
// What is covered:
// - Each state the table shows, drawn from the recorded feeds
// - jsdom does not lay out: the mobile table is asserted through its classes and column order
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarBoxScore.test.ts
//
// SEE: web/src/lib/components/AllStarBoxScore.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import AllStarBoxScore from '../../../src/lib/components/AllStarBoxScore.svelte';
import { playerHref, teamHref, viewOf } from '../all-star/views';

const view = viewOf('after');
const box = (id: string) => view.boxes[id]!;
const show = (
	id = 'g1',
	layout: 'desktop' | 'mobile' = 'desktop',
	tab: 'away' | 'home' = 'away',
	onTab = () => {}
) => render(AllStarBoxScore, { props: { box: box(id), tab, onTab, layout, teamHref, playerHref } });

const headers = (container: HTMLElement) =>
	[...container.querySelectorAll('.head .cell')].map((c) => c.textContent?.trim());

describe('AllStarBoxScore', () => {
	it('has a tab per team with the active one selected, and switching calls onTab', async () => {
		const onTab = vi.fn();
		show('g1', 'desktop', 'away', onTab);
		const tabs = screen.getAllByRole('tab');
		expect(tabs.map((t) => t.textContent?.trim())).toEqual(['STR', 'WAV']);
		expect(tabs.map((t) => t.getAttribute('aria-selected'))).toEqual(['true', 'false']);
		await fireEvent.click(tabs[1]);
		expect(onTab).toHaveBeenCalledWith('home');
	});

	it('shows the rows of the selected team', () => {
		const away = show('g1', 'desktop', 'away');
		expect(
			[...away.container.querySelectorAll('.cell.player .name')].map((n) => n.textContent?.trim())
		).toEqual(['Ada Example', 'Ben Sample']);
		const home = show('g1', 'desktop', 'home');
		expect(home.container.querySelectorAll('.row[role=row]').length).toBeGreaterThan(0);
		expect(home.container.textContent).toContain('Cy Placeholder');
	});

	it('draws the desktop columns in the spec order', () => {
		const { container } = show();
		expect(headers(container)).toEqual([
			'#',
			'Player',
			'Pos',
			'Min',
			'Pts',
			'Reb',
			'Ast',
			'Stl',
			'Blk',
			'FG',
			'3P',
			'+/−'
		]);
		expect(container.querySelector('.box-score')?.classList.contains('mobile')).toBe(false);
	});

	it('draws the mobile column order, the hint and a sticky player column', () => {
		const { container } = show('g1', 'mobile');
		expect(headers(container)).toEqual([
			'Player',
			'Pts',
			'Reb',
			'Ast',
			'Min',
			'Stl',
			'Blk',
			'FG',
			'3P',
			'+/−'
		]);
		expect(screen.getByText('Swipe for more columns')).toBeTruthy();
		expect(container.querySelector('.box-score')?.classList.contains('mobile')).toBe(true);
		expect(container.querySelectorAll('.cell.sticky').length).toBeGreaterThan(0);
		expect(container.querySelector('.cell.player .meta')?.textContent).toBe('#7 · G · 10:00');
		expect(container.querySelector('.cell.player .name')?.textContent?.trim()).toBe('A. Example');
	});

	it('has no hint and no sticky column on desktop', () => {
		const { container } = show();
		expect(screen.queryByText('Swipe for more columns')).toBeNull();
		expect(container.querySelector('.cell.sticky')).toBeNull();
	});

	it('draws the starter square only for a starter', () => {
		const { container } = show();
		const rows = [...container.querySelectorAll('.row')].slice(1, 3);
		expect(rows.map((r) => r.querySelector('.cell.player .starter') !== null)).toEqual([
			true,
			false
		]);
	});

	it('links the name to the player and the monogram to the league team', () => {
		const { container } = show();
		expect(screen.getByRole('link', { name: 'Ada Example' }).getAttribute('href')).toBe(
			'/player/1001'
		);
		const monogram = container.querySelector('a.team-monogram.allstar-league');
		expect(monogram?.textContent).toBe('HBR');
		expect(monogram?.getAttribute('href')).toBe('/team/hbr');
		expect(container.querySelector('.league .league-bar')).not.toBeNull();
	});

	it('has no monogram and no team link for a player with no league team', () => {
		const { container } = show('g2');
		const first = container.querySelectorAll('.row')[1];
		expect(first.textContent).toContain('Eli Made-Up');
		expect(first.querySelector('.team-monogram')).toBeNull();
		expect(first.querySelector('.league')).toBeNull();
		expect(first.querySelector('a[href^="/team"]')).toBeNull();
	});

	it('never links an All-Star team', () => {
		const { container } = show();
		expect(container.querySelector('.tabs a')).toBeNull();
		expect(
			[...container.querySelectorAll('a')].every((a) => !a.getAttribute('href')?.includes('str'))
		).toBe(true);
	});

	it('draws the top points in accent and a negative plus-minus muted', () => {
		const { container } = show();
		const rows = [...container.querySelectorAll('.row')].slice(1, 3);
		expect(rows.map((r) => r.querySelector('.cell.points')?.classList.contains('top'))).toEqual([
			true,
			true
		]);
		expect(
			rows.map((r) => r.querySelector('.cell.plusMinus')?.classList.contains('negative'))
		).toEqual([false, true]);
		const home = show('g1', 'desktop', 'home').container;
		const homeRows = [...home.querySelectorAll('.row')].slice(1, 3);
		expect(homeRows.map((r) => r.querySelector('.cell.points')?.classList.contains('top'))).toEqual(
			[true, false]
		);
	});

	it('draws the totals row', () => {
		const { container } = show();
		const totals = container.querySelector('.row.totals')!;
		expect(totals.textContent).toContain('Totals');
		expect(totals.querySelector('.cell.points')?.textContent).toBe('24');
		expect(totals.querySelector('.cell.fieldGoals')?.textContent).toBe('12-18');
	});
});
