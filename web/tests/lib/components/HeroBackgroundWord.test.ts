// web/tests/lib/components/HeroBackgroundWord.test.ts
//
// Tests for the HeroBackgroundWord component.
//
// Tested:
// - Shows the word
// - Has the active class only when active
// - Sets --side-accent to the accent, and to the neutral accent token when it is null
// - Animates on an active change when motion is allowed, and not with reduced motion
//
// What is covered:
// - Each state of the word, plus the crossfade with and without reduced motion
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/HeroBackgroundWord.test.ts
//
// SEE: web/src/lib/components/HeroBackgroundWord.svelte
import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import HeroBackgroundWord from '../../../src/lib/components/HeroBackgroundWord.svelte';

afterEach(() => {
	vi.unstubAllGlobals();
	Reflect.deleteProperty(HTMLElement.prototype, 'animate');
});

const wordOf = (container: HTMLElement) => container.querySelector('.word') as HTMLElement;

describe('HeroBackgroundWord', () => {
	it('shows the word, active only when it is', () => {
		const idle = render(HeroBackgroundWord, {
			props: { text: 'Varga', accent: null, active: false }
		});
		expect(wordOf(idle.container).textContent).toBe('Varga');
		expect(wordOf(idle.container).classList.contains('active')).toBe(false);
		idle.unmount();
		const on = render(HeroBackgroundWord, { props: { text: 'Varga', accent: null, active: true } });
		expect(wordOf(on.container).classList.contains('active')).toBe(true);
	});

	it('sets --side-accent from the accent, and the neutral accent when it is null', () => {
		const accent = render(HeroBackgroundWord, {
			props: { text: 'Varga', accent: '#1f6f8b', active: true }
		});
		expect(wordOf(accent.container).style.getPropertyValue('--side-accent')).toBe('#1f6f8b');
		accent.unmount();
		const neutral = render(HeroBackgroundWord, {
			props: { text: 'Varga', accent: null, active: true }
		});
		expect(wordOf(neutral.container).style.getPropertyValue('--side-accent')).toBe(
			'var(--identity-neutral-accent)'
		);
	});

	it('animates when its active state changes, and not with reduced motion', async () => {
		const animate = vi.fn(() => ({ cancel: vi.fn() }));
		Object.assign(HTMLElement.prototype, { animate });
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const first = render(HeroBackgroundWord, {
			props: { text: 'Varga', accent: null, active: false }
		});
		expect(animate).not.toHaveBeenCalled();
		await first.rerender({ text: 'Varga', accent: null, active: true });
		expect(animate).toHaveBeenCalledOnce();
		first.unmount();
		animate.mockClear();
		vi.stubGlobal('matchMedia', () => ({ matches: true }));
		const second = render(HeroBackgroundWord, {
			props: { text: 'Varga', accent: null, active: false }
		});
		await second.rerender({ text: 'Varga', accent: null, active: true });
		expect(animate).not.toHaveBeenCalled();
	});
});
