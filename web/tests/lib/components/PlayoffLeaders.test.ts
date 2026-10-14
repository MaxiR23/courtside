// web/tests/lib/components/PlayoffLeaders.test.ts
//
// Tests for the PlayoffLeaders component.
//
// Tested:
// - Nine category tabs, the first pressed
// - The leader card and the rows 2 to 5 with the ranks the feed has
// - Switching the category; fewer rows; an empty category shows —
//
// What is covered:
// - Each state the section shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayoffLeaders.test.ts
//
// SEE: web/src/lib/components/PlayoffLeaders.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import PlayoffLeaders from '../../../src/lib/components/PlayoffLeaders.svelte';

const tabs = () =>
	toPlayoffsView(
		JSON.parse(
			readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'playoffs-picture.json'), 'utf8')
		) as PlayoffsFeed,
		null
	).leaders;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('PlayoffLeaders', () => {
	it('draws nine category tabs with the first pressed', () => {
		render(PlayoffLeaders, { props: { tabs: tabs() } });
		const buttons = screen.getAllByRole('button');
		expect(buttons).toHaveLength(9);
		expect(buttons.map((b) => b.getAttribute('aria-pressed'))).toEqual([
			'true',
			...Array(8).fill('false')
		]);
	});

	it('draws the leader card and the rows after it', () => {
		const { container } = render(PlayoffLeaders, { props: { tabs: tabs() } });
		expect(container.querySelector('.first .name')?.textContent).toBe('Leader points 1');
		expect(container.querySelector('.first .value')?.textContent).toBe('30.0');
		expect(container.querySelector('.first .category')?.textContent).toBe('Points');
		expect([...container.querySelectorAll('.row .rank')].map((r) => r.textContent)).toEqual([
			'2',
			'3'
		]);
	});

	it('switches the category and shows the rows the feed has', async () => {
		const { container } = render(PlayoffLeaders, { props: { tabs: tabs() } });
		await fireEvent.click(screen.getByRole('button', { name: 'Rebounds' }));
		expect(container.querySelector('.first .category')?.textContent).toBe('Rebounds');
		expect(container.querySelectorAll('.row')).toHaveLength(4);
	});

	it('shows — for an empty category', async () => {
		const { container } = render(PlayoffLeaders, { props: { tabs: tabs() } });
		await fireEvent.click(screen.getByRole('button', { name: 'Assists' }));
		expect(container.querySelector('.first .name')?.textContent).toBe('—');
		expect(container.querySelector('.first .team')?.textContent).toBe('—');
		expect(container.querySelector('.first .value')?.textContent).toBe('—');
		expect(container.querySelectorAll('.row')).toHaveLength(0);
	});
});
