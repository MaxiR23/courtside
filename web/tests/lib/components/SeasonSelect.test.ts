// web/tests/lib/components/SeasonSelect.test.ts
//
// Tests for the SeasonSelect component.
//
// Tested:
// - A native select named "Season" with one option per season, labelled, in the order given
// - The value on show is the selected option
// - Changing the select calls onChange with the end year as a number
// - Spanish name with a Spanish browser preference
// - The select height, border and text size come from tokens in its source
//
// What is covered:
// - The select drawn from props with no fetch; jsdom does no layout, so sizes are asserted in the source
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SeasonSelect.test.ts
//
// SEE: web/src/lib/components/SeasonSelect.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import SeasonSelect from '../../../src/lib/components/SeasonSelect.svelte';
import { preferLanguages } from '../../prefer-languages';

const seasons = [
	{ season: 2027, seasonLabel: '2026-27' },
	{ season: 2026, seasonLabel: '2025-26' },
	{ season: 1999, seasonLabel: '1998-99' }
];

afterEach(() => {
	vi.restoreAllMocks();
});

describe('SeasonSelect', () => {
	it('lists the seasons by label, in order, with the value selected', () => {
		render(SeasonSelect, { props: { seasons, value: 2026, onChange: vi.fn() } });
		const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
		expect([...select.options].map((option) => option.textContent)).toEqual([
			'2026-27',
			'2025-26',
			'1998-99'
		]);
		expect(select.value).toBe('2026');
	});

	it('calls onChange with the end year as a number', async () => {
		const onChange = vi.fn();
		render(SeasonSelect, { props: { seasons, value: 2027, onChange } });
		await fireEvent.change(screen.getByRole('combobox'), { target: { value: '1999' } });
		expect(onChange).toHaveBeenCalledWith(1999);
	});

	it('is named in Spanish for a Spanish browser', () => {
		preferLanguages(['es-ES']);
		render(SeasonSelect, { props: { seasons, value: 2027, onChange: vi.fn() } });
		expect(screen.getByRole('combobox', { name: 'Temporada' })).toBeTruthy();
	});

	it('takes its height, border and text from tokens', () => {
		const source = readFileSync(
			join(__dirname, '..', '..', '..', 'src', 'lib', 'components', 'SeasonSelect.svelte'),
			'utf8'
		);
		expect(source).toContain('height: var(--past-select-height)');
		expect(source).toContain('border: var(--hairline) solid var(--past-select-border)');
		expect(source).toContain('font-size: var(--past-select-size)');
		expect(source).toContain('letter-spacing: var(--past-select-letter-spacing)');
	});
});
