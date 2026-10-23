// web/tests/lib/components/PlayerAvatar.test.ts
//
// Tests for the PlayerAvatar component.
//
// Tested:
// - A lazy image with the name as its alt text
// - Initials with no photo, and after the image fails to load
// - A new photo URL tries again after a failure
// - The roster, leader, team-leader, search, cup-card, playoffs-avatar and playoffs-card size classes
// - The seven All-Star size classes
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

	it('uses the team-leader size class and shows initials without a photo', () => {
		const { container } = render(PlayerAvatar, {
			props: { name: 'Ada Byrne', photo: null, size: 'team-leader' }
		});
		expect(container.querySelector('.avatar')?.classList.contains('team-leader')).toBe(true);
		expect(screen.getByRole('img', { name: 'Ada Byrne' }).textContent).toBe('AB');
	});

	it('uses the search size class', () => {
		const { container } = render(PlayerAvatar, {
			props: { name: 'A B', photo: null, size: 'search' }
		});
		expect(container.querySelector('.avatar')?.classList.contains('search')).toBe(true);
	});

	it('uses the cup-card size class', () => {
		const { container } = render(PlayerAvatar, {
			props: { name: 'A B', photo: null, size: 'cup-card' }
		});
		expect(container.querySelector('.avatar')?.classList.contains('cup-card')).toBe(true);
	});

	it('uses the playoffs-card size class', () => {
		const { container } = render(PlayerAvatar, {
			props: { name: 'A B', photo: null, size: 'playoffs-card' }
		});
		expect(container.querySelector('.avatar')?.classList.contains('playoffs-card')).toBe(true);
	});

	it('uses the playoffs-avatar size class and shows initials without a photo', () => {
		const { container } = render(PlayerAvatar, {
			props: { name: 'Ada Byrne', photo: null, size: 'playoffs-avatar' }
		});
		expect(container.querySelector('.avatar')?.classList.contains('playoffs-avatar')).toBe(true);
		expect(screen.getByRole('img', { name: 'Ada Byrne' }).textContent).toBe('AB');
	});

	it('uses each All-Star size class', () => {
		for (const size of [
			'allstar-box',
			'allstar-top5',
			'allstar-top5-mobile',
			'allstar-roster',
			'allstar-roster-mobile',
			'allstar-mvp',
			'allstar-plate'
		] as const) {
			const { container, unmount } = render(PlayerAvatar, {
				props: { name: 'A B', photo: null, size }
			});
			expect(container.querySelector('.avatar')?.classList.contains(size)).toBe(true);
			unmount();
		}
	});
});
