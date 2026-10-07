// web/tests/lib/components/PlayerPhoto.test.ts
//
// Tests for the PlayerPhoto component.
//
// Tested:
// - Shows the player's photo with the full name as alt text, loaded lazily
// - Shows a placeholder with the initials and name when the photo fails to load
// - Keeps the photo frame when the placeholder replaces the photo
// - Tries again when the photo URL changes after a failure
// - The star variant fills its parent and keeps the placeholder fallback
//
// What is covered:
// - Each state and the error interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayerPhoto.test.ts
//
// SEE: web/src/lib/components/PlayerPhoto.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import type { PanelPlayer } from '../../../src/lib/schedule/types';

import PlayerPhoto from '../../../src/lib/components/PlayerPhoto.svelte';

const player: PanelPlayer = {
	firstName: 'Stephen',
	lastName: 'Curry',
	teamCode: 'GSW',
	photo: '/away.svg'
};

describe('PlayerPhoto', () => {
	it("shows the player's photo with the full name as its alt text, loaded lazily", () => {
		render(PlayerPhoto, { props: { player } });
		const img = screen.getByAltText('Stephen Curry');
		expect(img.getAttribute('src')).toBe('/away.svg');
		expect(img.getAttribute('loading')).toBe('lazy');
	});

	it("shows a placeholder with the player's initials and name when the photo fails to load", async () => {
		render(PlayerPhoto, { props: { player } });
		await fireEvent.error(screen.getByAltText('Stephen Curry'));
		const placeholder = screen.getByRole('img', { name: 'Stephen Curry' });
		expect(placeholder.textContent).toBe('SC');
		expect(document.querySelector('img')).toBeNull();
	});

	it('keeps the photo frame when the placeholder replaces the photo', async () => {
		const { container } = render(PlayerPhoto, { props: { player } });
		await fireEvent.error(screen.getByAltText('Stephen Curry'));
		const frame = container.querySelector('.photo-frame');
		expect(frame?.querySelector('.photo-placeholder')).not.toBeNull();
	});

	it('tries again when the photo URL changes after a failure', async () => {
		const { rerender } = render(PlayerPhoto, { props: { player } });
		await fireEvent.error(screen.getByAltText('Stephen Curry'));
		await rerender({ player: { ...player, photo: '/other.svg' } });
		expect(screen.getByAltText('Stephen Curry').getAttribute('src')).toBe('/other.svg');
	});
});

describe('PlayerPhoto star variant', () => {
	it('is not a star frame by default', () => {
		const { container } = render(PlayerPhoto, { props: { player } });
		expect(container.querySelector('.photo-frame')?.classList.contains('star')).toBe(false);
	});

	it('marks the frame as a star and shows the photo', () => {
		const { container } = render(PlayerPhoto, { props: { player, star: true } });
		expect(container.querySelector('.photo-frame')?.classList.contains('star')).toBe(true);
		expect(screen.getByAltText('Stephen Curry').getAttribute('src')).toBe('/away.svg');
	});

	it('falls back to the placeholder with initials when the star photo fails', async () => {
		const { container } = render(PlayerPhoto, { props: { player, star: true } });
		await fireEvent.error(screen.getByAltText('Stephen Curry'));
		expect(screen.getByRole('img', { name: 'Stephen Curry' }).textContent).toBe('SC');
		expect(container.querySelector('.photo-frame.star')).not.toBeNull();
	});
});
