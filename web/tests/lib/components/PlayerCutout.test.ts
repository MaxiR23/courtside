// web/tests/lib/components/PlayerCutout.test.ts
//
// Tests for the PlayerCutout component.
//
// Tested:
// - Shows the active player's photo and chip, and hides the other cutout from assistive technology
// - Switches the chip when the active player changes
// - Shows a placeholder when a photo fails to load
// - Renders photos only for the active and the next slide, and keeps shown ones
// - Shows a replacement player's photo after the previous photo in that slot failed
//
// What is covered:
// - Each state and the error interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayerCutout.test.ts
//
// SEE: web/src/lib/components/PlayerCutout.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import type { HeroPlayer } from '../../../src/lib/hero/types';

import PlayerCutout from '../../../src/lib/components/PlayerCutout.svelte';

const away: HeroPlayer = {
	firstName: 'Stephen',
	lastName: 'Curry',
	shortName: 'Curry',
	teamCode: 'GSW',
	teamName: 'Golden State Warriors',
	photo: '/away.svg'
};
const home: HeroPlayer = {
	firstName: 'LeBron',
	lastName: 'James',
	shortName: 'James',
	teamCode: 'LAL',
	teamName: 'Los Angeles Lakers',
	photo: '/home.svg'
};
const players = [away, home];

describe('PlayerCutout', () => {
	it("shows the active player's photo with the player's name as alt text", () => {
		render(PlayerCutout, { props: { players, active: 0 } });
		const img = screen.getByAltText('Stephen Curry');
		expect(img.getAttribute('src')).toBe('/away.svg');
	});

	it("marks the inactive player's cutout hidden from assistive technology", () => {
		const { container } = render(PlayerCutout, { props: { players, active: 0 } });
		const cutouts = container.querySelectorAll('.cutout');
		expect(cutouts).toHaveLength(2);
		expect(cutouts[0].getAttribute('aria-hidden')).toBeNull();
		expect(cutouts[1].getAttribute('aria-hidden')).toBe('true');
	});

	it("shows the active player's team code, first name, last name and team name in the chip", () => {
		const { container } = render(PlayerCutout, { props: { players, active: 0 } });
		const chip = container.querySelector('.chip');
		expect(chip?.textContent).toContain('GSW');
		expect(chip?.textContent).toContain('Stephen');
		expect(chip?.textContent).toContain('Curry');
		expect(chip?.textContent).toContain('Golden State Warriors');
	});

	it('switches the chip to the other player when active changes', async () => {
		const { container, rerender } = render(PlayerCutout, { props: { players, active: 0 } });
		await rerender({ players, active: 1 });
		const chip = container.querySelector('.chip');
		expect(chip?.textContent).toContain('LAL');
		expect(chip?.textContent).toContain('James');
		expect(chip?.textContent).not.toContain('GSW');
	});

	it("shows a placeholder with the player's name when the photo fails to load", async () => {
		const { container } = render(PlayerCutout, { props: { players, active: 0 } });
		await fireEvent.error(screen.getByAltText('Stephen Curry'));
		expect(screen.queryByAltText('Stephen Curry')).toBeNull();
		expect(screen.getByRole('img', { name: 'Stephen Curry' })).toBeTruthy();
		expect(container.querySelector('.chip')).not.toBeNull();
	});

	it("keeps the other player's photo when only one fails", async () => {
		render(PlayerCutout, { props: { players, active: 0 } });
		await fireEvent.error(screen.getByAltText('Stephen Curry'));
		expect(screen.getByAltText('LeBron James')).toBeTruthy();
	});

	it('renders only the active and the next photo, and the next one after advancing', async () => {
		const six = Array.from({ length: 6 }, (_, i) => ({
			...away,
			lastName: `P${i}`,
			photo: `/p${i}.svg`
		}));
		const { container, rerender } = render(PlayerCutout, { props: { players: six, active: 0 } });
		const srcs = () =>
			Array.from(container.querySelectorAll('img')).map((img) => img.getAttribute('src'));
		expect(srcs()).toEqual(['/p0.svg', '/p1.svg']);
		await rerender({ players: six, active: 1 });
		expect(srcs()).toEqual(['/p0.svg', '/p1.svg', '/p2.svg']);
		expect(container.querySelectorAll('.cutout')).toHaveLength(6);
	});

	it("shows the new player's photo after a failed photo is replaced", async () => {
		const { rerender } = render(PlayerCutout, { props: { players, active: 0 } });
		await fireEvent.error(screen.getByAltText('Stephen Curry'));
		const replacement: HeroPlayer = {
			...away,
			firstName: 'Klay',
			lastName: 'Thompson',
			shortName: 'Thompson',
			photo: '/replacement.svg'
		};
		await rerender({ players: [replacement, home], active: 0 });
		const img = screen.getByAltText('Klay Thompson');
		expect(img.getAttribute('src')).toBe('/replacement.svg');
	});
});
