// web/tests/lib/components/PlayerAvatar.test.ts
//
// Tests for the PlayerAvatar component.
//
// Tested:
// - A lazy image with the name as its alt text
// - Initials with no photo, and after the image fails to load
// - A new photo URL tries again after a failure
// - A first and last name as the name: initials, alt text and aria label from the joined name
// - The roster, leader, team-leader, search, cup-card, playoffs-avatar, playoffs-card, playoffs-mvp and playoffs-conference-mvp size classes
// - The eight All-Star size classes
// - The hero plate size covers its 82% box anchored bottom center, and allstar-plate stays as it is
// - The clip prop: clip-bottom only with clip bottom, and the safe end alignment rules
//
// What is covered:
// - Each state the avatar shows, plus the error event
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayerAvatar.test.ts
//
// SEE: web/src/lib/components/PlayerAvatar.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import PlayerAvatar from '../../../src/lib/components/PlayerAvatar.svelte';

const style = (
	readFileSync(
		join(__dirname, '..', '..', '..', 'src/lib/components/PlayerAvatar.svelte'),
		'utf8'
	).match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1] ?? ''
).replace(/\/\*[\s\S]*?\*\//g, '');
const declarations = (selector: string): string[] =>
	[...style.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
		.filter((m) => m[1]!.split(',').some((s) => s.trim() === selector))
		.flatMap((m) =>
			m[2]!
				.split(';')
				.map((d) => d.trim().replace(/\s+/g, ' '))
				.filter(Boolean)
		);

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

	it('takes a first and last name', () => {
		render(PlayerAvatar, {
			props: { name: { firstName: 'Jimmy', lastName: 'Butler III' }, photo: null, size: 'roster' }
		});
		expect(screen.getByRole('img', { name: 'Jimmy Butler III' }).textContent).toBe('JB');
	});

	it('uses the joined first and last name as alt text', () => {
		render(PlayerAvatar, {
			props: {
				name: { firstName: 'Jimmy', lastName: 'Butler III' },
				photo: 'https://example.com/a.png',
				size: 'roster'
			}
		});
		expect(screen.getByAltText('Jimmy Butler III').getAttribute('src')).toBe(
			'https://example.com/a.png'
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

	it('uses the playoffs-mvp and playoffs-conference-mvp size classes and shows initials without a photo', () => {
		for (const size of ['playoffs-mvp', 'playoffs-conference-mvp'] as const) {
			const { container, unmount } = render(PlayerAvatar, {
				props: { name: 'Ada Byrne', photo: null, size }
			});
			expect(container.querySelector('.avatar')?.classList.contains(size)).toBe(true);
			expect(screen.getByRole('img', { name: 'Ada Byrne' }).textContent).toBe('AB');
			unmount();
		}
	});

	it('uses each All-Star size class', () => {
		for (const size of [
			'allstar-box',
			'allstar-top5',
			'allstar-top5-mobile',
			'allstar-roster',
			'allstar-roster-mobile',
			'allstar-mvp',
			'allstar-plate',
			'allstar-plate-cover'
		] as const) {
			const { container, unmount } = render(PlayerAvatar, {
				props: { name: 'A B', photo: null, size }
			});
			expect(container.querySelector('.avatar')?.classList.contains(size)).toBe(true);
			unmount();
		}
	});

	it('covers the hero plate box anchored at the bottom center, and leaves allstar-plate as it is', () => {
		expect(declarations('.allstar-plate-cover')).toContain(
			'height: var(--allstar-plate-cover-height)'
		);
		expect(declarations('.allstar-plate-cover img')).toEqual(
			expect.arrayContaining(['object-fit: cover', 'object-position: bottom center'])
		);
		expect(declarations('.allstar-plate')).toContain('height: var(--allstar-plate-photo-height)');
		expect(declarations('.allstar-plate img')).toEqual(
			expect.arrayContaining(['object-fit: contain', 'object-position: bottom'])
		);
	});
});

describe('PlayerAvatar clip prop', () => {
	it('clips only at the bottom with clip bottom', () => {
		const { container } = render(PlayerAvatar, {
			props: {
				name: 'Kai Lowe',
				photo: 'https://example.com/a.png',
				size: 'playoffs-conference-mvp',
				clip: 'bottom'
			}
		});
		const avatar = container.querySelector('.avatar');
		expect(avatar?.classList.contains('clip-bottom')).toBe(true);
		expect(avatar?.classList.contains('playoffs-conference-mvp')).toBe(true);
		expect(container.querySelector('img')).not.toBeNull();
	});

	it('keeps the default clip without the prop', () => {
		for (const size of ['roster', 'playoffs-conference-mvp'] as const) {
			const { container, unmount } = render(PlayerAvatar, {
				props: { name: 'Kai Lowe', photo: 'https://example.com/a.png', size }
			});
			expect(container.querySelector('.avatar')?.classList.contains('clip-bottom')).toBe(false);
			unmount();
		}
	});

	it('anchors the image with safe end alignment under clip bottom', () => {
		expect(style.length).toBeGreaterThan(0);
		expect(declarations('.avatar.clip-bottom')).toEqual(
			expect.arrayContaining([
				'display: flex',
				'flex-direction: column',
				'justify-content: safe flex-end',
				'align-items: center'
			])
		);
		expect(declarations('.avatar.clip-bottom img')).toEqual(
			expect.arrayContaining(['position: static', 'translate: none'])
		);
		expect(declarations('.avatar')).toContain('overflow: hidden');
	});
});
