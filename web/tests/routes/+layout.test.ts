// web/tests/routes/+layout.test.ts
//
// Tests for the root layout.
//
// Tested:
// - Renders the page content
// - Loads only the font weights the design spec names
// - Opens the search overlay on "/" and on Ctrl+K and Cmd+K; "/" typed in a field does not
// - Closes it on Esc and returns the focus to the registered search trigger
// - Closes the search overlay after a navigation, and does nothing when it is closed
// - Sets the document language to es with a Spanish browser preference, en otherwise
//
// What is covered:
// - The root layout's own state: the children, the language and the search overlay
// - A config mock with no search feed URL, so no request is made
//
// Run with: cd web && pnpm exec vitest run tests/routes/+layout.test.ts
//
// SEE: web/src/routes/+layout.svelte
import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { createRawSnippet, tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { searchOverlay } from '../../src/lib/search/overlay.svelte';
import { preferLanguages } from '../prefer-languages';

import NavSearchTrigger from '../../src/lib/components/NavSearchTrigger.svelte';
import Layout from '../../src/routes/+layout.svelte';

const navigation = vi.hoisted(() => ({ callbacks: [] as Array<() => void> }));
vi.mock('$app/navigation', () => ({
	afterNavigate: (cb: () => void) => {
		navigation.callbacks.push(cb);
	}
}));

vi.mock('../../src/lib/feed/config', () => ({
	get searchFeedUrl() {
		return undefined;
	}
}));

function renderLayout() {
	return render(Layout, {
		props: {
			params: {},
			data: {},
			children: createRawSnippet(() => ({ render: () => '<p>Page content</p>' }))
		}
	});
}

afterEach(() => {
	searchOverlay.close();
	vi.restoreAllMocks();
	document.documentElement.lang = '';
});

describe('root layout', () => {
	it('renders the page content inside the layout', () => {
		renderLayout();
		expect(screen.getByText('Page content')).toBeTruthy();
	});

	it('loads only Barlow 400 and 500 and Barlow Condensed 400, 500 and 600', () => {
		renderLayout();
		const links = [
			...document.head.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')
		].filter((l) => l.href.startsWith('https://fonts.googleapis.com/'));
		expect(links).toHaveLength(1);
		expect(new URL(links[0].href).searchParams.getAll('family')).toEqual([
			'Barlow:wght@400;500',
			'Barlow Condensed:wght@400;500;600'
		]);
	});

	it('sets the document language to es with a Spanish browser preference', async () => {
		preferLanguages(['es-ES']);
		renderLayout();
		await tick();
		expect(document.documentElement.lang).toBe('es');
	});

	it('sets the document language to en otherwise', async () => {
		preferLanguages(['fr-FR']);
		renderLayout();
		await tick();
		expect(document.documentElement.lang).toBe('en');
	});

	describe('navigation', () => {
		const navigate = () => navigation.callbacks[navigation.callbacks.length - 1]();

		it('closes the overlay and restores the scroll lock after a navigation', async () => {
			document.body.style.overflow = 'auto';
			renderLayout();
			searchOverlay.show();
			await screen.findByRole('dialog');
			expect(document.body.style.overflow).toBe('hidden');
			navigate();
			await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
			expect(document.body.style.overflow).toBe('auto');
			document.body.style.overflow = '';
		});

		it('does nothing after a navigation when the overlay is closed', async () => {
			renderLayout();
			navigate();
			await tick();
			expect(searchOverlay.open).toBe(false);
			expect(screen.queryByRole('dialog')).toBeNull();
		});
	});

	describe('search shortcuts', () => {
		it('opens the dialog on "/" outside a field', async () => {
			renderLayout();
			expect(screen.queryByRole('dialog')).toBeNull();
			await fireEvent.keyDown(document.body, { key: '/' });
			expect(await screen.findByRole('dialog', { name: 'Search' })).toBeTruthy();
		});

		it('does not open on "/" typed in a field', async () => {
			render(Layout, {
				props: {
					params: {},
					data: {},
					children: createRawSnippet(() => ({ render: () => '<input aria-label="Notes" />' }))
				}
			});
			await fireEvent.keyDown(screen.getByLabelText('Notes'), { key: '/' });
			expect(screen.queryByRole('dialog')).toBeNull();
		});

		it('opens on Ctrl+K and on Cmd+K', async () => {
			renderLayout();
			await fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
			expect(await screen.findByRole('dialog')).toBeTruthy();
			searchOverlay.close();
			await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
			await fireEvent.keyDown(document.body, { key: 'k', metaKey: true });
			expect(await screen.findByRole('dialog')).toBeTruthy();
		});

		it('closes on Esc and returns the focus to the trigger', async () => {
			render(NavSearchTrigger, { props: { layout: 'desktop' } });
			renderLayout();
			const trigger = screen.getByRole('button', { name: 'Search' });
			await fireEvent.click(trigger);
			const dialog = await screen.findByRole('dialog');
			await fireEvent.keyDown(dialog, { key: 'Escape' });
			await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
			expect(document.activeElement).toBe(trigger);
		});
	});
});
