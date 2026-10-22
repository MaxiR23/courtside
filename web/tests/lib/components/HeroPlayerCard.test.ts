// web/tests/lib/components/HeroPlayerCard.test.ts
//
// Tests for the HeroPlayerCard component.
//
// Tested:
// - Shows the active player's photo, with the player's name as alt text
// - Hides the inactive slide from assistive technology
// - Shows the player strip (name, "{City} {Team}" linked to the team page) and switches it with active
// - Shows a placeholder on a photo error and keeps the other photo; a replaced player shows its photo
// - Renders photos only for the active and the next slide, and keeps shown ones
// - Draws the faded team logo and the tricode of each slide, and the strip mark
// - Draws the monogram in the logo layer and the strip for a side without a logo
// - Sets --side-accent on the card and on each slide from the accent, and the neutral accent when null
//
// What is covered:
// - Each state of the card and the photo error interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/HeroPlayerCard.test.ts
//
// SEE: web/src/lib/components/HeroPlayerCard.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import type { HeroPlayer, HeroSide } from '../../../src/lib/hero/types';

import HeroPlayerCard from '../../../src/lib/components/HeroPlayerCard.svelte';

const player = (
	firstName: string,
	lastName: string,
	teamCode: string,
	teamName: string,
	photo: string
): HeroPlayer => ({ firstName, lastName, shortName: lastName, teamCode, teamName, photo });

const away: HeroSide = {
	code: 'HBR',
	name: 'Mariners',
	city: 'Harbor City',
	guest: false,
	logo: { light: 'https://example.com/hbr-light.svg', dark: 'https://example.com/hbr-dark.svg' },
	accent: '#1f6f8b',
	star: player('Ines', 'Varga', 'HBR', 'Harbor City Mariners', '/away.svg')
};
const home: HeroSide = {
	code: 'PVO',
	name: 'Owls',
	city: 'Pine Valley',
	guest: false,
	logo: null,
	accent: null,
	star: player('Tomas', 'Okafor', 'PVO', 'Pine Valley Owls', '/home.svg')
};
const sides = [away, home];
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const props = { teamHref, sides, active: 0 };

describe('HeroPlayerCard', () => {
	it("shows the active player's photo with the player's name as alt text", () => {
		render(HeroPlayerCard, { props });
		expect(screen.getByAltText('Ines Varga').getAttribute('src')).toBe('/away.svg');
	});

	it('hides the inactive slide from assistive technology', () => {
		const { container } = render(HeroPlayerCard, { props });
		const slides = container.querySelectorAll('.slide');
		expect(slides).toHaveLength(2);
		expect(slides[0].getAttribute('aria-hidden')).toBeNull();
		expect(slides[1].getAttribute('aria-hidden')).toBe('true');
		expect(container.querySelectorAll('.cutout')).toHaveLength(2);
	});

	it('shows the active player and team in the strip, linking the team to its page', () => {
		const { container } = render(HeroPlayerCard, { props });
		const strip = container.querySelector('.strip') as HTMLElement;
		expect(strip.textContent).toContain('Ines Varga');
		expect(strip.textContent).toContain('Harbor City Mariners');
		expect(
			[...strip.querySelectorAll('a')].map((a) => [a.textContent, a.getAttribute('href')])
		).toEqual([['Harbor City Mariners', '/team/hbr']]);
	});

	it('hides the strip mark from assistive technology when the side has no logo', async () => {
		const { container, rerender } = render(HeroPlayerCard, { props });
		await rerender({ ...props, active: 1 });
		expect(container.querySelector('.strip-mark')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('switches the strip to the other player when active changes', async () => {
		const { container, rerender } = render(HeroPlayerCard, { props });
		await rerender({ ...props, active: 1 });
		const strip = container.querySelector('.strip') as HTMLElement;
		expect(strip.textContent).toContain('Tomas Okafor');
		expect(strip.textContent).toContain('Pine Valley Owls');
		expect(strip.textContent).not.toContain('Ines Varga');
	});

	it("shows a placeholder with the player's name on a photo error, and keeps the other photo", async () => {
		const { container } = render(HeroPlayerCard, { props });
		await fireEvent.error(screen.getByAltText('Ines Varga'));
		expect(screen.queryByAltText('Ines Varga')).toBeNull();
		expect(screen.getByRole('img', { name: 'Ines Varga' })).toBeTruthy();
		expect(screen.getByAltText('Tomas Okafor')).toBeTruthy();
		expect(container.querySelector('.strip')).not.toBeNull();
	});

	it('renders only the active and the next photo, and the next one after advancing', async () => {
		const six = Array.from({ length: 6 }, (_, i) => ({
			...away,
			star: { ...away.star, lastName: `P${i}`, photo: `/p${i}.svg` }
		}));
		const { container, rerender } = render(HeroPlayerCard, {
			props: { teamHref, sides: six, active: 0 }
		});
		const photos = () =>
			Array.from(container.querySelectorAll('.cutout img')).map((img) => img.getAttribute('src'));
		expect(photos()).toEqual(['/p0.svg', '/p1.svg']);
		await rerender({ teamHref, sides: six, active: 1 });
		expect(photos()).toEqual(['/p0.svg', '/p1.svg', '/p2.svg']);
		expect(container.querySelectorAll('.cutout')).toHaveLength(6);
	});

	it("shows the new player's photo after a failed photo is replaced", async () => {
		const { rerender } = render(HeroPlayerCard, { props });
		await fireEvent.error(screen.getByAltText('Ines Varga'));
		const replacement: HeroSide = {
			...away,
			star: player('Mira', 'Holt', 'HBR', 'Harbor City Mariners', '/replacement.svg')
		};
		await rerender({ teamHref, sides: [replacement, home], active: 0 });
		expect(screen.getByAltText('Mira Holt').getAttribute('src')).toBe('/replacement.svg');
	});

	it('draws the faded team logo and the tricode of each slide', () => {
		const { container } = render(HeroPlayerCard, { props });
		const slides = container.querySelectorAll('.slide');
		expect(slides[0].querySelector('.logo-layer img')?.getAttribute('src')).toBe(
			'https://example.com/hbr-dark.svg'
		);
		expect([...container.querySelectorAll('.tricode')].map((t) => t.textContent?.trim())).toEqual([
			'HBR',
			'PVO'
		]);
	});

	it('draws the team logo in the strip mark', () => {
		const { container } = render(HeroPlayerCard, { props });
		expect(container.querySelector('.strip-mark img')?.getAttribute('src')).toBe(
			'https://example.com/hbr-dark.svg'
		);
	});

	it('draws the monogram in the logo layer and the strip for a side without a logo', () => {
		const { container } = render(HeroPlayerCard, { props: { ...props, active: 1 } });
		const slides = container.querySelectorAll('.slide');
		expect(slides[1].querySelector('.logo-layer img')).toBeNull();
		expect(slides[1].querySelector('.logo-layer .team-monogram')?.textContent).toBe('PVO');
		expect(container.querySelector('.strip-mark img')).toBeNull();
		expect(container.querySelector('.strip-mark .team-monogram')?.textContent).toBe('PVO');
	});

	it('sets --side-accent on the card and each slide, with the neutral accent for a null accent', () => {
		const { container } = render(HeroPlayerCard, { props });
		const accentOf = (el: Element | null) =>
			(el as HTMLElement).style.getPropertyValue('--side-accent');
		const slides = container.querySelectorAll('.slide');
		expect(accentOf(container.querySelector('.player-card'))).toBe('#1f6f8b');
		expect(accentOf(slides[0])).toBe('#1f6f8b');
		expect(accentOf(slides[1])).toBe('var(--identity-neutral-accent)');
	});

	it('sets the neutral accent on the card when the active side has none', () => {
		const { container } = render(HeroPlayerCard, { props: { ...props, active: 1 } });
		expect(
			(container.querySelector('.player-card') as HTMLElement).style.getPropertyValue(
				'--side-accent'
			)
		).toBe('var(--identity-neutral-accent)');
	});
});
