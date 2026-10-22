// web/tests/lib/components/HeroSlideSelector.test.ts
//
// Tests for the HeroSlideSelector component.
//
// Tested:
// - Shows the team logo and the team name; the monogram for a side without a logo
// - Reads "Show Mariners, away" and "Show Owls, home" in English and in Spanish
// - Marks the active selector current
// - Calls onselect on click
// - Draws the track fill only when active and running
// - Sets --side-accent to the side's accent, and to the neutral accent token when it is null
//
// What is covered:
// - Each state of the selector, plus the click
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/HeroSlideSelector.test.ts
//
// SEE: web/src/lib/components/HeroSlideSelector.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { HeroSide } from '../../../src/lib/hero/types';
import { preferLanguages } from '../../prefer-languages';

import HeroSlideSelector from '../../../src/lib/components/HeroSlideSelector.svelte';

const star = {
	firstName: 'Ines',
	lastName: 'Varga',
	shortName: 'Varga',
	teamCode: 'HBR',
	teamName: 'Harbor City Mariners',
	photo: 'https://example.com/varga.png'
};
const mariners: HeroSide = {
	code: 'HBR',
	name: 'Mariners',
	city: 'Harbor City',
	guest: false,
	logo: { light: 'https://example.com/hbr-light.svg', dark: 'https://example.com/hbr-dark.svg' },
	accent: '#1f6f8b',
	star
};
const owls: HeroSide = { ...mariners, code: 'PVO', name: 'Owls', logo: null, accent: null };

const props = {
	side: mariners,
	place: 'away' as const,
	active: false,
	running: false,
	cycle: 0,
	onselect: () => {}
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('HeroSlideSelector', () => {
	it('shows the dark logo and the team name', () => {
		const { container } = render(HeroSlideSelector, { props });
		expect(container.querySelector('img')?.getAttribute('src')).toBe(
			'https://example.com/hbr-dark.svg'
		);
		expect(screen.getByText('Mariners')).toBeTruthy();
	});

	it('shows the monogram for a side without a logo', () => {
		const { container } = render(HeroSlideSelector, { props: { ...props, side: owls } });
		expect(container.querySelector('img')).toBeNull();
		expect(screen.getByText('PVO').classList.contains('team-monogram')).toBe(true);
	});

	it('names the away and the home selector', () => {
		const away = render(HeroSlideSelector, { props });
		expect(screen.getByRole('button', { name: 'Show Mariners, away' })).toBeTruthy();
		away.unmount();
		render(HeroSlideSelector, { props: { ...props, side: owls, place: 'home' } });
		expect(screen.getByRole('button', { name: 'Show Owls, home' })).toBeTruthy();
	});

	it('names the selector in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		const away = render(HeroSlideSelector, { props });
		expect(screen.getByRole('button', { name: 'Mostrar a Mariners, visitante' })).toBeTruthy();
		away.unmount();
		render(HeroSlideSelector, { props: { ...props, place: 'home' } });
		expect(screen.getByRole('button', { name: 'Mostrar a Mariners, local' })).toBeTruthy();
	});

	it('marks the active selector current and only that one', () => {
		const active = render(HeroSlideSelector, { props: { ...props, active: true } });
		expect(screen.getByRole('button').getAttribute('aria-current')).toBe('true');
		active.unmount();
		render(HeroSlideSelector, { props });
		expect(screen.getByRole('button').getAttribute('aria-current')).toBeNull();
	});

	it('calls onselect on click', async () => {
		const onselect = vi.fn();
		render(HeroSlideSelector, { props: { ...props, onselect } });
		await fireEvent.click(screen.getByRole('button'));
		expect(onselect).toHaveBeenCalledOnce();
	});

	it('draws the track fill only when active and running', () => {
		const fills = (active: boolean, running: boolean) => {
			const { container, unmount } = render(HeroSlideSelector, {
				props: { ...props, active, running }
			});
			const count = container.querySelectorAll('.track-fill').length;
			unmount();
			return count;
		};
		expect(fills(true, true)).toBe(1);
		expect(fills(true, false)).toBe(0);
		expect(fills(false, true)).toBe(0);
		expect(fills(false, false)).toBe(0);
	});

	it("sets --side-accent to the side's accent, and to the neutral accent when it is null", () => {
		const accent = render(HeroSlideSelector, { props });
		expect(
			(screen.getByRole('button') as HTMLElement).style.getPropertyValue('--side-accent')
		).toBe('#1f6f8b');
		accent.unmount();
		render(HeroSlideSelector, { props: { ...props, side: owls } });
		expect(
			(screen.getByRole('button') as HTMLElement).style.getPropertyValue('--side-accent')
		).toBe('var(--identity-neutral-accent)');
	});
});
