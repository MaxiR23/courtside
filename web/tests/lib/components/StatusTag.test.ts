// web/tests/lib/components/StatusTag.test.ts
//
// Tests for the StatusTag component.
//
// Tested:
// - Shows Tonight, Live now or Final for each status
// - Shows Esta noche, En vivo or Final with a Spanish browser preference
//
// What is covered:
// - Every status, in English and in Spanish
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/StatusTag.test.ts
//
// SEE: web/src/lib/components/StatusTag.svelte
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../../prefer-languages';

import StatusTag from '../../../src/lib/components/StatusTag.svelte';

afterEach(() => {
	vi.restoreAllMocks();
});

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

describe('StatusTag with a Spanish browser preference', () => {
	it('shows Esta noche for a scheduled game tonight', () => {
		preferLanguages(['es-ES']);
		render(StatusTag, { props: { status: 'tonight' } });
		expect(screen.getByText('Esta noche')).toBeTruthy();
	});

	it('shows En vivo for a live game', () => {
		preferLanguages(['es-ES']);
		render(StatusTag, { props: { status: 'live' } });
		expect(screen.getByText('En vivo')).toBeTruthy();
	});

	it('shows Final for a finished game', () => {
		preferLanguages(['es-ES']);
		render(StatusTag, { props: { status: 'final' } });
		expect(screen.getByText('Final')).toBeTruthy();
	});
});
