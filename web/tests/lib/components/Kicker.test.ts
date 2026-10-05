// web/tests/lib/components/Kicker.test.ts
//
// Tests for the Kicker component.
//
// Tested:
// - Shows the given text
//
// What is covered:
// - Its only state
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Kicker.test.ts
//
// SEE: web/src/lib/components/Kicker.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import Kicker from '../../../src/lib/components/Kicker.svelte';

describe('Kicker', () => {
	it('shows the given text', () => {
		render(Kicker, { props: { text: '10:30 PM ET · Chase Center' } });
		expect(screen.getByText('10:30 PM ET · Chase Center')).toBeTruthy();
	});
});
