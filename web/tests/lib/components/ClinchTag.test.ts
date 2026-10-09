// web/tests/lib/components/ClinchTag.test.ts
//
// Tests for the ClinchTag component.
//
// Tested:
// - Draws the code with the accent look for *, z, y and x
// - Draws the code with the ink look for xp and pb
// - Draws the code with the muted look for e
//
// What is covered:
// - The tone classes; jsdom does not compute the colors
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/ClinchTag.test.ts
//
// SEE: web/src/lib/components/ClinchTag.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import ClinchTag from '../../../src/lib/components/ClinchTag.svelte';
import type { ClinchView } from '../../../src/lib/standings/types';

const draw = (clinch: ClinchView) => {
	render(ClinchTag, { props: { clinch } });
	return screen.getByText(clinch.code);
};

describe('ClinchTag', () => {
	it('draws the code with the accent look for *, z, y and x', () => {
		for (const code of ['*', 'z', 'y', 'x']) {
			const { unmount } = render(ClinchTag, { props: { clinch: { code, tone: 'accent' } } });
			const tag = screen.getByText(code);
			expect(tag.classList.contains('accent')).toBe(true);
			unmount();
		}
	});

	it('draws the code with the ink look for xp and pb', () => {
		for (const code of ['xp', 'pb']) {
			const { unmount } = render(ClinchTag, { props: { clinch: { code, tone: 'ink' } } });
			expect(screen.getByText(code).classList.contains('ink')).toBe(true);
			unmount();
		}
	});

	it('draws the code with the muted look for e', () => {
		const tag = draw({ code: 'e', tone: 'muted' });
		expect(tag.classList.contains('muted')).toBe(true);
		expect(tag.classList.contains('accent')).toBe(false);
	});
});
