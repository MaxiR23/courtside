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
// - The star photo is sized by its column's height, never wider than the
//   column, bottom-centered
// - The leader photo keeps its width and height tokens
//
// What is covered:
// - Each state and the error interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayerPhoto.test.ts
//
// SEE: web/src/lib/components/PlayerPhoto.svelte
// SEE: web/src/lib/styles/tokens.css
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import type { PanelPlayer } from '../../../src/lib/schedule/types';

import PlayerPhoto from '../../../src/lib/components/PlayerPhoto.svelte';

const source = readFileSync(
	join(import.meta.dirname, '../../../src/lib/components/PlayerPhoto.svelte'),
	'utf8'
);

function rule(selector: RegExp): string {
	return selector.exec(source)?.[1] ?? '';
}

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

	it('keeps the leader photo frame and photo sizes', () => {
		const frame = rule(/\.photo-frame\s*\{([^}]*)\}/);
		expect(frame).toMatch(/width:\s*var\(--leader-photo-width\);/);
		expect(frame).toMatch(/height:\s*var\(--leader-photo-height\);/);
		const img = rule(/\n\timg\s*\{([^}]*)\}/);
		expect(img).toMatch(/width:\s*var\(--leader-photo-scale\);/);
		expect(img).toMatch(/bottom:\s*0;/);
		expect(img).toMatch(/left:\s*50%;/);
		expect(img).toMatch(/translate:\s*-50% 0;/);
		expect(img).not.toMatch(/(^|[^-])height:/);
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

	it('sizes the star photo by the column height, never wider than the column, bottom-centered', () => {
		const img = rule(/\.star img\s*\{([^}]*)\}/);
		expect(img).toMatch(/height:\s*100%;/);
		expect(img).toMatch(/width:\s*auto;/);
		expect(img).toMatch(/max-width:\s*100%;/);
		expect(img).toMatch(/object-fit:\s*contain;/);
		expect(img).toMatch(/object-position:\s*bottom;/);
		expect(img).not.toContain('--star-photo-scale');
	});

	it('keeps the glow, the left divider and the frame filling its column', () => {
		const star = rule(/\.star\s*\{([^}]*)\}/);
		expect(star).toMatch(/width:\s*100%;/);
		expect(star).toMatch(/height:\s*100%;/);
		expect(star).toMatch(/border-left:\s*var\(--hairline\) solid var\(--color-divider\);/);
		expect(star).toMatch(/background:\s*var\(--star-glow\), var\(--color-frame-fill\);/);
	});
});
