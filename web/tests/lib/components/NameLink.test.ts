// web/tests/lib/components/NameLink.test.ts
//
// Tests for the NameLink component.
//
// Tested:
// - Renders the text as a link to the href
// - Renders plain text with no link when the href is null
//
// What is covered:
// - Both states: with and without an href
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NameLink.test.ts
//
// SEE: web/src/lib/components/NameLink.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import NameLink from '../../../src/lib/components/NameLink.svelte';

describe('NameLink', () => {
	it('renders the text as a link to the href', () => {
		render(NameLink, { props: { href: '/team/gsw' as ResolvedPathname, text: 'Warriors' } });
		const link = screen.getByRole('link', { name: 'Warriors' });
		expect(link.getAttribute('href')).toBe('/team/gsw');
		expect(link.classList.contains('name-link')).toBe(true);
	});

	it('renders plain text with no link when the href is null', () => {
		render(NameLink, { props: { href: null, text: 'Warriors' } });
		expect(screen.queryByRole('link')).toBeNull();
		expect(screen.getByText('Warriors')).toBeTruthy();
	});
});
