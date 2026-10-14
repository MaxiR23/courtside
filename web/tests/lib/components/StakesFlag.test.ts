// web/tests/lib/components/StakesFlag.test.ts
//
// Tests for the StakesFlag component.
//
// Tested:
// - Shows the text it is given, in its own class
// - Plain text: no link and no button
//
// What is covered:
// - The flag; the accent outline and the ellipsis are CSS and jsdom does no layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/StakesFlag.test.ts
//
// SEE: web/src/lib/components/StakesFlag.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import StakesFlag from '../../../src/lib/components/StakesFlag.svelte';

describe('StakesFlag', () => {
	it('shows the text', () => {
		render(StakesFlag, { props: { text: 'Can clinch' } });
		expect(screen.getByText('Can clinch').classList.contains('stakes-flag')).toBe(true);
	});

	it('is plain text with no link or button', () => {
		const { container } = render(StakesFlag, { props: { text: 'Game 7' } });
		expect(container.querySelector('a, button')).toBeNull();
	});
});
