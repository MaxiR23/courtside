// web/tests/lib/count/count.test.ts
//
// Tests for the text of the hero count-up.
//
// Tested:
// - Every number in the text counts by the progress
// - Signs and separators are kept
// - The final text comes back at progress 1 and beyond
// - A negative progress counts as zero
// - A text without digits is left as it is
//
// What is covered:
// - Pure logic: happy path, edge cases (the bounds of the progress, no digits)
//
// Run with: cd web && pnpm exec vitest run tests/lib/count/count.test.ts
//
// SEE: web/src/lib/count/count.ts
import { describe, expect, it } from 'vitest';

import { countText } from '../../../src/lib/count/count';

describe('countText', () => {
	it('counts every number in the text by the progress', () => {
		expect(countText('16-6', 0.5)).toBe('8-3');
		expect(countText('16-6', 0)).toBe('0-0');
	});

	it('keeps signs and separators', () => {
		expect(countText('+142', 0.5)).toBe('+71');
		expect(countText('−37', 0.5)).toBe('−19');
		expect(countText('9 – 2', 0.5)).toBe('5 – 1');
	});

	it('returns the final text at progress 1 and beyond', () => {
		expect(countText('16-6', 1)).toBe('16-6');
		expect(countText('+142', 2)).toBe('+142');
	});

	it('clamps a negative progress to zero', () => {
		expect(countText('16-6', -1)).toBe('0-0');
	});

	it('leaves a text without digits as it is', () => {
		expect(countText('—', 0.5)).toBe('—');
		expect(countText('', 0.5)).toBe('');
	});
});
