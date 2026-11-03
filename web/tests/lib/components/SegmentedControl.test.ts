// web/tests/lib/components/SegmentedControl.test.ts
//
// Tests for the SegmentedControl component.
//
// Tested:
// - A labeled group of buttons with aria-pressed on the current value
// - A click calls onChange with the value
//
// What is covered:
// - Pressed and not pressed options, user interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SegmentedControl.test.ts
//
// SEE: web/src/lib/components/SegmentedControl.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import SegmentedControl from '../../../src/lib/components/SegmentedControl.svelte';

const options = [
	{ value: 'all', label: 'All' },
	{ value: 'recap', label: 'Recaps' }
];

describe('SegmentedControl', () => {
	it('draws a labeled group with the current option pressed', () => {
		render(SegmentedControl, {
			props: { label: 'Type', options, value: 'recap', onChange: () => {} }
		});
		expect(screen.getByRole('group', { name: 'Type' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Recaps' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getByRole('button', { name: 'All' }).getAttribute('aria-pressed')).toBe('false');
	});

	it('calls onChange with the value of the clicked option', async () => {
		const onChange = vi.fn();
		render(SegmentedControl, { props: { label: 'Type', options, value: 'all', onChange } });
		await fireEvent.click(screen.getByRole('button', { name: 'Recaps' }));
		expect(onChange).toHaveBeenCalledWith('recap');
	});
});
