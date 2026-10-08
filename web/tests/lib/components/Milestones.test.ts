// web/tests/lib/components/Milestones.test.ts
//
// Tests for the Milestones component.
//
// Tested:
// - Eight cells with value and Career sub-line
// - The mobile class with the mobile layout and none with the desktop one
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

	it('uses the mobile class only with the mobile layout', () => {
		const desktop = render(Milestones, { props: { milestones, layout: 'desktop' } });
		expect(desktop.container.querySelector('.cells')?.classList.contains('mobile')).toBe(false);
		desktop.unmount();
		const mobile = render(Milestones, { props: { milestones, layout: 'mobile' } });
		expect(mobile.container.querySelector('.cells')?.classList.contains('mobile')).toBe(true);
	});
});
