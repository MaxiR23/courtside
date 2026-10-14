// web/tests/lib/components/PostseasonAverages.test.ts
//
// Tests for the PostseasonAverages component.
//
// Tested:
// - A tab per finalist, the first pressed; clicking a tab switches the roster
// - A row per player with PTS, REB, AST, BLK and FG%; — for a player without stats, last
//
// What is covered:
// - Each state the table shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PostseasonAverages.test.ts
//
// SEE: web/src/lib/components/PostseasonAverages.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../../../src/lib/contract/playoffs-finals';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import PostseasonAverages from '../../../src/lib/components/PostseasonAverages.svelte';

const read = <T>(file: string): T =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', file), 'utf8')) as T;
const averages = () =>
	toPlayoffsView(
		read<PlayoffsFeed>('playoffs-complete.json'),
		read<PlayoffsFinalsFeed>('playoffs-finals.json')
	).headToHead!.averages;
const rows = (container: HTMLElement) =>
	[...container.querySelectorAll('.row.body')].map((r) =>
		[...r.querySelectorAll('.cell')].map((c) => (c.querySelector('.name') ?? c).textContent?.trim())
	);

afterEach(() => {
	vi.restoreAllMocks();
});

describe('PostseasonAverages', () => {
	it('draws a tab per finalist with the first pressed', () => {
		render(PostseasonAverages, { props: { averages: averages() } });
		const tabs = screen.getAllByRole('button');
		expect(tabs.map((t) => [t.textContent?.trim(), t.getAttribute('aria-pressed')])).toEqual([
			['QXA', 'true'],
			['QYA', 'false']
		]);
	});

	it('draws a row per player with — for a player without stats, last', () => {
		const { container } = render(PostseasonAverages, { props: { averages: averages() } });
		expect(rows(container)).toEqual([
			['Kai Lowe', '27.5', '8.2', '6.8', '1.2', '51.2%'],
			['Lou Marsh', '15.0', '4.0', '3.5', '0.4', '44.0%'],
			['Ned Oakes', '—', '—', '—', '—', '—']
		]);
		expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
			'Player',
			'PTS',
			'REB',
			'AST',
			'BLK',
			'FG%'
		]);
	});

	it('switches the roster when a tab is clicked', async () => {
		const { container } = render(PostseasonAverages, { props: { averages: averages() } });
		await fireEvent.click(screen.getByRole('button', { name: 'QYA' }));
		expect(screen.getByRole('button', { name: 'QYA' }).getAttribute('aria-pressed')).toBe('true');
		expect(rows(container)).toEqual([['Moe Nash', '22.0', '10.1', '3.2', '2.0', '47.0%']]);
	});
});
