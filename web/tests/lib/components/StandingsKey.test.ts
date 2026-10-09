// web/tests/lib/components/StandingsKey.test.ts
//
// Tests for the StandingsKey component.
//
// Tested:
// - The Key label, seven tags with their meanings and the note
// - Spanish copy
//
// What is covered:
// - The one state it shows, in two languages; the entries come from the props layer
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/StandingsKey.test.ts
//
// SEE: web/src/lib/components/StandingsKey.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import StandingsKey from '../../../src/lib/components/StandingsKey.svelte';
import type { StandingsFeed } from '../../../src/lib/contract/standings';
import { toStandingsView } from '../../../src/lib/feed/standings-props';
import { preferLanguages } from '../../prefer-languages';

const entries = () =>
	toStandingsView(
		JSON.parse(
			readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'standings.json'), 'utf8')
		) as StandingsFeed
	).key;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('StandingsKey', () => {
	it('renders the Key label, seven tags with their meanings and the note', () => {
		const { container } = render(StandingsKey, { props: { entries: entries() } });
		expect(screen.getByText('Key')).toBeTruthy();
		expect([...container.querySelectorAll('.clinch-tag')].map((t) => t.textContent)).toEqual([
			'*',
			'z',
			'y',
			'x',
			'xp',
			'pb',
			'e'
		]);
		expect(screen.getByText('Clinched play-in')).toBeTruthy();
		expect(screen.getByText('Eliminated')).toBeTruthy();
		expect(container.querySelector('.note')?.textContent).toContain('dashed lines');
	});

	it('renders in Spanish', () => {
		preferLanguages(['es-ES']);
		render(StandingsKey, { props: { entries: entries() } });
		expect(screen.getByText('Leyenda')).toBeTruthy();
		expect(screen.getByText('Eliminado')).toBeTruthy();
	});
});
