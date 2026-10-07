// web/tests/lib/components/MessageRow.test.ts
//
// Tests for the MessageRow component.
//
// Tested:
// - Shows its text inside a blueprint frame
// - Shows a link after the message when one is given, and none without it
//
// What is covered:
// - Both states: with and without a link
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/MessageRow.test.ts
//
// SEE: web/src/lib/components/MessageRow.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import MessageRow from '../../../src/lib/components/MessageRow.svelte';

describe('MessageRow', () => {
	it('shows its text inside a blueprint frame', () => {
		render(MessageRow, { props: { text: 'Nothing here.' } });
		expect(screen.getByText('Nothing here.').closest('.blueprint-frame')).not.toBeNull();
	});

	it('shows a link after the message when one is given', () => {
		render(MessageRow, {
			props: {
				text: 'Game not found.',
				link: { href: '/' as ResolvedPathname, label: 'All games' }
			}
		});
		const link = screen.getByRole('link', { name: 'All games' });
		expect(link.getAttribute('href')).toBe('/');
		expect(link.closest('.blueprint-frame')).not.toBeNull();
	});

	it('shows no link without one', () => {
		render(MessageRow, { props: { text: 'Nothing here.' } });
		expect(screen.queryByRole('link')).toBeNull();
	});
});
