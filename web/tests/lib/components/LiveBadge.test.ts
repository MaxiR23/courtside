// web/tests/lib/components/LiveBadge.test.ts
//
// Tests for the LiveBadge component.
//
// Tested:
// - Reads LIVE as text, not as a dot
//
// What is covered:
// - Its only state
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/LiveBadge.test.ts
//
// SEE: web/src/lib/components/LiveBadge.svelte
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import LiveBadge from '../../../src/lib/components/LiveBadge.svelte';

describe('LiveBadge', () => {
	it('reads LIVE as text, not as a dot', () => {
		const { container } = render(LiveBadge);
		expect(container.querySelector('.live-badge')?.textContent).toBe('LIVE');
	});
});
