// web/tests/lib/components/HeadToHead.test.ts
//
// Tests for the HeadToHead component.
//
// Tested:
// - The record row with both finalists
// - Eight bars in the feed's order
// - The postseason averages below the bars
//
// What is covered:
// - Each part of the section, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/HeadToHead.test.ts
//
// SEE: web/src/lib/components/HeadToHead.svelte
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../../../src/lib/contract/playoffs-finals';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import HeadToHead from '../../../src/lib/components/HeadToHead.svelte';

const read = <T>(file: string): T =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', file), 'utf8')) as T;
const headToHead = () =>
	toPlayoffsView(
		read<PlayoffsFeed>('playoffs-complete.json'),
		read<PlayoffsFinalsFeed>('playoffs-finals.json')
	).headToHead!;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('HeadToHead', () => {
	it('draws the record row with both finalists', () => {
		const { container } = render(HeadToHead, { props: { headToHead: headToHead() } });
		expect(
			[...container.querySelectorAll('.record')].map((r) =>
				r.textContent?.replace(/\s+/g, ' ').trim()
			)
		).toEqual(['QXA 16-6', 'QYA —']);
	});

	it('draws the eight bars in order', () => {
		const { container } = render(HeadToHead, { props: { headToHead: headToHead() } });
		expect(
			[...container.querySelectorAll('.mirrored-bar .label')].map((l) => l.textContent)
		).toEqual([
			'Points per game',
			'FG%',
			'eFG%',
			'Assists',
			'Rebounds',
			'Blocks',
			'Steals',
			'Technical fouls'
		]);
	});

	it('draws the postseason averages below the bars', () => {
		render(HeadToHead, { props: { headToHead: headToHead() } });
		expect(screen.getByRole('heading', { name: 'Postseason averages' })).toBeTruthy();
		expect(screen.getByText('Kai Lowe', { selector: '.name' })).toBeTruthy();
	});
});
