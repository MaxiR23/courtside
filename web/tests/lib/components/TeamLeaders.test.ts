// web/tests/lib/components/TeamLeaders.test.ts
//
// Tests for the TeamLeaders component.
//
// Tested:
// - One card per leader with the label, value, name, line and avatar
// - Initials for a leader with no photo
// - Each card links to its player page, with no nested interactive element
//
// What is covered:
// - A full section and a section with one card
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamLeaders.test.ts
//
// SEE: web/src/lib/components/TeamLeaders.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamLeaders from '../../../src/lib/components/TeamLeaders.svelte';
import type { LeadersSection } from '../../../src/lib/team/types';

const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;

const leaders: LeadersSection = {
	meta: '2025-26 · per game',
	cards: [
		{
			playerId: 'p-sga',
			label: 'Points',
			value: '31.8',
			name: 'Shai Gilgeous-Alexander',
			line: '#2 · Guard',
			photo: 'https://example.com/sga.png'
		},
		{
			playerId: 'p-holmgren',
			label: 'Rebounds',
			value: '8.9',
			name: 'Chet Holmgren',
			line: 'Forward-Center',
			photo: null
		}
	]
};

describe('TeamLeaders', () => {
	it('shows one card per leader with its label, value, name and line', () => {
		render(TeamLeaders, { props: { leaders, playerHref } });
		expect(screen.getAllByRole('listitem')).toHaveLength(2);
		for (const text of [
			'Points',
			'31.8',
			'Shai Gilgeous-Alexander',
			'#2 · Guard',
			'Rebounds',
			'8.9',
			'Chet Holmgren',
			'Forward-Center'
		]) {
			expect(screen.getByText(text)).toBeTruthy();
		}
	});

	it('shows the photo, or initials with none', () => {
		render(TeamLeaders, { props: { leaders, playerHref } });
		expect(screen.getByRole('img', { name: 'Shai Gilgeous-Alexander' }).getAttribute('src')).toBe(
			'https://example.com/sga.png'
		);
		expect(screen.getByRole('img', { name: 'Chet Holmgren' }).textContent).toBe('CH');
	});

	it('links each card to its player page, with nothing interactive inside', () => {
		const { container } = render(TeamLeaders, { props: { leaders, playerHref } });
		expect(screen.getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual([
			'/player/p-sga',
			'/player/p-holmgren'
		]);
		expect(container.querySelectorAll('a a, button a, a button')).toHaveLength(0);
	});

	it('shows a single card', () => {
		render(TeamLeaders, {
			props: { leaders: { ...leaders, cards: [leaders.cards[0]!] }, playerHref }
		});
		expect(screen.getAllByRole('listitem')).toHaveLength(1);
	});
});
