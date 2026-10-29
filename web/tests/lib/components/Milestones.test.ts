// web/tests/lib/components/Milestones.test.ts
//
// Tests for the Milestones component.
//
// Tested:
// - Eight cells with value and Career sub-line
// - Two fixed columns with the mobile layout and none with the desktop one
// - Values in tabular figures
//
// What is covered:
// - Each case, from the recorded player feed through the props layer
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Milestones.test.ts
//
// SEE: web/src/lib/components/Milestones.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import Milestones from '../../../src/lib/components/Milestones.svelte';
import type { PlayerFeed } from '../../../src/lib/contract/player';
import { toPlayerView } from '../../../src/lib/feed/player-props';

const feed = JSON.parse(
	readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'player.json'), 'utf8')
) as PlayerFeed;
const milestones = toPlayerView(feed).sections.milestones!;

describe('Milestones', () => {
	it('shows the eight cells with value and career sub-line', () => {
		const { container } = render(Milestones, { props: { milestones, layout: 'desktop' } });
		const cells = [...container.querySelectorAll('.cell')];
		expect(cells).toHaveLength(8);
		expect(cells[0]?.textContent?.replace(/\s+/g, ' ').trim()).toBe('Double-doubles 12 Career 75');
		expect(cells[6]?.textContent?.replace(/\s+/g, ' ').trim()).toBe('AST/TO 2.67 Career 1.92');
	});

	it('still renders the grid element for an empty list', () => {
		const { container } = render(Milestones, {
			props: { milestones: { ...milestones, cells: [] }, layout: 'desktop' }
		});
		expect(container.querySelector('.cells')).not.toBeNull();
		expect(container.querySelectorAll('.cell')).toHaveLength(0);
	});

	it('uses two columns only with the mobile layout', () => {
		const desktop = render(Milestones, { props: { milestones, layout: 'desktop' } });
		const desktopGrid = desktop.container.querySelector<HTMLElement>('.cells')!;
		expect(desktopGrid.classList.contains('fixed')).toBe(false);
		expect(desktopGrid.style.getPropertyValue('--cells-columns')).toBe('');
		desktop.unmount();
		const mobile = render(Milestones, { props: { milestones, layout: 'mobile' } });
		const mobileGrid = mobile.container.querySelector<HTMLElement>('.cells')!;
		expect(mobileGrid.classList.contains('fixed')).toBe(true);
		expect(mobileGrid.style.getPropertyValue('--cells-columns')).toBe('2');
	});

	it('shows the values in tabular figures', () => {
		const { container } = render(Milestones, { props: { milestones, layout: 'desktop' } });
		const values = [...container.querySelectorAll('.value')];
		expect(values).toHaveLength(8);
		expect(values.every((v) => v.classList.contains('numeric'))).toBe(true);
	});
});
