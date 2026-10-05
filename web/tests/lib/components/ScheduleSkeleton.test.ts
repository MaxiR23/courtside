// web/tests/lib/components/ScheduleSkeleton.test.ts
//
// Tests for the ScheduleSkeleton component.
//
// Tested:
// - A seven-day strip and three game cards, each in a blueprint frame
// - The schedule anchor, marked busy, with the bones hidden from assistive tech
// - No text
// - The shimmer loops, and does not run with reduced motion
//
// What is covered:
// - The single state it shows, plus reduced motion
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/ScheduleSkeleton.test.ts
//
// SEE: web/src/lib/components/ScheduleSkeleton.svelte
import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ScheduleSkeleton from '../../../src/lib/components/ScheduleSkeleton.svelte';

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	Reflect.deleteProperty(HTMLElement.prototype, 'animate');
});

describe('ScheduleSkeleton', () => {
	it('renders a seven-day strip and three game cards', () => {
		const { container } = render(ScheduleSkeleton);
		expect(container.querySelectorAll('.day-bone')).toHaveLength(7);
		const cards = container.querySelectorAll('.card-bone');
		expect(cards).toHaveLength(3);
		for (const card of cards) expect(card.closest('.blueprint-frame')).not.toBeNull();
	});

	it('is the schedule anchor and is marked busy', () => {
		const { container } = render(ScheduleSkeleton);
		expect(container.querySelector('section#schedule')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.bones')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('holds no text', () => {
		const { container } = render(ScheduleSkeleton);
		expect(container.textContent?.trim()).toBe('');
	});

	it('shimmers, and not with reduced motion', () => {
		const animate = vi.fn<(keyframes: unknown, options: unknown) => { cancel: () => void }>(() => ({
			cancel: vi.fn()
		}));
		Object.assign(HTMLElement.prototype, { animate });
		const looped = () =>
			animate.mock.calls.some(
				(call) => (call[1] as { iterations?: number } | undefined)?.iterations === Infinity
			);
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const first = render(ScheduleSkeleton);
		expect(looped()).toBe(true);
		first.unmount();
		animate.mockClear();
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: query === '(prefers-reduced-motion: reduce)'
		}));
		render(ScheduleSkeleton);
		expect(animate).not.toHaveBeenCalled();
	});
});
