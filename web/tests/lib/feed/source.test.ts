// web/tests/lib/feed/source.test.ts
//
// Unit test: feedSource builds a page's feed source from its feed URL.
//
// Tested:
// - Builds the source once with the URL it is given
// - A pending URL (null) gives null and an unconfigured one (undefined) gives undefined, without building
// - A new URL builds a new source
// - An exception thrown by build propagates
//
// What is covered:
// - Happy path, edge cases (null, undefined) and the error case
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/source.test.ts
//
// SEE: web/src/lib/feed/source.ts
import { describe, expect, it, vi } from 'vitest';
import { feedSource } from '#lib/feed/source.ts';

describe('feedSource', () => {
	it('builds the source once with the URL it is given', () => {
		const source = {};
		const build = vi.fn(() => source);
		expect(feedSource('/a', build)).toBe(source);
		expect(build).toHaveBeenCalledOnce();
		expect(build).toHaveBeenCalledWith('/a');
	});

	it('gives null without calling build while the URL is pending', () => {
		const build = vi.fn(() => ({}));
		expect(feedSource(null, build)).toBeNull();
		expect(build).not.toHaveBeenCalled();
	});

	it('gives undefined without calling build when no URL is configured', () => {
		const build = vi.fn(() => ({}));
		expect(feedSource(undefined, build)).toBeUndefined();
		expect(build).not.toHaveBeenCalled();
	});

	it('builds a new source for a new URL', () => {
		const build = vi.fn((url: string) => ({ url }));
		const a = feedSource('/a', build);
		const b = feedSource('/b', build);
		expect(a).not.toBe(b);
		expect(build).toHaveBeenNthCalledWith(2, '/b');
	});

	it('lets an exception thrown by build propagate', () => {
		expect(() =>
			feedSource('/a', () => {
				throw new Error('boom');
			})
		).toThrow('boom');
	});
});
