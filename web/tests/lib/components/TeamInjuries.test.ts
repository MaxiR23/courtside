// web/tests/lib/components/TeamInjuries.test.ts
//
// Tests for the TeamInjuries component.
//
// Tested:
// - One row per injury with the name, line, status tag and comment
// - No comment paragraph and no line when they are null
// - "No injuries reported." with an empty list
//
// What is covered:
// - Each state the section shows
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamInjuries.test.ts
//
// SEE: web/src/lib/components/TeamInjuries.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamInjuries from '../../../src/lib/components/TeamInjuries.svelte';
import type { TeamInjuryRow } from '../../../src/lib/team/types';

const injuries: TeamInjuryRow[] = [
	{ name: 'Chet Holmgren', line: '#7 · F-C', status: 'out', comment: 'Hip, out for the season' },
	{ name: 'Nikola Rookie', line: null, status: 'questionable', comment: null }
];

describe('TeamInjuries', () => {
	it('shows each injury with its line, tag and comment', () => {
		render(TeamInjuries, { props: { injuries } });
		expect(screen.getAllByRole('listitem')).toHaveLength(2);
		expect(screen.getByText('Chet Holmgren')).toBeTruthy();
		expect(screen.getByText('#7 · F-C')).toBeTruthy();
		expect(screen.getByText('Out')).toBeTruthy();
		expect(screen.getByText('Hip, out for the season')).toBeTruthy();
		expect(screen.getByText('Questionable')).toBeTruthy();
	});

	it('shows no line and no comment paragraph when they are null', () => {
		const { container } = render(TeamInjuries, { props: { injuries: [injuries[1]!] } });
		expect(container.querySelector('.detail')).toBeNull();
		expect(container.querySelector('.comment')).toBeNull();
	});

	it('says no injuries were reported with an empty list', () => {
		render(TeamInjuries, { props: { injuries: [] } });
		expect(screen.getByText('No injuries reported.')).toBeTruthy();
		expect(screen.queryByRole('listitem')).toBeNull();
	});
});
