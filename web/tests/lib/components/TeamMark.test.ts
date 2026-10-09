// web/tests/lib/components/TeamMark.test.ts
//
// Tests for the TeamMark component.
//
// Tested:
// - The tile shows the code
// - The tile shows the initials for a guest without a code
// - A league tile, label and name link to teamHref(code)
// - A guest is never a link, with or without a code
// - Without teamHref, nothing links
// - The label with versus reads "vs DEN" at home and "@ Mariners" away, and is never a link
// - The name shows the name of the team, or its label without one
//
// What is covered:
// - Each part and each state of the team: a league team, a guest with a code and a guest without one
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamMark.test.ts
//
// SEE: web/src/lib/components/TeamMark.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamMark from '../../../src/lib/components/TeamMark.svelte';

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const league = { code: 'DEN', name: 'Nuggets', city: 'Denver', guest: false };
const mariners = { code: null, name: 'Mariners', city: 'Harbor City', guest: true };

describe('TeamMark', () => {
	it('shows the code in the tile', () => {
		render(TeamMark, { props: { team: league, part: 'tile', size: 'large' } });
		expect(screen.getByText('DEN').classList.contains('team-monogram')).toBe(true);
	});

	it('shows the initials in the tile of a guest without a code', () => {
		render(TeamMark, { props: { team: mariners, part: 'tile', size: 'small' } });
		const tile = screen.getByText('HM');
		expect(tile.classList.contains('team-monogram')).toBe(true);
		expect(tile.classList.contains('small')).toBe(true);
	});

	it('links a league tile, label and name to the team page', () => {
		for (const part of ['tile', 'label', 'name'] as const) {
			const { container, unmount } = render(TeamMark, {
				props: { team: league, part, size: 'large', teamHref }
			});
			expect(container.querySelector('a')?.getAttribute('href')).toBe('/team/den');
			unmount();
		}
	});

	it('never links a guest, with or without a code', () => {
		for (const team of [mariners, { ...mariners, code: 'HCM' }]) {
			for (const part of ['tile', 'label', 'name'] as const) {
				const { container, unmount } = render(TeamMark, {
					props: { team, part, size: 'large', teamHref }
				});
				expect(container.querySelector('a')).toBeNull();
				unmount();
			}
		}
	});

	it('links nothing without teamHref', () => {
		for (const part of ['tile', 'label', 'name'] as const) {
			const { container, unmount } = render(TeamMark, { props: { team: league, part } });
			expect(container.querySelector('a')).toBeNull();
			unmount();
		}
	});

	it('reads "vs DEN" at home and "@ Mariners" away on the label, never as a link', () => {
		const home = render(TeamMark, {
			props: { team: league, part: 'label', versus: 'home', teamHref }
		});
		expect(home.container.textContent).toBe('vs DEN');
		expect(home.container.querySelector('a')).toBeNull();
		home.unmount();
		const away = render(TeamMark, { props: { team: mariners, part: 'label', versus: 'away' } });
		expect(away.container.textContent).toBe('@ Mariners');
	});

	it('shows the name of the team on the name part', () => {
		render(TeamMark, { props: { team: league, part: 'name' } });
		expect(screen.getByText('Nuggets')).toBeTruthy();
	});

	it('shows the label when a team has no name on the name part', () => {
		render(TeamMark, { props: { team: { ...league, name: null }, part: 'name' } });
		expect(screen.getByText('DEN')).toBeTruthy();
	});
});
