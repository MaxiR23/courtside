// web/tests/lib/components/CupGames.test.ts
//
// Tests for the CupGames component.
//
// Tested:
// - The chips in order with their counts; All pressed by default
// - Choosing a chip shows only that round's days; the day headings
// - A round with no games shows an empty list
//
// What is covered:
// - The selection, the rows under each day, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/CupGames.test.ts
//
// SEE: web/src/lib/components/CupGames.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CupFeed } from '../../../src/lib/contract/cup';
import { toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';
import CupGames from '../../../src/lib/components/CupGames.svelte';
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;

const feed = (): CupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'cup.json'), 'utf8')
	) as CupFeed;
const view = (source: CupFeed = feed()) => toCupView(source);

afterEach(() => {
	vi.restoreAllMocks();
});

const show = () =>
	render(CupGames, { props: { filters: view().filters, layout: 'desktop' as const, gameHref } });
const chips = () => screen.getAllByRole('button');

describe('CupGames', () => {
	it('shows the chips in order with their counts, All pressed', () => {
		show();
		expect(screen.getByRole('group', { name: 'Filter Cup games' })).toBeTruthy();
		expect(chips().map((c) => c.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			'All 6',
			'Group play 5',
			'Quarterfinals 0',
			'Semifinals 0',
			'Championship 1'
		]);
		expect(chips().map((c) => c.getAttribute('aria-pressed'))).toEqual([
			'true',
			'false',
			'false',
			'false',
			'false'
		]);
	});

	it('shows every day under All', () => {
		const { container } = show();
		expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
			'Wednesday, November 4',
			'Saturday, November 7',
			'Wednesday, December 16'
		]);
		expect(container.querySelectorAll('li')).toHaveLength(6);
	});

	it('shows only the days of the chosen round', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: /Championship/ }));
		expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
			'Wednesday, December 16'
		]);
		expect(container.querySelectorAll('li')).toHaveLength(1);
		expect(screen.getByRole('button', { name: /Championship/ }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getByRole('button', { name: /All/ }).getAttribute('aria-pressed')).toBe('false');
	});

	it('shows an empty list for a round with no games', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: /Semifinals/ }));
		expect(screen.queryAllByRole('heading', { level: 3 })).toHaveLength(0);
		expect(container.querySelectorAll('li')).toHaveLength(0);
	});

	it('shows Spanish copy', () => {
		preferLanguages(['es-ES']);
		show();
		expect(screen.getByRole('group', { name: 'Filtrar partidos de la Copa' })).toBeTruthy();
		expect(screen.getByRole('button', { name: /Todos/ })).toBeTruthy();
	});
});
