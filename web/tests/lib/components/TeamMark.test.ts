// web/tests/lib/components/TeamMark.test.ts
//
// Tests for the TeamMark component.
//
// Tested:
// - The tile shows the code
// - The tile shows the initials for a guest without a code
// - A historical side shows its season code and links to today's team (ADR 0054)
// - A league tile, label and name link to teamHref(code)
// - A guest is never a link, with or without a code
// - Without teamHref, nothing links
// - The label with versus reads "vs DEN" at home and "@ Mariners" away, and is never a link
// - The name shows the name of the team, or its label without one
// - The tile draws the dark logo, else the light one, else the monogram
// - The tile falls back to the monogram in the same box after an image error, and tries a new logo again
// - The logo is drawn in every size variant, and a linked logo keeps the code as its name
//
// What is covered:
// - Each part and each state of the team: a league team, a guest with a code and a guest without one
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamMark.test.ts
//
// SEE: web/src/lib/components/TeamMark.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamMark from '../../../src/lib/components/TeamMark.svelte';

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const league = { code: 'DEN', name: 'Nuggets', city: 'Denver', guest: false };
const logo = {
	light: 'https://example.com/light.svg',
	dark: 'https://example.com/dark.svg'
};
const mariners = { code: null, name: 'Mariners', city: 'Harbor City', guest: true };

describe('TeamMark', () => {
	it("links a historical side to today's team while showing its season code", () => {
		const team = { ...league, historicalCode: 'SEA' };
		for (const part of ['tile', 'label'] as const) {
			const { container, unmount } = render(TeamMark, {
				props: { team, part, size: 'large', teamHref }
			});
			const link = container.querySelector('a');
			expect(link?.textContent).toBe('SEA');
			expect(link?.getAttribute('href')).toBe('/team/den');
			unmount();
		}
	});

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

	it('draws the dark logo when the logo has one', () => {
		const { container } = render(TeamMark, { props: { team: league, part: 'tile', logo } });
		const img = container.querySelector('img');
		expect(img?.getAttribute('src')).toBe('https://example.com/dark.svg');
		expect(img?.getAttribute('alt')).toBe('');
		expect(container.textContent).toBe('');
	});

	it('draws the light logo when the dark one is null', () => {
		const { container } = render(TeamMark, {
			props: { team: league, part: 'tile', logo: { ...logo, dark: null } }
		});
		expect(container.querySelector('img')?.getAttribute('src')).toBe(
			'https://example.com/light.svg'
		);
	});

	it('draws the monogram when the logo is null and when the prop is absent', () => {
		for (const props of [{ logo: null }, {}]) {
			const { container, unmount } = render(TeamMark, {
				props: { team: league, part: 'tile', ...props }
			});
			expect(container.querySelector('img')).toBeNull();
			expect(screen.getByText('DEN')).toBeTruthy();
			unmount();
		}
	});

	it('draws the monogram in the same box after the image error', async () => {
		const { container } = render(TeamMark, {
			props: { team: league, part: 'tile', size: 'standings', logo }
		});
		await fireEvent.error(container.querySelector('img') as HTMLImageElement);
		expect(container.querySelector('img')).toBeNull();
		const tile = screen.getByText('DEN');
		expect(tile.classList.contains('team-monogram')).toBe(true);
		expect(tile.classList.contains('standings')).toBe(true);
	});

	it('tries a new logo again after a failed one', async () => {
		const { container, rerender } = render(TeamMark, {
			props: { team: league, part: 'tile', logo }
		});
		await fireEvent.error(container.querySelector('img') as HTMLImageElement);
		expect(container.querySelector('img')).toBeNull();
		await rerender({
			team: league,
			part: 'tile',
			logo: { light: 'https://example.com/other.svg', dark: null }
		});
		expect(container.querySelector('img')?.getAttribute('src')).toBe(
			'https://example.com/other.svg'
		);
	});

	it('draws the logo and the monogram in each size variant', () => {
		const sizes = [
			'large',
			'small',
			'header',
			'header-mobile',
			'injury',
			'team',
			'standings',
			'search',
			'cup-draw',
			'cup-champion',
			'playoffs-champion',
			'cup-node',
			'allstar-league',
			'names',
			'fill'
		] as const;
		for (const size of sizes) {
			const withLogo = render(TeamMark, { props: { team: league, part: 'tile', size, logo } });
			const box = withLogo.container.querySelector('.team-monogram');
			expect(box?.classList.contains(size), size).toBe(true);
			expect(box?.querySelector('img'), size).not.toBeNull();
			withLogo.unmount();
			const plain = render(TeamMark, { props: { team: league, part: 'tile', size } });
			expect(plain.container.querySelector('.team-monogram')?.classList.contains(size), size).toBe(
				true
			);
			plain.unmount();
		}
	});

	it('keeps the code as the accessible name of a linked logo', () => {
		render(TeamMark, { props: { team: league, part: 'tile', logo, teamHref } });
		expect(screen.getByRole('link', { name: 'DEN' }).getAttribute('href')).toBe('/team/den');
	});
});
