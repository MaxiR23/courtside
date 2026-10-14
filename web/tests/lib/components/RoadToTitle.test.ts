// web/tests/lib/components/RoadToTitle.test.ts
//
// Tests for the RoadToTitle component.
//
// Tested:
// - Two cards with the name, the seed line and the postseason record
// - The series rows with round, opponent seed, opponent and result; a loss muted
// - Fewer rows when a path has fewer series; — for a missing record
//
// What is covered:
// - Each state the section shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/RoadToTitle.test.ts
//
// SEE: web/src/lib/components/RoadToTitle.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../../../src/lib/contract/playoffs-finals';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import RoadToTitle from '../../../src/lib/components/RoadToTitle.svelte';

const read = <T>(file: string): T =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', file), 'utf8')) as T;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const show = (change: (f: PlayoffsFinalsFeed) => void = () => {}) => {
	const finals = read<PlayoffsFinalsFeed>('playoffs-finals.json');
	change(finals);
	const road = toPlayoffsView(read<PlayoffsFeed>('playoffs-complete.json'), finals).road;
	return render(RoadToTitle, { props: { road, teamHref } });
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('RoadToTitle', () => {
	it('draws two cards with the name, the seed line and the postseason record', () => {
		const { container } = show();
		const cards = [...container.querySelectorAll('.finalist')];
		expect(cards).toHaveLength(2);
		expect(cards[0]!.querySelector('.name')?.textContent).toBe('Harbor Owls');
		expect(cards[0]!.querySelector('.seed-line')?.textContent).toBe('#1 seed · 64-18');
		expect(cards[0]!.querySelector('.postseason')?.textContent).toBe('16-6');
		expect(cards[1]!.querySelector('.postseason')?.textContent).toBe('—');
	});

	it('draws a row per series with round, seed, opponent and result', () => {
		const { container } = show();
		const rows = [...container.querySelectorAll('.finalist')[0]!.querySelectorAll('.row')];
		expect(rows).toHaveLength(4);
		expect(rows.map((r) => r.querySelector('.round')?.textContent)).toEqual([
			'Round 1',
			'Conference semifinals',
			'Conference finals',
			'NBA Finals'
		]);
		expect(rows[0]!.querySelector('.seed')?.textContent).toBe('#8');
		expect(rows[0]!.querySelector('.result')?.textContent).toBe('4–0 W');
		expect(screen.getAllByRole('link', { name: 'Bison' })[0]?.getAttribute('href')).toBe(
			'/team/qxh'
		);
	});

	it('mutes a lost series and draws fewer rows for a shorter path', () => {
		const { container } = show((f) => (f.road[1]!.series[2]!.result = 'loss'));
		const second = container.querySelectorAll('.finalist')[1]!;
		const rows = [...second.querySelectorAll('.row')];
		expect(rows).toHaveLength(3);
		expect(rows.map((r) => r.classList.contains('loss'))).toEqual([false, false, true]);
	});
});
