// web/tests/lib/search/keys.test.ts
//
// Tests for the search overlay's keyboard helpers.
//
// Tested:
// - "/" opens outside a text field, not in an input, a textarea or a contenteditable
// - Ctrl+K and Cmd+K open from anywhere
// - Nothing opens with Alt, while composing or when the default is prevented
// - moveActive wraps at both ends and returns -1 with no rows
//
// What is covered:
// - Pure logic; elements are built in the test
//
// Run with: cd web && pnpm exec vitest run tests/lib/search/keys.test.ts
//
// SEE: web/src/lib/search/keys.ts
import { describe, expect, it } from 'vitest';

import { moveActive, opensSearch } from '../../../src/lib/search/keys';

type Init = Partial<Parameters<typeof opensSearch>[0]>;

const press = (init: Init) =>
	opensSearch({
		key: '',
		metaKey: false,
		ctrlKey: false,
		altKey: false,
		target: document.body,
		isComposing: false,
		defaultPrevented: false,
		...init
	});

describe('opensSearch', () => {
	it('opens on "/" outside a field', () => {
		expect(press({ key: '/' })).toBe(true);
	});

	it('does not open on "/" in a text input, a textarea or a contenteditable', () => {
		expect(press({ key: '/', target: document.createElement('input') })).toBe(false);
		expect(press({ key: '/', target: document.createElement('textarea') })).toBe(false);
		const editable = document.createElement('div');
		Object.defineProperty(editable, 'isContentEditable', { value: true });
		expect(press({ key: '/', target: editable })).toBe(false);
	});

	it('opens on "/" in a checkbox', () => {
		const box = document.createElement('input');
		box.type = 'checkbox';
		expect(press({ key: '/', target: box })).toBe(true);
	});

	it('opens on Ctrl+K and Cmd+K from anywhere, even in an input', () => {
		const input = document.createElement('input');
		expect(press({ key: 'k', ctrlKey: true, target: input })).toBe(true);
		expect(press({ key: 'K', metaKey: true, target: input })).toBe(true);
	});

	it('does not open on a bare k or on "/" with a modifier', () => {
		expect(press({ key: 'k' })).toBe(false);
		expect(press({ key: '/', ctrlKey: true })).toBe(false);
	});

	it('does not open with Alt, while composing or when already handled', () => {
		expect(press({ key: 'k', ctrlKey: true, altKey: true })).toBe(false);
		expect(press({ key: '/', altKey: true })).toBe(false);
		expect(press({ key: '/', isComposing: true })).toBe(false);
		expect(press({ key: '/', defaultPrevented: true })).toBe(false);
	});
});

describe('moveActive', () => {
	it('moves down and up', () => {
		expect(moveActive(0, 1, 3)).toBe(1);
		expect(moveActive(2, -1, 3)).toBe(1);
	});

	it('wraps down from the last row and up from the first', () => {
		expect(moveActive(2, 1, 3)).toBe(0);
		expect(moveActive(0, -1, 3)).toBe(2);
	});

	it('returns -1 with no rows', () => {
		expect(moveActive(0, 1, 0)).toBe(-1);
		expect(moveActive(-1, -1, 0)).toBe(-1);
	});
});
