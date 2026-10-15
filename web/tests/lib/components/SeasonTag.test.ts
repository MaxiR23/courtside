// web/tests/lib/components/SeasonTag.test.ts
//
// Tests for the SeasonTag component.
//
// Tested:
// - Renders the text it is given
// - The size, letter spacing, border and color come from tokens in its source
//
// What is covered:
// - The tag drawn from props; jsdom does no layout, so styles are asserted in the source
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SeasonTag.test.ts
//
// SEE: web/src/lib/components/SeasonTag.svelte
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import SeasonTag from '../../../src/lib/components/SeasonTag.svelte';

describe('SeasonTag', () => {
	it('renders the text', () => {
		render(SeasonTag, { props: { text: 'Season 2004-05' } });
		expect(screen.getByText('Season 2004-05')).toBeTruthy();
	});

	it('takes its size, letter spacing, border and color from tokens', () => {
		const source = readFileSync(
			join(__dirname, '..', '..', '..', 'src', 'lib', 'components', 'SeasonTag.svelte'),
			'utf8'
		);
		expect(source).toContain('font-size: var(--past-tag-size)');
		expect(source).toContain('letter-spacing: var(--past-tag-letter-spacing)');
		expect(source).toContain('border: var(--hairline) solid var(--color-accent)');
		expect(source).toContain('color: var(--color-accent-light)');
	});
});
