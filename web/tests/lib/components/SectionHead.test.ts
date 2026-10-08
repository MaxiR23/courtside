// web/tests/lib/components/SectionHead.test.ts
//
// Tests for the SectionHead component.
//
// Tested:
// - Shows the title as an h2
// - Shows the meta only when given
// - Adds the emphasis class to the meta on request
//
// What is covered:
// - The header shared by the sections of the game and team pages
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SectionHead.test.ts
//
// SEE: web/src/lib/components/SectionHead.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import SectionHead from '../../../src/lib/components/SectionHead.svelte';

describe('SectionHead', () => {
	it('shows the title as an h2 and no meta without one', () => {
		const { container } = render(SectionHead, { props: { title: 'Roster' } });
		expect(screen.getByRole('heading', { level: 2, name: 'Roster' })).toBeTruthy();
		expect(container.querySelector('.meta')).toBeNull();
	});

	it('shows the meta when given', () => {
		const { container } = render(SectionHead, { props: { title: 'Injuries', meta: 'Report' } });
		const meta = container.querySelector('.meta');
		expect(meta?.textContent).toBe('Report');
		expect(meta?.classList.contains('emphasis')).toBe(false);
	});

	it('adds the emphasis class on request', () => {
		const { container } = render(SectionHead, {
			props: { title: 'Win probability', meta: 'GSW 68%', emphasis: true }
		});
		expect(container.querySelector('.meta')?.classList.contains('emphasis')).toBe(true);
	});
});
