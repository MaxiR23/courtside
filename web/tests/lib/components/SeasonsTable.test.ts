// web/tests/lib/components/SeasonsTable.test.ts
//
// Tests for the SeasonsTable component.
//
// Tested:
// - Per game with Regular selected by default, the MIN header present
// - Totals removes MIN and switches the rows; Playoffs shows the playoff rows
// - No Playoffs button without playoff seasons
// - aria-pressed follows the selection
//
// What is covered:
// - Each case, from the recorded player feed through the props layer
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SeasonsTable.test.ts
//
// SEE: web/src/lib/components/SeasonsTable.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import SeasonsTable from '../../../src/lib/components/SeasonsTable.svelte';
import type { PlayerFeed } from '../../../src/lib/contract/player';
import { toPlayerView } from '../../../src/lib/feed/player-props';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const feed = (): PlayerFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'player.json'), 'utf8')
	) as PlayerFeed;

const show = (source: PlayerFeed = feed()) =>
	render(SeasonsTable, {
		props: { seasons: toPlayerView(source).sections.seasons!, gameHref }
	});

const headers = () => screen.getAllByRole('columnheader').map((cell) => cell.textContent);
const rowLabels = () =>
	screen.getAllByRole('rowheader').map((cell) => cell.textContent?.trim().split(/\s+/)[0]);

describe('SeasonsTable', () => {
	it('starts on Per game and Regular, with the MIN column', () => {
		show();
		expect(headers()).toContain('MIN');
		expect(rowLabels()).toEqual(['2025-26', '2024-25', '2018-19', 'Career']);
		expect(screen.getByRole('button', { name: 'Per game' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getByRole('button', { name: 'Regular' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getByText('LAC · OKC')).toBeTruthy();
	});

	it('removes MIN and switches the rows with Totals', async () => {
		show();
		await fireEvent.click(screen.getByRole('button', { name: 'Totals' }));
		expect(headers()).not.toContain('MIN');
		expect(screen.getByRole('button', { name: 'Totals' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getByRole('button', { name: 'Per game' }).getAttribute('aria-pressed')).toBe(
			'false'
		);
		expect(screen.getAllByText('650–1,300').length).toBeGreaterThan(0);
	});

	it('shows the playoff rows with Playoffs', async () => {
		show();
		await fireEvent.click(screen.getByRole('button', { name: 'Playoffs' }));
		expect(rowLabels()).toEqual(['2024-25', 'Career']);
		expect(screen.getByRole('button', { name: 'Playoffs' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
	});

	it('has no Playoffs button without playoff seasons', () => {
		const source = feed();
		source.seasons.playoffs = { perGame: [], totals: [], career: null };
		show(source);
		expect(screen.queryByRole('button', { name: 'Playoffs' })).toBeNull();
		expect(screen.queryByRole('group', { name: 'Season type' })).toBeNull();
	});
});
