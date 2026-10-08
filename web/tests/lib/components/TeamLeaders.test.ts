// web/tests/lib/components/TeamLeaders.test.ts
//
// Tests for the TeamLeaders component.
//
// Tested:
// - One card per leader with the label, value, name, line and avatar
// - Initials for a leader with no photo
// - No link inside a card
//
// What is covered:
// - A full section and a section with one card
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamLeaders.test.ts
//
// SEE: web/src/lib/components/TeamLeaders.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamLeaders from '../../../src/lib/components/TeamLeaders.svelte';
import type { LeadersSection } from '../../../src/lib/team/types';

const leaders: LeadersSection = {
	meta: '2025-26 · per game',
	cards: [
		{
			label: 'Points',
			value: '31.8',
			name: 'Shai Gilgeous-Alexander',
			line: '#2 · Guard',
			photo: 'https://example.com/sga.png'
		},
		{ label: 'Rebounds', value: '8.9', name: 'Chet Holmgren', line: 'Forward-Center', photo: null }
	]
};

describe('TeamLeaders', () => {
	it('shows one card per leader with its label, value, name and line', () => {
		render(TeamLeaders, { props: { leaders } });
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
		render(TeamLeaders, { props: { leaders } });
		expect(screen.getByRole('img', { name: 'Shai Gilgeous-Alexander' }).getAttribute('src')).toBe(
			'https://example.com/sga.png'
		);
		expect(screen.getByRole('img', { name: 'Chet Holmgren' }).textContent).toBe('CH');
	});

	it('has no link in a card', () => {
		render(TeamLeaders, { props: { leaders } });
		expect(screen.queryByRole('link')).toBeNull();
	});

	it('shows a single card', () => {
		render(TeamLeaders, { props: { leaders: { ...leaders, cards: [leaders.cards[0]!] } } });
		expect(screen.getAllByRole('listitem')).toHaveLength(1);
	});
});
