// web/tests/lib/components/CupTeamLine.test.ts
//
// Tests for the CupTeamLine component.
//
// Tested:
// - The line is one link to the Cup page
// - The group name in accent text, then the Cup record
//
// What is covered:
// - The line as a link; the accent color is CSS and jsdom does no layout, so the class is checked
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/CupTeamLine.test.ts
//
// SEE: web/src/lib/components/CupTeamLine.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import CupTeamLine from '../../../src/lib/components/CupTeamLine.svelte';

const line = { group: 'East Group A', record: '3-1' };

describe('CupTeamLine', () => {
	it('links the line to the Cup page', () => {
		render(CupTeamLine, { props: { line } });
		expect(screen.getByRole('link', { name: 'East Group A · 3-1' }).getAttribute('href')).toBe(
			'/cup'
		);
	});

	it('shows the group name in accent text', () => {
		const { container } = render(CupTeamLine, { props: { line } });
		const group = container.querySelector('.group');
		expect(group?.textContent).toBe('East Group A');
	});

	it('shows the Cup record after the group', () => {
		const { container } = render(CupTeamLine, { props: { line } });
		expect(container.querySelector('.cup-line')?.textContent).toBe('East Group A · 3-1');
	});
});
