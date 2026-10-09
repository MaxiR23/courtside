// web/tests/lib/components/PlayerAvatar.test.ts
//
// Tests for the PlayerAvatar component.
//
// Tested:
// - A lazy image with the name as its alt text
// - Initials with no photo, and after the image fails to load
// - A new photo URL tries again after a failure
// - The roster, leader and search size classes
//
// What is covered:
// - Each state the avatar shows, plus the error event
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayerAvatar.test.ts
//
// SEE: web/src/lib/components/PlayerAvatar.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import PlayerAvatar from '../../../src/lib/components/PlayerAvatar.svelte';

describe('PlayerAvatar', () => {
	it('shows a lazy image with the name as alt text', () => {
		render(PlayerAvatar, {
			props: { name: 'Chet Holmgren', photo: 'https://example.com/a.png', size: 'roster' }
		});
		const img = screen.getByRole('img', { name: 'Chet Holmgren' });
		expect(img.getAttribute('src')).toBe('https://example.com/a.png');
		expect(img.getAttribute('loading')).toBe('lazy');
	});

	it('shows the first letters of the first and last words with no photo', () => {
		render(PlayerAvatar, {
			props: { name: 'shai gilgeous-alexander', photo: null, size: 'roster' }
		});
		const placeholder = screen.getByRole('img', { name: 'shai gilgeous-alexander' });
		expect(placeholder.textContent).toBe('SG');
	});

	it('shows one initial for a one-word name', () => {
		render(PlayerAvatar, { props: { name: 'Nene', photo: null, size: 'roster' } });
		expect(screen.getByRole('img', { name: 'Nene' }).textContent).toBe('N');
	});

	it('shows the initials after the image fails to load', async () => {
		render(PlayerAvatar, {
			props: { name: 'Chet Holmgren', photo: 'https://example.com/a.png', size: 'roster' }
		});
		await fireEvent.error(screen.getByRole('img', { name: 'Chet Holmgren' }));
		const placeholder = screen.getByRole('img', { name: 'Chet Holmgren' });
		expect(placeholder.tagName).toBe('SPAN');
		expect(placeholder.textContent).toBe('CH');
	});

	it('tries again when the photo URL changes', async () => {
		const { rerender } = render(PlayerAvatar, {
			props: { name: 'Chet Holmgren', photo: 'https://example.com/a.png', size: 'roster' }
		});
		await fireEvent.error(screen.getByRole('img', { name: 'Chet Holmgren' }));
		await rerender({ name: 'Chet Holmgren', photo: 'https://example.com/b.png', size: 'roster' });
		expect(screen.getByRole('img', { name: 'Chet Holmgren' }).getAttribute('src')).toBe(
			'https://example.com/b.png'
		);
	});

	it('uses the roster size class', () => {
		const { container } = render(PlayerAvatar, {
			props: { name: 'A B', photo: null, size: 'roster' }
		});
		expect(container.querySelector('.avatar')?.classList.contains('roster')).toBe(true);
	});

	it('uses the leader size class', () => {
		const { container } = render(PlayerAvatar, {
			props: { name: 'A B', photo: null, size: 'leader' }
		});
		expect(container.querySelector('.avatar')?.classList.contains('leader')).toBe(true);
	});

	it('uses the search size class', () => {
		const { container } = render(PlayerAvatar, {
			props: { name: 'A B', photo: null, size: 'search' }
		});
		expect(container.querySelector('.avatar')?.classList.contains('search')).toBe(true);
	});
});
