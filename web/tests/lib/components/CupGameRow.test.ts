// web/tests/lib/components/CupGameRow.test.ts
//
// Tests for the CupGameRow component.
//
// Tested:
// - A final row: scores, the loser dimmed
// - A scheduled row with its time and broadcast, and without a broadcast
// - The live badge and the postponed status; the not counted tag
// - A link to gameHref only when the game is linked; the mobile class
//
// What is covered:
// - Each status a row can show, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/CupGameRow.test.ts
//
// SEE: web/src/lib/components/CupGameRow.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CupFeed } from '../../../src/lib/contract/cup';
import { toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';
import CupGameRow from '../../../src/lib/components/CupGameRow.svelte';
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;

const feed = (): CupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'cup.json'), 'utf8')
	) as CupFeed;
const view = (source: CupFeed = feed()) => toCupView(source);

afterEach(() => {
	vi.restoreAllMocks();
});

const games = () => view().filters[0]!.days.flatMap((d) => d.games);
const show = (index: number, layout: 'desktop' | 'mobile' = 'desktop') =>
	render(CupGameRow, { props: { game: games()[index]!, layout, gameHref } });

describe('CupGameRow', () => {
	it('shows a final row with both scores and the loser dimmed', () => {
		const { container } = show(0);
		expect(container.textContent).toContain('Group play');
		expect(screen.getByText('98')).toBeTruthy();
		expect(screen.getByText('110')).toBeTruthy();
		const sides = [...container.querySelectorAll('.side')];
		expect(sides.map((s) => s.classList.contains('loser'))).toEqual([true, false]);
		expect(screen.getByText('Final')).toBeTruthy();
		expect(screen.getByText('Courtside TV')).toBeTruthy();
	});

	it('shows a scheduled row with its time and broadcast', () => {
		show(2);
		expect(screen.getByText('7:00 PM')).toBeTruthy();
		expect(screen.getByText('Courtside TV')).toBeTruthy();
	});

	it('shows a scheduled row without a broadcast', () => {
		const { container } = show(3);
		expect(screen.getByText('9:30 PM')).toBeTruthy();
		expect(container.querySelector('.broadcast')).toBeNull();
		expect(container.querySelectorAll('.score')).toHaveLength(0);
	});

	it('shows the live badge for a live game', () => {
		show(1);
		expect(screen.getByText('LIVE')).toBeTruthy();
	});

	it('shows the postponed status', () => {
		show(4);
		expect(screen.getByText('Postponed')).toBeTruthy();
	});

	it('shows the not counted tag on the championship', () => {
		show(5);
		expect(screen.getByText('Not counted in standings')).toBeTruthy();
		expect(screen.getByText('Championship')).toBeTruthy();
	});

	it('links to the game page only when the game is linked', () => {
		const linked = show(0);
		expect(screen.getByRole('link').getAttribute('href')).toBe('/game/9000001');
		linked.unmount();
		const plain = show(2);
		expect(screen.queryByRole('link')).toBeNull();
		expect(plain.container.querySelector('div.cup-game-row')).not.toBeNull();
	});

	it('adds the mobile class only with the mobile layout', () => {
		const desktop = show(0);
		expect(desktop.container.querySelector('.cup-game-row')?.classList.contains('mobile')).toBe(
			false
		);
		desktop.unmount();
		const mobile = show(0, 'mobile');
		expect(mobile.container.querySelector('.cup-game-row')?.classList.contains('mobile')).toBe(
			true
		);
	});

	it('shows Spanish copy', () => {
		preferLanguages(['es-ES']);
		show(5);
		expect(screen.getByText('No cuenta en la clasificación')).toBeTruthy();
	});
});
