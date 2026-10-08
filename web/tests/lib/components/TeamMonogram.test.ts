// web/tests/lib/components/TeamMonogram.test.ts
//
// Tests for the TeamMonogram component.
//
// Tested:
// - Shows the three-letter code
// - Uses the large or small box by size
// - Uses the header and header-mobile boxes on the game detail page
// - Uses the injury box on the injuries section
// - Uses the team box on the team page
// - Links the code to the href when one is given, and renders a span without one
//
// What is covered:
// - Both sizes
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamMonogram.test.ts
//
// SEE: web/src/lib/components/TeamMonogram.svelte
import type { ResolvedPathname } from '$app/types';
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

	it('renders the team size', () => {
		render(TeamMonogram, { props: { code: 'OKC', size: 'team' } });
		expect(screen.getByText('OKC').classList.contains('team')).toBe(true);
	});

	it('renders the injury size', () => {
		render(TeamMonogram, { props: { code: 'GSW', size: 'injury' } });
		expect(screen.getByText('GSW').classList.contains('injury')).toBe(true);
	});

	it('links the code to the href when one is given', () => {
		render(TeamMonogram, {
			props: { code: 'GSW', size: 'large', href: '/team/gsw' as ResolvedPathname }
		});
		const link = screen.getByRole('link', { name: 'GSW' });
		expect(link.getAttribute('href')).toBe('/team/gsw');
		expect(link.classList.contains('large')).toBe(true);
		expect(link.classList.contains('linked')).toBe(true);
	});

	it('renders a span with no link without an href', () => {
		render(TeamMonogram, { props: { code: 'GSW', size: 'large' } });
		expect(screen.queryByRole('link')).toBeNull();
		expect(screen.getByText('GSW').tagName).toBe('SPAN');
	});
});
