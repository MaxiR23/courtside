// web/tests/lib/components/DateButton.test.ts
//
// Tests for the DateButton component.
//
// Tested:
// - A button that opens a dialog: aria-haspopup, aria-expanded false then true after a click, and a second click closes it
// - The label is a <time> with the date when one is given, and plain text when not
// - Desktop: the dialog has the panel class and is not modal; a click outside closes it, a click inside does not; Esc closes it; focus returns to the button
// - Mobile: the scrim renders; the body scroll is hidden while open and restored on close; a click on the scrim closes it; Esc closes it
// - A navigation closes the sheet
// - The button's 44px target comes from the hit target token in its source
//
// What is covered:
// - The button and its sheet drawn from props with a fake loader and a recorded calendar; no fetch, no clock
// - jsdom does no layout, so the height is asserted in the source
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/DateButton.test.ts
//
// SEE: web/src/lib/components/DateButton.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import DateButton from '../../../src/lib/components/DateButton.svelte';
import type { CalendarFeed } from '../../../src/lib/contract/calendar';

const navigation = vi.hoisted(() => ({ callbacks: [] as Array<() => void> }));
vi.mock('$app/navigation', () => ({
	afterNavigate: (cb: () => void) => {
		navigation.callbacks.push(cb);
	}
}));

const recorded = (): CalendarFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'calendar.json'), 'utf8')
	) as CalendarFeed;

const show = (layout: 'desktop' | 'mobile' = 'desktop', datetime: string | null = '1999-02-05') =>
	render(DateButton, {
		props: {
			text: 'Fri, Feb 5, 1999',
			datetime,
			layout,
			calendar: {
				load: () => Promise.resolve(recorded()),
				season: '1999',
				selectedDay: '1999-02-05',
				today: '1999-02-06',
				dayHref: (date: string) => `/day/${date}` as ResolvedPathname
			}
		}
	});

const trigger = () => screen.getByRole('button', { name: /Feb 5, 1999/ });

async function open() {
	await fireEvent.click(trigger());
	await screen.findByRole('combobox');
}

beforeEach(() => {
	navigation.callbacks = [];
});

afterEach(() => {
	vi.restoreAllMocks();
	document.body.style.overflow = '';
});

describe('DateButton', () => {
	it('is a button that opens a dialog and a second click closes it', async () => {
		show();
		expect(trigger().getAttribute('aria-haspopup')).toBe('dialog');
		expect(trigger().getAttribute('aria-expanded')).toBe('false');
		await open();
		expect(trigger().getAttribute('aria-expanded')).toBe('true');
		await fireEvent.click(trigger());
		expect(trigger().getAttribute('aria-expanded')).toBe('false');
		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('draws the label as a time with the date, or as plain text without one', () => {
		const { container, unmount } = show('desktop', '1999-02-05');
		expect(container.querySelector('time')?.getAttribute('datetime')).toBe('1999-02-05');
		unmount();
		const second = show('desktop', null);
		expect(second.container.querySelector('time')).toBeNull();
		expect(trigger().textContent).toContain('Fri, Feb 5, 1999');
	});

	it('opens a panel that is not modal on desktop', async () => {
		show('desktop');
		await open();
		const dialog = screen.getByRole('dialog');
		expect(dialog.classList.contains('panel')).toBe(true);
		expect(dialog.getAttribute('aria-modal')).toBeNull();
	});

	it('closes on a click outside, not on a click inside, on desktop', async () => {
		show('desktop');
		await open();
		await fireEvent.click(screen.getByRole('dialog'));
		expect(screen.queryByRole('dialog')).not.toBeNull();
		await fireEvent.click(document.body);
		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('closes on Esc and returns focus to the button on desktop', async () => {
		show('desktop');
		await open();
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByRole('dialog')).toBeNull();
		await waitFor(() => expect(document.activeElement).toBe(trigger()));
	});

	it('returns focus to the button after Close', async () => {
		show('desktop');
		await open();
		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));
		expect(screen.queryByRole('dialog')).toBeNull();
		await waitFor(() => expect(document.activeElement).toBe(trigger()));
	});

	it('draws a scrim and locks the body scroll on mobile, and restores it on close', async () => {
		const { container } = show('mobile');
		await open();
		expect(container.querySelector('.scrim')).not.toBeNull();
		expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('true');
		expect(document.body.style.overflow).toBe('hidden');
		await fireEvent.click(container.querySelector('.scrim') as HTMLElement);
		expect(screen.queryByRole('dialog')).toBeNull();
		expect(document.body.style.overflow).toBe('');
	});

	it('closes on Esc on mobile', async () => {
		show('mobile');
		await open();
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByRole('dialog')).toBeNull();
		expect(document.body.style.overflow).toBe('');
	});

	it('closes when a navigation ends', async () => {
		show('desktop');
		await open();
		for (const callback of navigation.callbacks) callback();
		await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
	});

	it('takes its 44px target from the hit target token', () => {
		const source = readFileSync(
			join(__dirname, '..', '..', '..', 'src', 'lib', 'components', 'DateButton.svelte'),
			'utf8'
		);
		expect(source).toContain('min-height: var(--hit-target-size)');
	});
});
