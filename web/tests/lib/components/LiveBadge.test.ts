// web/tests/lib/components/LiveBadge.test.ts
//
// Tests for the LiveBadge component.
//
// Tested:
// - Reads LIVE as text, not as a dot
// - Reads EN VIVO as text with a Spanish browser preference
//
// What is covered:
// - Its only state, in English and in Spanish
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/LiveBadge.test.ts
//
// SEE: web/src/lib/components/LiveBadge.svelte
import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../../prefer-languages';

import LiveBadge from '../../../src/lib/components/LiveBadge.svelte';

afterEach(() => {
	vi.restoreAllMocks();
});

describe('LiveBadge', () => {
	it('reads LIVE as text, not as a dot', () => {
		const { container } = render(LiveBadge);
		expect(container.querySelector('.live-badge')?.textContent).toBe('LIVE');
	});

	it('reads EN VIVO as text with a Spanish browser preference', () => {
		preferLanguages(['es-ES']);
		const { container } = render(LiveBadge);
		expect(container.querySelector('.live-badge')?.textContent).toBe('EN VIVO');
	});
});
