// web/tests/lib/components/BlueprintFrame.test.ts
//
// Tests for the BlueprintFrame component.
//
// Tested:
// - Renders its content inside the frame
// - Draws four registration marks, hidden from assistive technology
//
// What is covered:
// - Its only state
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/BlueprintFrame.test.ts
//
// SEE: web/src/lib/components/BlueprintFrame.svelte
import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it } from 'vitest';

import BlueprintFrame from '../../../src/lib/components/BlueprintFrame.svelte';

function renderFrame() {
	return render(BlueprintFrame, {
		props: { children: createRawSnippet(() => ({ render: () => '<p>Inside</p>' })) }
	});
}

describe('BlueprintFrame', () => {
	it('renders its content inside the frame', () => {
		const { container } = renderFrame();
		const frame = container.querySelector('.blueprint-frame');
		expect(frame?.contains(screen.getByText('Inside'))).toBe(true);
	});

	it('draws four registration marks, one per corner', () => {
		const { container } = renderFrame();
		for (const corner of ['tl', 'tr', 'bl', 'br']) {
			expect(container.querySelectorAll(`.blueprint-mark-${corner}`)).toHaveLength(1);
		}
		expect(container.querySelectorAll('.blueprint-mark')).toHaveLength(4);
	});

	it('hides the registration marks from assistive technology', () => {
		const { container } = renderFrame();
		for (const mark of container.querySelectorAll('.blueprint-mark')) {
			expect(mark.getAttribute('aria-hidden')).toBe('true');
		}
	});
});
