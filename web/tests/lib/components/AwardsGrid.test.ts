// web/tests/lib/components/AwardsGrid.test.ts
//
// Tests for the AwardsGrid component.
//
// Tested:
// - One card per award, in the feed's order
// - The mobile class on a phone, none on desktop
//
// What is covered:
// - Each layout the grid shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AwardsGrid.test.ts
//
// SEE: web/src/lib/components/AwardsGrid.svelte
import { render } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import AwardsGrid from '../../../src/lib/components/AwardsGrid.svelte';

const awards = () =>
	toPlayoffsView(
		JSON.parse(
			readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'playoffs-complete.json'), 'utf8')
		) as PlayoffsFeed,
		null
	).awards;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('AwardsGrid', () => {
	it('draws one card per award in the feed order', () => {
		const { container } = render(AwardsGrid, { props: { awards: awards(), layout: 'desktop' } });
		const names = [...container.querySelectorAll('.award-name')].map((n) => n.textContent);
		expect(names).toEqual([
			'Most Valuable Player',
			'Finals MVP',
			'East finals MVP',
			'West finals MVP',
			'Twyman-Stokes Teammate Award',
			'All-NBA 1st Team'
		]);
		expect(container.querySelector('.awards-grid')?.classList.contains('mobile')).toBe(false);
	});

	it('becomes a snap scroller on a phone', () => {
		const { container } = render(AwardsGrid, { props: { awards: awards(), layout: 'mobile' } });
		expect(container.querySelector('.awards-grid')?.classList.contains('mobile')).toBe(true);
		expect(container.querySelectorAll('.item')).toHaveLength(6);
	});

	it('draws nothing for no awards', () => {
		const { container } = render(AwardsGrid, { props: { awards: [], layout: 'desktop' } });
		expect(container.querySelectorAll('.item')).toHaveLength(0);
	});
});
