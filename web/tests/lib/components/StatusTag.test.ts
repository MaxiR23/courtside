// web/tests/lib/components/StatusTag.test.ts
//
// Tests for the StatusTag component.
//
// Tested:
// - Shows Tonight, Live now or Final for each status
//
// What is covered:
// - Every status
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/StatusTag.test.ts
//
// SEE: web/src/lib/components/StatusTag.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import StatusTag from '../../../src/lib/components/StatusTag.svelte';

describe('StatusTag', () => {
	it('shows Tonight for a scheduled game tonight', () => {
		render(StatusTag, { props: { status: 'tonight' } });
		expect(screen.getByText('Tonight')).toBeTruthy();
	});

	it('shows Live now for a live game', () => {
		render(StatusTag, { props: { status: 'live' } });
		expect(screen.getByText('Live now')).toBeTruthy();
	});

	it('shows Final for a finished game', () => {
		render(StatusTag, { props: { status: 'final' } });
		expect(screen.getByText('Final')).toBeTruthy();
	});
});
