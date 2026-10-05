// web/tests/lib/schedule/spoiler-free.test.ts
//
// Tests for the spoiler-free setting state.
//
// Tested:
// - Off by default and when nothing or an unknown value is stored
// - Loads a stored choice; toggling stores each choice; a new visit restores it
// - Keeps working when the storage cannot be reached, written or is missing
//
// What is covered:
// - Happy path, edge cases and the error cases of the storage
// - A fake storage, never the real one
//
// Run with: cd web && pnpm exec vitest run tests/lib/schedule/spoiler-free.test.ts
//
// SEE: web/src/lib/schedule/spoiler-free.svelte.ts
import { describe, expect, it, vi } from 'vitest';

import { SpoilerFree } from '../../../src/lib/schedule/spoiler-free.svelte';

function fakeStorage(initial?: string) {
	const data = new Map<string, string>();
	if (initial !== undefined) data.set('courtside.spoiler-free', initial);
	return {
		getItem: vi.fn((key: string) => data.get(key) ?? null),
		setItem: vi.fn((key: string, value: string) => void data.set(key, value))
	} as unknown as Storage;
}

describe('SpoilerFree', () => {
	it('is off before anything is loaded', () => {
		expect(new SpoilerFree(() => fakeStorage('on')).on).toBe(false);
	});

	it('stays off when nothing was stored', () => {
		const state = new SpoilerFree(() => fakeStorage());
		state.load();
		expect(state.on).toBe(false);
	});

	it('turns on when a stored choice of on is loaded', () => {
		const state = new SpoilerFree(() => fakeStorage('on'));
		state.load();
		expect(state.on).toBe(true);
	});

	it('stays off when the stored value is unknown', () => {
		const state = new SpoilerFree(() => fakeStorage('maybe'));
		state.load();
		expect(state.on).toBe(false);
	});

	it('toggles on and off and stores each choice', () => {
		const storage = fakeStorage();
		const state = new SpoilerFree(() => storage);
		state.toggle();
		expect(state.on).toBe(true);
		expect(storage.setItem).toHaveBeenLastCalledWith('courtside.spoiler-free', 'on');
		state.toggle();
		expect(state.on).toBe(false);
		expect(storage.setItem).toHaveBeenLastCalledWith('courtside.spoiler-free', 'off');
	});

	it('restores the choice in a new visit', () => {
		const storage = fakeStorage();
		new SpoilerFree(() => storage).toggle();
		const next = new SpoilerFree(() => storage);
		next.load();
		expect(next.on).toBe(true);
	});

	it('keeps working for the visit when the storage cannot be reached', () => {
		const state = new SpoilerFree(() => {
			throw new DOMException('denied', 'SecurityError');
		});
		expect(() => state.load()).not.toThrow();
		state.toggle();
		expect(state.on).toBe(true);
		state.toggle();
		expect(state.on).toBe(false);
	});

	it('keeps the toggled choice when the storage cannot be written', () => {
		const storage = fakeStorage();
		vi.mocked(storage.setItem).mockImplementation(() => {
			throw new DOMException('full', 'QuotaExceededError');
		});
		const state = new SpoilerFree(() => storage);
		expect(() => state.toggle()).not.toThrow();
		expect(state.on).toBe(true);
	});

	it('keeps working without any storage', () => {
		const state = new SpoilerFree(() => undefined);
		state.load();
		state.toggle();
		expect(state.on).toBe(true);
	});
});
