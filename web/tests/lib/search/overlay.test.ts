// web/tests/lib/search/overlay.test.ts
//
// Tests for the search overlay's open state.
//
// Tested:
// - show opens
// - close closes and focuses the registered trigger
// - The cleanup of an old trigger does not clear a newer one
//
// What is covered:
// - The reactive module without mounting; real buttons in jsdom
//
// Run with: cd web && pnpm exec vitest run tests/lib/search/overlay.test.ts
//
// SEE: web/src/lib/search/overlay.svelte.ts
import { afterEach, describe, expect, it } from 'vitest';

import { SearchOverlayState } from '../../../src/lib/search/overlay.svelte';

afterEach(() => {
	document.body.innerHTML = '';
});

const button = () => document.body.appendChild(document.createElement('button'));

describe('SearchOverlayState', () => {
	it('opens on show', () => {
		const state = new SearchOverlayState();
		expect(state.open).toBe(false);
		state.show();
		expect(state.open).toBe(true);
	});

	it('closes and focuses the registered trigger', () => {
		const state = new SearchOverlayState();
		const trigger = button();
		state.register(trigger);
		state.show();
		state.close();
		expect(state.open).toBe(false);
		expect(document.activeElement).toBe(trigger);
	});

	it('closes without a trigger', () => {
		const state = new SearchOverlayState();
		state.show();
		state.close();
		expect(state.open).toBe(false);
	});

	it('does not clear a newer trigger when an old one cleans up', () => {
		const state = new SearchOverlayState();
		const older = button();
		const newer = button();
		const cleanOlder = state.register(older);
		state.register(newer);
		cleanOlder();
		state.close();
		expect(document.activeElement).toBe(newer);
	});

	it('forgets the trigger when its own cleanup runs', () => {
		const state = new SearchOverlayState();
		const trigger = button();
		const clean = state.register(trigger);
		clean();
		state.close();
		expect(document.activeElement).not.toBe(trigger);
	});
});
