// web/tests/lib/components/AllStarLiveDot.test.ts
//
// Tests for the AllStarLiveDot component.
//
// Tested:
// - The dot is hidden from assistive technology
// - It pulses with the live dot params when animation is supported
// - It does not animate under reduced motion
//
// What is covered:
// - The dot drawn with a fake animate; no real animation runs
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarLiveDot.test.ts
//
// SEE: web/src/lib/components/AllStarLiveDot.svelte
import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import AllStarLiveDot from '../../../src/lib/components/AllStarLiveDot.svelte';

afterEach(() => {
	vi.unstubAllGlobals();
	delete (HTMLElement.prototype as { animate?: unknown }).animate;
});

describe('AllStarLiveDot', () => {
	it('is hidden from assistive technology', () => {
		const { container } = render(AllStarLiveDot);
		expect(container.querySelector('.live-dot')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('pulses forever when animation is supported', () => {
		const animate = vi.fn(() => ({ cancel: () => {} }));
		(HTMLElement.prototype as { animate?: unknown }).animate = animate;
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		render(AllStarLiveDot);
		expect(animate).toHaveBeenCalledTimes(1);
		const options = (animate.mock.calls[0] as unknown[])[1] as { iterations: number };
		expect(options.iterations).toBe(Infinity);
	});

	it('does not animate under reduced motion', () => {
		const animate = vi.fn(() => ({ cancel: () => {} }));
		(HTMLElement.prototype as { animate?: unknown }).animate = animate;
		vi.stubGlobal('matchMedia', () => ({ matches: true }));
		render(AllStarLiveDot);
		expect(animate).not.toHaveBeenCalled();
	});
});
