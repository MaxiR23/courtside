// web/tests/lib/components/GameLog.test.ts
//
// Tests for the GameLog component.
//
// Tested:
// - All selected by default, with every chip that has rows and none without
// - Regular season, NBA Cup and Playoffs show their rows
// - 20 of 25 rows with Show all 25 games; clicking shows all and Show fewer with aria-expanded
// - Changing the chip collapses the list; no toggle with 20 rows or fewer
// - Links only on linked rows
//
// What is covered:
// - Each case, from props built for the test
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/GameLog.test.ts
//
// SEE: web/src/lib/components/GameLog.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import GameLog from '../../../src/lib/components/GameLog.svelte';
import type { GameLogSection, StatRowView } from '../../../src/lib/player/types';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;

const rowsOf = (prefix: string, count: number): StatRowView[] =>
	Array.from({ length: count }, (_, i) => ({
		key: `${prefix}-${i}`,
		label: `${prefix} ${i}`,
		sub: null,
		link: { gameId: `${prefix}-${i}`, linked: i === 0 },
		cells: [{ mark: 'W', win: true, text: '100–90' }, '30']
	}));

const log = (all = 25): GameLogSection => ({
	meta: '2025-26',
	columns: [
		{ key: 'result', label: 'Result', wide: true },
		{ key: 'min', label: 'MIN', muted: true }
	],
	filters: [
		{ id: 'all', label: 'All', rows: rowsOf('all', all) },
		{ id: 'regular', label: 'Regular season', rows: rowsOf('reg', 3) },
		{ id: 'playoffs', label: 'Playoffs', rows: rowsOf('po', 2) }
	]
});

const show = (section: GameLogSection) => render(GameLog, { props: { log: section, gameHref } });

const bodyRows = () => screen.getAllByRole('row').length - 1;

describe('GameLog', () => {
	it('selects All and lists only the chips with rows', () => {
		show(log());
		const chips = screen.getAllByRole('button').filter((b) => b.classList.contains('chip'));
		expect(chips.map((b) => b.textContent?.trim())).toEqual([
			'All',
			'Regular season',
			'Playoffs',
			'Show all 25 games'
		]);
		expect(screen.getByRole('button', { name: 'All' }).getAttribute('aria-pressed')).toBe('true');
		expect(screen.queryByRole('button', { name: 'NBA Cup' })).toBeNull();
	});

	it('shows the rows of the chosen chip', async () => {
		show(log());
		await fireEvent.click(screen.getByRole('button', { name: 'Regular season' }));
		expect(bodyRows()).toBe(3);
		await fireEvent.click(screen.getByRole('button', { name: 'Playoffs' }));
		expect(bodyRows()).toBe(2);
		expect(screen.getByRole('button', { name: 'Playoffs' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
	});

	it('shows 20 of 25 rows, then all of them and Show fewer when expanded', async () => {
		show(log());
		expect(bodyRows()).toBe(20);
		const toggle = screen.getByRole('button', { name: 'Show all 25 games' });
		expect(toggle.getAttribute('aria-expanded')).toBe('false');
		await fireEvent.click(toggle);
		expect(bodyRows()).toBe(25);
		const fewer = screen.getByRole('button', { name: 'Show fewer' });
		expect(fewer.getAttribute('aria-expanded')).toBe('true');
		await fireEvent.click(fewer);
		expect(bodyRows()).toBe(20);
	});

	it('collapses the list when the chip changes', async () => {
		show(log());
		await fireEvent.click(screen.getByRole('button', { name: 'Show all 25 games' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Regular season' }));
		await fireEvent.click(screen.getByRole('button', { name: 'All' }));
		expect(bodyRows()).toBe(20);
		expect(screen.getByRole('button', { name: 'Show all 25 games' })).toBeTruthy();
	});

	it('has no toggle with 20 rows or fewer', () => {
		show(log(20));
		expect(bodyRows()).toBe(20);
		expect(screen.queryByRole('button', { name: /Show/ })).toBeNull();
	});

	it('links only the linked rows', () => {
		show(log(3));
		expect(screen.getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual(['/game/all-0']);
	});
});
