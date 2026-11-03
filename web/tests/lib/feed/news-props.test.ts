// web/tests/lib/feed/news-props.test.ts
//
// Tests for the props layer that turns the news feeds into card and note views.
//
// Tested:
// - toNewsCard: kind labels, team tag (first code, uppercase, null without teams), EN only for an English note in Spanish, photo kept null, the date
// - newsBlock: no source, loading, failed, empty and ready
// - homeNews takes 10 notes; recapBlock takes the note of the article feed
// - toNewsArticle: related players, teams, the game label with and without a score and with and without the game's date; null without a note
// - gameDayLabel: the game's US Eastern day from its tip-off, null before the feed
// - filterByKind and teamOptions
//
// What is covered:
// - Pure logic on invented feeds (tests/lib/feed/fixtures/news.json, news-article.json); a fixed `now`, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/news-props.test.ts
//
// SEE: web/src/lib/feed/news-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GameDetailFeed } from '../../../src/lib/contract/game-detail';
import type { NewsFeed } from '../../../src/lib/contract/news';
import type { NewsNote } from '../../../src/lib/contract/news-article';
import type { NewsArticleFeed } from '../../../src/lib/contract/news-article';
import type { SearchFeed } from '../../../src/lib/contract/search';
import {
	filterByKind,
	gameDayLabel,
	homeNews,
	newsBlock,
	recapBlock,
	teamOptions,
	toNewsArticle,
	toNewsCard
} from '../../../src/lib/feed/news-props';
import { preferLanguages } from '../../prefer-languages';

const read = (name: string) =>
	JSON.parse(readFileSync(join(import.meta.dirname, 'fixtures', name), 'utf8'));
const news = read('news.json') as NewsFeed;
const article = read('news-article.json') as NewsArticleFeed;
const search = read('search.json') as SearchFeed;

const note = (index: number): NewsNote => news.notes[index] as NewsNote;

const NOW = new Date('2026-11-03T12:00:00Z');
const ctx = { now: NOW, language: 'en' };

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toNewsCard', () => {
	it('labels the kind, in both languages', () => {
		const recap = note(0);
		const plain = note(1);
		expect(toNewsCard(recap, ctx).kindLabel).toBe('Recap');
		expect(toNewsCard(plain, ctx).kindLabel).toBe('News');
		preferLanguages(['es']);
		expect(toNewsCard(recap, { ...ctx, language: 'es' }).kindLabel).toBe('Crónica');
	});

	it('tags the first team, uppercase, or none', () => {
		expect(toNewsCard({ ...note(0), teams: ['gsw', 'min'] }, ctx).teamTag).toBe('GSW');
		expect(toNewsCard({ ...note(0), teams: [] }, ctx).teamTag).toBeNull();
	});

	it('marks an English note only when the page is in Spanish', () => {
		const english = { ...note(0), language: 'en' as const };
		expect(toNewsCard(english, { ...ctx, language: 'es' }).english).toBe(true);
		expect(toNewsCard(english, ctx).english).toBe(false);
		expect(toNewsCard({ ...english, language: 'es' }, { ...ctx, language: 'es' }).english).toBe(
			false
		);
	});

	it('keeps a missing photo null, and the date', () => {
		const card = toNewsCard({ ...note(0), photo: null }, ctx);
		expect(card.photo).toBeNull();
		expect(card.date).toBe('17 h ago');
		expect(toNewsCard(note(0), ctx).photo).toEqual({
			url: 'https://images.example.com/n1.jpg',
			width: 1280,
			height: 720
		});
	});
});

describe('newsBlock', () => {
	const toView = (feed: NewsFeed) => feed.notes.map((n) => toNewsCard(n, ctx));

	it('is null with no source', () => {
		expect(newsBlock(undefined, toView)).toBeNull();
	});

	it('is loading before the feed and while the source is not built', () => {
		expect(newsBlock({ feed: null, failed: false }, toView)).toEqual({ kind: 'loading' });
		expect(newsBlock(null, toView)).toEqual({ kind: 'loading' });
	});

	it('is null on a failure', () => {
		expect(newsBlock({ feed: null, failed: true }, toView)).toBeNull();
	});

	it('is null with no notes and ready with notes', () => {
		expect(newsBlock({ feed: { ...news, notes: [] }, failed: false }, toView)).toBeNull();
		const block = newsBlock({ feed: news, failed: false }, toView);
		expect(block?.kind).toBe('ready');
		expect(block?.kind === 'ready' && block.notes).toHaveLength(12);
	});
});

describe('homeNews and recapBlock', () => {
	it('takes the first 10 notes', () => {
		const cards = homeNews(news.notes, ctx);
		expect(cards).toHaveLength(10);
		expect(cards[0].id).toBe('note-01');
	});

	it('gives the note of the article feed, or nothing', () => {
		expect(recapBlock(article, ctx)).toHaveLength(1);
		expect(recapBlock({ note: null, game: null }, ctx)).toEqual([]);
	});
});

describe('toNewsArticle', () => {
	it('lists the related players, the teams and the game', () => {
		const view = toNewsArticle(article, ctx, null)!;
		expect(view.related.players).toEqual([
			{ id: '1001', name: 'Ana Lopez' },
			{ id: '1002', name: 'Beto Ruiz' }
		]);
		expect(view.related.teams).toEqual([
			{ code: 'gsw', label: 'GSW' },
			{ code: 'min', label: 'MIN' }
		]);
		expect(view.credit).toBe('Photo Credit');
		expect(view.fullDate).toBe('October 28, 2026, 11:30 PM');
	});

	it('shows the score alone until the game date is known', () => {
		expect(toNewsArticle(article, ctx, null)!.related.game).toEqual({
			id: '0022600001',
			label: 'GSW 119 – 114 MIN'
		});
	});

	it('adds the game date once known', () => {
		expect(toNewsArticle(article, ctx, 'Oct 28')!.related.game?.label).toBe(
			'GSW 119 – 114 MIN · Oct 28'
		);
	});

	it('draws a game with no score without it', () => {
		const unscored = { ...article, game: { ...article.game!, score: null } };
		expect(toNewsArticle(unscored, ctx, null)!.related.game?.label).toBe('GSW – MIN');
	});

	it('has no game button without a game, and no view without a note', () => {
		expect(toNewsArticle({ ...article, game: null }, ctx, 'Oct 28')!.related.game).toBeNull();
		expect(toNewsArticle({ note: null, game: null }, ctx, null)).toBeNull();
	});

	it('has no credit without a photo', () => {
		const bare = { ...article, note: { ...article.note!, photo: null } };
		expect(toNewsArticle(bare, ctx, null)!.credit).toBeNull();
	});
});

describe('gameDayLabel', () => {
	it('gives the US Eastern day of the tip-off, not the viewer day', () => {
		// 02:30 UTC on the 29th is still the 28th in New York.
		expect(gameDayLabel({ startTime: '2026-10-29T02:30:00Z' } as GameDetailFeed)).toBe('Oct 28');
		preferLanguages(['es']);
		expect(gameDayLabel({ startTime: '2026-10-29T02:30:00Z' } as GameDetailFeed)).toBe('28 oct');
	});

	it('is null before the feed is in', () => {
		expect(gameDayLabel(null)).toBeNull();
	});
});

describe('filterByKind', () => {
	const cards = news.notes.map((n) => toNewsCard(n, ctx));

	it('keeps all, or one kind', () => {
		expect(filterByKind(cards, 'all')).toHaveLength(12);
		const recaps = filterByKind(cards, 'recap');
		expect(recaps.length).toBeGreaterThan(0);
		expect(recaps.every((c) => c.kind === 'recap')).toBe(true);
		const plain = filterByKind(cards, 'news');
		expect(plain.every((c) => c.kind === 'news')).toBe(true);
		expect(recaps.length + plain.length).toBe(12);
	});
});

describe('teamOptions', () => {
	it('gives the teams of the search feed with lowercase codes, sorted by name', () => {
		const options = teamOptions(search, 'en');
		expect(options).toHaveLength(search.teams.length);
		expect(options[0].code).toBe(options[0].code.toLowerCase());
		const labels = options.map((o) => o.label);
		expect(labels).toEqual([...labels].sort((a, b) => a.localeCompare(b, 'en')));
	});
});
