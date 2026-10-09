// web/tests/lib/search/dialog.test.ts
//
// Tests for the search dialog's scroll lock and focus trap.
//
// Tested:
// - The scroll lock sets overflow hidden and restores the previous inline value
// - Tab from the last focusable element goes to the first; Shift+Tab from the first to the last
// - Tab in the middle is left alone
//
// What is covered:
// - DOM behavior in jsdom; no layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/search/dialog.test.ts
//
// SEE: web/src/lib/search/dialog.ts
import { afterEach, describe, expect, it } from 'vitest';

import { keepFocusInside, lockBodyScroll } from '../../../src/lib/search/dialog';

afterEach(() => {
	document.body.innerHTML = '';
	document.body.style.overflow = '';
});

describe('lockBodyScroll', () => {
	it('hides overflow and restores the previous inline value', () => {
		document.body.style.overflow = 'scroll';
		const release = lockBodyScroll(document.body);
		expect(document.body.style.overflow).toBe('hidden');
		release();
		expect(document.body.style.overflow).toBe('scroll');
	});

	it('restores an empty value', () => {
		const release = lockBodyScroll(document.body);
		release();
		expect(document.body.style.overflow).toBe('');
	});
});

describe('keepFocusInside', () => {
	function setup() {
		document.body.innerHTML = `<div id="box">
			<input id="a" /><button id="b">b</button><button id="skip" tabindex="-1">x</button>
			<button id="off" disabled>o</button><a id="c" href="/x">c</a></div>`;
		const el = (id: string) => document.getElementById(id) as HTMLElement;
		return { box: el('box'), a: el('a'), b: el('b'), c: el('c') };
	}
	const tab = (shiftKey = false) =>
		new KeyboardEvent('keydown', { key: 'Tab', shiftKey, cancelable: true });

	it('wraps Tab from the last focusable element to the first', () => {
		const { box, a, c } = setup();
		c.focus();
		const event = tab();
		keepFocusInside(event, box);
		expect(event.defaultPrevented).toBe(true);
		expect(document.activeElement).toBe(a);
	});

	it('wraps Shift+Tab from the first focusable element to the last', () => {
		const { box, a, c } = setup();
		a.focus();
		const event = tab(true);
		keepFocusInside(event, box);
		expect(event.defaultPrevented).toBe(true);
		expect(document.activeElement).toBe(c);
	});

	it('leaves Tab in the middle alone', () => {
		const { box, b } = setup();
		b.focus();
		const event = tab();
		keepFocusInside(event, box);
		expect(event.defaultPrevented).toBe(false);
		expect(document.activeElement).toBe(b);
	});

	it('ignores other keys', () => {
		const { box, c } = setup();
		c.focus();
		const event = new KeyboardEvent('keydown', { key: 'a', cancelable: true });
		keepFocusInside(event, box);
		expect(event.defaultPrevented).toBe(false);
	});
});
