// web/tests/lib/components/Button.test.ts
//
// Tests for the Button component.
//
// Tested:
// - Renders a link when given an href and a button when given an action
// - Calls the action on click
// - Wraps only the primary variant in a blueprint frame
//
// What is covered:
// - Both variants, both element kinds, user interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Button.test.ts
//
// SEE: web/src/lib/components/Button.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import Button from '../../../src/lib/components/Button.svelte';

const href = '/' as ResolvedPathname;

describe('Button', () => {
	it('renders a link to the given href with its label', () => {
		render(Button, { props: { variant: 'secondary', label: 'Schedule', href } });
		const link = screen.getByRole('link', { name: 'Schedule' });
		expect(link.getAttribute('href')).toBe('/');
	});

	it('renders a button of type button when given an action', () => {
		render(Button, { props: { variant: 'primary', label: 'Go', onclick: () => {} } });
		const button = screen.getByRole('button', { name: 'Go' });
		expect(button.getAttribute('type')).toBe('button');
	});

	it('calls the action when the button is clicked', async () => {
		const onclick = vi.fn();
		render(Button, { props: { variant: 'secondary', label: 'Go', onclick } });
		await fireEvent.click(screen.getByRole('button', { name: 'Go' }));
		expect(onclick).toHaveBeenCalledTimes(1);
	});

	it('wraps the primary variant in a blueprint frame', () => {
		const { container } = render(Button, { props: { variant: 'primary', label: 'Go', href } });
		expect(container.querySelectorAll('.blueprint-mark')).toHaveLength(4);
	});

	it('renders the secondary variant without a blueprint frame', () => {
		const { container } = render(Button, { props: { variant: 'secondary', label: 'Go', href } });
		expect(container.querySelector('.blueprint-frame')).toBeNull();
		expect(container.querySelectorAll('.blueprint-mark')).toHaveLength(0);
	});
});
