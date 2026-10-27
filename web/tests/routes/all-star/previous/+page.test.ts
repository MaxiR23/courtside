// web/tests/routes/all-star/previous/+page.test.ts
//
// Tests for the previous edition route.
//
// Tested:
// - The route turns off server rendering and keeps prerender from the layout
// - All-Star is the current page in the nav
// - It renders the after view of previousEdition with the previous year and no Last time section
// - A feed with no previousEdition shows the unavailable row and requests nothing more
// - A 503 shows the unavailable row and requests nothing more
// - It loads the feed once and sends no further request, also after the tab is visible again
// - The edition frame with its caption when previousEdition carries a video, the placeholder when not; no season selector
// - The document title is the page heading then the site name, in English and Spanish; All-Star then the site name while loading and with no previousEdition; the loading title in English and Spanish
//
// What is covered:
// - The page wired end to end with the recorded before feed (its previousEdition); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run tests/routes/all-star/previous/+page.test.ts
//
// SEE: web/src/routes/all-star/previous/+page.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { AllStarFeed } from '../../../../src/lib/contract/all-star';

import { preferLanguages } from '../../../prefer-languages';

import Page from '../../../../src/routes/all-star/previous/+page.svelte';

const config = vi.hoisted(() => ({ url: undefined as string | undefined }));
vi.mock('../../../../src/lib/feed/config', () => ({
	get allStarFeedUrl() {
		return config.url;
	}
}));

const FEED_URL = 'https://feeds.example.com/all-star.json';
const withPrevious = (): AllStarFeed =>
	JSON.parse(
		readFileSync(
			join(__dirname, '..', '..', '..', 'lib', 'feed', 'fixtures', 'all-star-before.json'),
			'utf8'
		)
	);
const withoutPrevious = (): AllStarFeed => ({ ...withPrevious(), previousEdition: null });

const UNAVAILABLE = "Data isn't available right now. Check back later.";

type Answer = () => Promise<unknown>;
let answers: Answer[];
let fetchMock: ReturnType<typeof vi.fn>;
const answerWith =
	(body: unknown): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
const answerStatus =
	(status: number): Answer =>
	() =>
		Promise.resolve({ ok: false, status, json: () => Promise.resolve({}) });

function stubFetch(...next: Answer[]) {
	answers = next;
	fetchMock = vi.fn((url: string) => {
		if (url !== FEED_URL) throw new Error(`Unexpected URL ${url}`);
		const answer = answers.length > 1 ? answers.shift() : answers[0];
		return (answer as Answer)();
	});
	vi.stubGlobal('fetch', fetchMock);
}

async function settle() {
	await vi.advanceTimersByTimeAsync(0);
	await tick();
}

async function renderPage() {
	const result = render(Page);
	await settle();
	return result;
}

const ids = (container: HTMLElement) =>
	[...container.querySelectorAll('.sections > section')].map((s) => s.id);

beforeEach(() => {
	document.title = '';
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2027-01-10T12:00:00Z'));
	vi.stubGlobal(
		'matchMedia',
		vi.fn(() => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} }))
	);
	config.url = FEED_URL;
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe('Previous edition route', () => {
	it('turns off server rendering and inherits prerender from the layout', async () => {
		const options = await import('../../../../src/routes/all-star/previous/+page');
		expect(options.ssr).toBe(false);
		expect((options as { prerender?: boolean }).prerender).toBeUndefined();
	});
});

describe('Previous edition page', () => {
	it('marks All-Star as the current page', async () => {
		stubFetch(answerWith(withPrevious()));
		await renderPage();
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		const link = screen.getByRole('link', { name: 'All-Star' });
		expect(link.getAttribute('aria-current')).toBe('page');
		expect(link.getAttribute('href')).toBe('/all-star');
	});

	it('renders the after view of the previous edition with the previous year and no Last time', async () => {
		stubFetch(answerWith(withPrevious()));
		const { container } = await renderPage();
		expect(screen.getAllByText('All-Star 2026').length).toBeGreaterThan(0);
		expect(screen.getByRole('heading', { level: 1, name: 'Team Dunes' })).toBeTruthy();
		expect(screen.getByText('Champions of the day')).toBeTruthy();
		expect(ids(container)).toEqual(['mvp', 'games', 'teams']);
		expect(screen.queryByText('Last time')).toBeNull();
		expect(container.querySelectorAll('.game-card')).toHaveLength(2);
		expect(container.querySelector('.game-card[aria-pressed=true]')?.textContent).toContain(
			'Championship'
		);
	});

	it('shows the unavailable row when the feed has no previous edition and requests nothing more', async () => {
		stubFetch(answerWith(withoutPrevious()), answerWith(withPrevious()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'All-Star' })).toBeTruthy();
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
	});

	it('shows the unavailable row on a 503 and requests nothing more', async () => {
		stubFetch(answerStatus(503), answerWith(withPrevious()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
	});

	it('shows the unavailable row with no URL configured and requests nothing', async () => {
		config.url = undefined;
		stubFetch(answerWith(withPrevious()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('loads the feed once and sends no further request, also after the tab becomes visible again', async () => {
		const state = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
		stubFetch(answerWith(withPrevious()));
		await renderPage();
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		state.mockReturnValue('hidden');
		document.dispatchEvent(new Event('visibilitychange'));
		state.mockReturnValue('visible');
		document.dispatchEvent(new Event('visibilitychange'));
		await vi.advanceTimersByTimeAsync(0);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});
});

describe('Previous edition video', () => {
	const highlight = {
		title: 'Edition recap',
		channel: 'Example Channel',
		thumbnailUrl: 'https://video.example.com/thumb/edition.jpg',
		embedUrl: 'https://video.example.com/embed/edition'
	};

	it('shows the edition frame with its caption and no season selector', async () => {
		const feed = withPrevious();
		feed.previousEdition!.editionHighlight = highlight;
		stubFetch(answerWith(feed));
		await renderPage();
		expect(screen.getByText('Edition highlights')).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Play Edition recap' })).toBeTruthy();
		expect(screen.queryByRole('combobox')).toBeNull();
	});

	it('shows the placeholder and no caption without a video', async () => {
		const feed = withPrevious();
		feed.previousEdition!.editionHighlight = null;
		stubFetch(answerWith(feed));
		await renderPage();
		expect(screen.queryByText('Edition highlights')).toBeNull();
	});
});

describe('Previous edition document title', () => {
	const harbor = (): AllStarFeed => {
		const feed = withPrevious();
		const champion = feed.previousEdition!.teams.find((t) => t.placement.kind === 'champion');
		champion!.team.name = 'Team Harbor';
		return feed;
	};

	it('is the page heading then the site name, in English and Spanish', async () => {
		stubFetch(answerWith(harbor()));
		await renderPage();
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Team Harbor');
		expect(document.title).toBe('Team Harbor · Courtside');
		preferLanguages(['es']);
		stubFetch(answerWith(harbor()));
		await renderPage();
		expect(document.title).toBe('Team Harbor · Courtside');
	});

	it('is the section name while loading', async () => {
		stubFetch(() => new Promise(() => {}));
		await renderPage();
		expect(document.title).toBe('All-Star · Courtside');
	});

	it('is the section name while loading, in Spanish', async () => {
		preferLanguages(['es']);
		stubFetch(() => new Promise(() => {}));
		await renderPage();
		expect(document.title).toBe('All-Star · Courtside');
	});

	it('is the section name with no previousEdition', async () => {
		stubFetch(answerWith(withoutPrevious()));
		await renderPage();
		expect(document.title).toBe('All-Star · Courtside');
	});
});
