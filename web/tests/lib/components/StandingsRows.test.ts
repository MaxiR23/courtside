// web/tests/lib/components/StandingsRows.test.ts
//
// Tests for the StandingsRows component.
//
// Tested:
// - The six column headers in English and Spanish
// - Both rows, away first, with their values
// - The team cell is the row header and sticky; the table sits in the scroll wrapper
//
// What is covered:
// - Each state, in both languages
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/StandingsRows.test.ts
//
// SEE: web/src/lib/components/StandingsRows.svelte
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { StandingsSection } from '../../../src/lib/game/types';
import { preferLanguages } from '../../prefer-languages';

import StandingsRows from '../../../src/lib/components/StandingsRows.svelte';

afterEach(() => {
	vi.restoreAllMocks();
});

const standings: StandingsSection = {
	away: {
		code: 'GSW',
		name: 'Warriors',
		conference: '3rd West',
		record: '12–5',
		home: '7–2',
		away: '5–3',
		lastTen: '7–3'
	},
	home: {
		code: 'LAL',
		name: 'Lakers',
		conference: '1st West',
		record: '14–3',
		home: '8–1',
		away: '6–2',
		lastTen: '8–2'
	}
};

const headers = () => screen.getAllByRole('columnheader').map((h) => h.textContent);

describe('StandingsRows', () => {
	it('shows the six column headers in English', () => {
		render(StandingsRows, { props: { standings } });
		expect(headers()).toEqual(['Team', 'Conference', 'Record', 'Home', 'Away', 'Last 10']);
	});

	it('shows the six column headers in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(StandingsRows, { props: { standings } });
		expect(headers()).toEqual([
			'Equipo',
			'Conferencia',
			'Balance',
			'Local',
			'Visitante',
			'Últimos 10'
		]);
	});

	it('shows both rows, away first, with their values', () => {
		const { container } = render(StandingsRows, { props: { standings } });
		const rows = [...container.querySelectorAll('.body')].map((row) =>
			[...row.children].map((c) => c.textContent)
		);
		expect(rows).toEqual([
			['Warriors', '3rd West', '12–5', '7–2', '5–3', '7–3'],
			['Lakers', '1st West', '14–3', '8–1', '6–2', '8–2']
		]);
	});

	it('makes the team cell the sticky row header and scrolls the table', () => {
		const { container } = render(StandingsRows, { props: { standings } });
		const names = screen.getAllByRole('rowheader');
		expect(names.map((n) => n.textContent)).toEqual(['Warriors', 'Lakers']);
		for (const name of names) expect(name.classList.contains('team')).toBe(true);
		expect(container.querySelector('.scroll > [role="table"]')).not.toBeNull();
	});
});
