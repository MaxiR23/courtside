// web/tests/lib/hero/slideshow.test.ts
//
// Tests for the hero slideshow state.
//
// Tested:
// - Advancing, wrapping, jumping to a slide and stopping
// - Timers never stack and a restart resets the wait
// - Invalid counts and indexes throw a RangeError
// - The JS interval matches the --hero-slide-interval token
//
// What is covered:
// - Happy path, edge cases and error case
// - Fake timers, no real clock
//
// Run with: cd web && pnpm exec vitest run tests/lib/hero/slideshow.test.ts
//
// SEE: web/src/lib/hero/slideshow.svelte.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { SLIDE_INTERVAL_MS, Slideshow } from '../../../src/lib/hero/slideshow.svelte';

beforeEach(() => {
	vi.useFakeTimers();
});

afterEach(() => {
	vi.useRealTimers();
});

describe('Slideshow', () => {
	it('starts on the first slide', () => {
		expect(new Slideshow(2).current).toBe(0);
	});

	it('advances to the next slide after 7 seconds', () => {
		const show = new Slideshow(2);
		show.start();
		vi.advanceTimersByTime(7000);
		expect(show.current).toBe(1);
	});

	it('wraps back to the first slide after the last', () => {
		const show = new Slideshow(2);
		show.start();
		vi.advanceTimersByTime(14000);
		expect(show.current).toBe(0);
	});

	it('does not advance before the interval ends', () => {
		const show = new Slideshow(2);
		show.start();
		vi.advanceTimersByTime(6999);
		expect(show.current).toBe(0);
	});

	it('jumps to a slide and restarts the 7 second wait', () => {
		const show = new Slideshow(3);
		show.start();
		vi.advanceTimersByTime(5000);
		show.goTo(2);
		expect(show.current).toBe(2);
		vi.advanceTimersByTime(6999);
		expect(show.current).toBe(2);
		vi.advanceTimersByTime(1);
		expect(show.current).toBe(0);
	});

	it('counts a new cycle on every slide change', () => {
		const show = new Slideshow(2);
		show.start();
		const before = show.cycle;
		vi.advanceTimersByTime(7000);
		expect(show.cycle).toBe(before + 1);
		show.goTo(0);
		expect(show.cycle).toBe(before + 2);
	});

	it('stops advancing once stopped', () => {
		const show = new Slideshow(2);
		const stop = show.start();
		stop();
		vi.advanceTimersByTime(30000);
		expect(show.current).toBe(0);
	});

	it('does not stack timers when started twice', () => {
		const show = new Slideshow(3);
		show.start();
		show.start();
		vi.advanceTimersByTime(7000);
		expect(show.current).toBe(1);
	});

	it('throws a RangeError for a slide out of range', () => {
		const show = new Slideshow(2);
		expect(() => show.goTo(2)).toThrow(RangeError);
		expect(() => show.goTo(-1)).toThrow(RangeError);
		expect(() => show.goTo(0.5)).toThrow(RangeError);
	});

	it('throws a RangeError for a count below one', () => {
		expect(() => new Slideshow(0)).toThrow(RangeError);
		expect(() => new Slideshow(1.5)).toThrow(RangeError);
	});

	it('exports a 7 second interval matching the --hero-slide-interval token', () => {
		const css = readFileSync(
			join(import.meta.dirname, '../../../src/lib/styles/tokens.css'),
			'utf8'
		);
		const match = css.match(/--hero-slide-interval:\s*([\d.]+)s;/);
		expect(Number(match?.[1])).toBe(SLIDE_INTERVAL_MS / 1000);
	});
});
