// web/tests/lib/components/StageStrip.test.ts
//
// Tests for the StageStrip component.
//
// Tested:
// - Four stages in order with their label, dates (or TBD) and status label
// - The current class on in progress, done on complete, neither on next and upcoming
// - The mobile class with the mobile layout, none with the desktop layout
// - Five columns: the five class, five stages in order, the mobile and five classes together
// - Spanish copy
//
// What is covered:
// - Each state a stage can show, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/StageStrip.test.ts
//
// SEE: web/src/lib/components/StageStrip.svelte
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CupFeed } from '../../../src/lib/contract/cup';
import { toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';
import StageStrip from '../../../src/lib/components/StageStrip.svelte';

const feed = (): CupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'cup.json'), 'utf8')
	) as CupFeed;
const view = (source: CupFeed = feed()) => toCupView(source);

afterEach(() => {
	vi.restoreAllMocks();
});

const stages = () => view().header.stages;

describe('StageStrip', () => {
	it('shows the four stages in order with label, dates and status', () => {
		const { container } = render(StageStrip, { props: { stages: stages(), layout: 'desktop' } });
		const items = [...container.querySelectorAll('li')].map((li) =>
			[...li.querySelectorAll('.label, .dates, .status')].map((s) => s.textContent)
		);
		expect(items).toEqual([
			['Group play', 'Nov 4 – Dec 2', 'In progress'],
			['Quarterfinals', 'Dec 8', 'Next'],
			['Semifinals', 'TBD', 'Upcoming'],
			['Championship', 'Dec 16', 'Upcoming']
		]);
	});

	it('marks current on in progress and done on complete, and neither on the rest', () => {
		const list = stages();
		list[0] = { ...list[0]!, status: 'complete', statusLabel: 'Complete' };
		list[1] = { ...list[1]!, status: 'in_progress', statusLabel: 'In progress' };
		const { container } = render(StageStrip, { props: { stages: list, layout: 'desktop' } });
		const items = [...container.querySelectorAll('li')];
		expect(items.map((li) => li.classList.contains('done'))).toEqual([true, false, false, false]);
		expect(items.map((li) => li.classList.contains('current'))).toEqual([
			false,
			true,
			false,
			false
		]);
	});

	it('adds the mobile class only with the mobile layout', () => {
		const first = render(StageStrip, { props: { stages: stages(), layout: 'desktop' } });
		expect(first.container.querySelector('ol')?.classList.contains('mobile')).toBe(false);
		first.unmount();
		const second = render(StageStrip, { props: { stages: stages(), layout: 'mobile' } });
		expect(second.container.querySelector('ol')?.classList.contains('mobile')).toBe(true);
	});

	it('adds the five class only with five columns', () => {
		const four = render(StageStrip, { props: { stages: stages(), layout: 'desktop' } });
		expect(four.container.querySelector('ol')?.classList.contains('five')).toBe(false);
		four.unmount();
		const five = render(StageStrip, {
			props: { stages: stages(), layout: 'desktop', columns: 5 }
		});
		expect(five.container.querySelector('ol')?.classList.contains('five')).toBe(true);
	});

	it('shows five stages in order with label, dates and status, and marks them by status', () => {
		const list = [
			{ key: 'playin', label: 'Play-In', dates: 'Apr 14 – Apr 17', status: 'complete' },
			{ key: 'round_1', label: 'Round 1', dates: 'Apr 18 – May 3', status: 'in_progress' },
			{ key: 'round_2', label: 'Conf. semis', dates: 'May 4', status: 'next' },
			{ key: 'round_3', label: 'Conf. finals', dates: 'TBD', status: 'upcoming' },
			{ key: 'finals', label: 'Finals', dates: 'TBD', status: 'upcoming' }
		] as const;
		const { container } = render(StageStrip, {
			props: {
				stages: list.map((s) => ({ ...s, statusLabel: s.status })),
				layout: 'desktop',
				columns: 5
			}
		});
		const items = [...container.querySelectorAll('li')];
		expect(items.map((li) => li.querySelector('.label')?.textContent)).toEqual([
			'Play-In',
			'Round 1',
			'Conf. semis',
			'Conf. finals',
			'Finals'
		]);
		expect(items.map((li) => li.classList.contains('current'))).toEqual([
			false,
			true,
			false,
			false,
			false
		]);
		expect(items.map((li) => li.classList.contains('done'))).toEqual([
			true,
			false,
			false,
			false,
			false
		]);
	});

	it('adds the mobile and five classes together on mobile with five columns', () => {
		const { container } = render(StageStrip, {
			props: { stages: stages(), layout: 'mobile', columns: 5 }
		});
		const list = container.querySelector('ol')?.classList;
		expect(list?.contains('mobile')).toBe(true);
		expect(list?.contains('five')).toBe(true);
	});

	it('shows Spanish copy', () => {
		preferLanguages(['es-ES']);
		render(StageStrip, { props: { stages: stages(), layout: 'desktop' } });
		expect(screen.getByText('Por definir')).toBeTruthy();
		expect(screen.getByText('En curso')).toBeTruthy();
	});
});
