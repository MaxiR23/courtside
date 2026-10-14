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
// - Uses the standings box on the standings page
// - Uses the search box in the search overlay
// - Uses the cup-draw box in the Cup draw list and the cup-champion box in the Cup header
// - Uses the playoffs-champion box in the playoffs hero
// - Uses the cup-node box in a bracket node
// - Uses the allstar-league box for a player's league team
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

	it('renders the standings size', () => {
		render(TeamMonogram, { props: { code: 'OKC', size: 'standings' } });
		expect(screen.getByText('OKC').classList.contains('standings')).toBe(true);
	});

	it('renders the search size', () => {
		render(TeamMonogram, { props: { code: 'OKC', size: 'search' } });
		expect(screen.getByText('OKC').classList.contains('search')).toBe(true);
	});

	it('renders the cup-draw and cup-champion sizes', () => {
		render(TeamMonogram, { props: { code: 'QXA', size: 'cup-draw' } });
		render(TeamMonogram, { props: { code: 'QXB', size: 'cup-champion' } });
		expect(screen.getByText('QXA').classList.contains('cup-draw')).toBe(true);
		expect(screen.getByText('QXB').classList.contains('cup-champion')).toBe(true);
	});

	it('renders the cup-node size', () => {
		render(TeamMonogram, { props: { code: 'QXC', size: 'cup-node' } });
		expect(screen.getByText('QXC').classList.contains('cup-node')).toBe(true);
	});

	it('renders the playoffs-champion size', () => {
		render(TeamMonogram, { props: { code: 'QXD', size: 'playoffs-champion' } });
		expect(screen.getByText('QXD').classList.contains('playoffs-champion')).toBe(true);
	});

	it('renders the allstar-league size, linked to the team page', () => {
		const { container } = render(TeamMonogram, {
			props: { code: 'HBR', size: 'allstar-league', href: '/team/hbr' as ResolvedPathname }
		});
		const link = container.querySelector('a');
		expect(link?.classList.contains('allstar-league')).toBe(true);
		expect(link?.getAttribute('href')).toBe('/team/hbr');
	});
});
