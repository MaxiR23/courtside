// web/tests/feed-source-follows-its-url.test.ts
//
// Cross-cutting test: the feed source of a route follows its URL, so no route builds a source
// from a closure that reads the route params (the page would keep the previous feed under the new URL).
//
// Tested:
// - The files to scan are found, and the scan cannot pass by matching nothing
// - The matcher flags single-line, multi-line, generic and DayLoader constructions that read params
//   and passes lookalikes (URL-only closures, params outside the constructor's parentheses)
// - No route builds a feed source from a closure that reads params
//
// What is covered:
// - Happy path (no route reads params in a source), edge cases (nested parentheses, generics,
//   params outside the constructor) and the error case (each form is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/feed-source-follows-its-url.test.ts
//
// SEE: web/src/lib/feed/source.ts
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const routesDir = join(import.meta.dirname, '../src/routes');
const CONSTRUCTION =
	/\bnew\s+(?:FeedPoller|FeedOnce|GamesFeedPoller|DayLoader)\s*(?:<[^>]*>)?\s*\(/g;

function sourceArguments(source: string): string[] {
	return [...source.matchAll(CONSTRUCTION)].map((match) => {
		const start = match.index + match[0].length;
		let depth = 1;
		let end = start;
		while (end < source.length && depth > 0) {
			const char = source[end];
			if (char === '(') depth++;
			else if (char === ')') depth--;
			end++;
		}
		return source.slice(start, end - 1);
	});
}

function paramsReaders(source: string): string[] {
	return sourceArguments(source).filter((args) => /\bparams\b/.test(args));
}

function sourcesUnder(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return sourcesUnder(path);
		return entry.name.endsWith('.ts') || entry.name.endsWith('.svelte') ? [path] : [];
	});
}

const files = sourcesUnder(routesDir);

describe('the scan', () => {
	it('finds the files to check', () => {
		expect(files.length).toBeGreaterThanOrEqual(15);
	});

	it('finds the feed source constructions', () => {
		const count = files.reduce(
			(sum, file) => sum + sourceArguments(readFileSync(file, 'utf8')).length,
			0
		);
		expect(count).toBeGreaterThanOrEqual(30);
	});
});

describe('the matcher', () => {
	it('flags a single-line construction that reads params', () => {
		const code =
			'new FeedPoller(() => loadGameDetailFeed(gameFeedUrl(template, params.id)), gamePollInterval)';
		expect(paramsReaders(code)).toHaveLength(1);
	});

	it('flags a multi-line construction with params on the second line', () => {
		const code = `new FeedPoller(
	() =>
		loadPlayerFeed(playerFeedUrlOf(template, params.id)),
	playerPollInterval
)`;
		expect(paramsReaders(code)).toHaveLength(1);
	});

	it('flags a generic construction', () => {
		expect(paramsReaders('new FeedOnce<X>(() => load(params.code))')).toHaveLength(1);
	});

	it('flags a DayLoader whose callback reads params', () => {
		const code = 'new DayLoader(load, w, c, () => void goto(resolve(`/?day=${params.date}`)))';
		expect(paramsReaders(code)).toHaveLength(1);
	});

	it('passes a closure that reads only a URL', () => {
		expect(paramsReaders('new FeedPoller(() => loadPlayerFeed(url), playerPollInterval)')).toEqual(
			[]
		);
		expect(
			paramsReaders(
				"new FeedOnce(() => loadCalendarFeed(calendarFeedUrlOf(calendarTemplate, 'current')))"
			)
		).toEqual([]);
	});

	it('passes params outside the constructor parentheses', () => {
		const code = "new FeedOnce(() => load(url)); resolve('/player/[id]', { id: params.id });";
		expect(paramsReaders(code)).toEqual([]);
	});
});

describe('the rule', () => {
	it('no route builds a feed source from a closure that reads params', () => {
		const offenders = files.flatMap((file) =>
			paramsReaders(readFileSync(file, 'utf8')).map(
				(args) => `${relative(routesDir, file)}: ${args.replace(/\s+/g, ' ').trim()}`
			)
		);
		expect(offenders).toEqual([]);
	});
});
