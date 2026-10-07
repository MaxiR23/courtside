// web/tests/lib/components/TeamMonogram.test.ts
//
// Tests for the TeamMonogram component.
//
// Tested:
// - Shows the three-letter code
// - Uses the large or small box by size
// - Uses the header and header-mobile boxes on the game detail page
//
// What is covered:
// - Both sizes
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamMonogram.test.ts
//
// SEE: web/src/lib/components/TeamMonogram.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamMonogram from '../../../src/lib/components/TeamMonogram.svelte';

describe('TeamMonogram', () => {
	it("shows the team's three-letter code", () => {
		render(TeamMonogram, { props: { code: 'GSW', size: 'large' } });
		expect(screen.getByText('GSW')).toBeTruthy();
	});

	it('uses the large box for the desktop row', () => {
		render(TeamMonogram, { props: { code: 'GSW', size: 'large' } });
		const el = screen.getByText('GSW');
		expect(el.classList.contains('large')).toBe(true);
		expect(el.classList.contains('small')).toBe(false);
	});

	it('uses the small box for the mobile row', () => {
		render(TeamMonogram, { props: { code: 'GSW', size: 'small' } });
		const el = screen.getByText('GSW');
		expect(el.classList.contains('small')).toBe(true);
		expect(el.classList.contains('large')).toBe(false);
	});

	it('renders the header and header-mobile sizes', () => {
		const { unmount } = render(TeamMonogram, { props: { code: 'GSW', size: 'header' } });
		expect(screen.getByText('GSW').classList.contains('header')).toBe(true);
		unmount();
		render(TeamMonogram, { props: { code: 'LAL', size: 'header-mobile' } });
		expect(screen.getByText('LAL').classList.contains('header-mobile')).toBe(true);
	});
});
