// web/tests/lib/feed/playoffs-props.test.ts
//
// Tests for the props layer that turns the playoffs feeds into the playoffs page props.
//
// Tested:
// - The section order of each state, and the sections a missing block hides
// - The finals sections hidden with no finals feed; the conference MVPs alone with no Finals MVP
// - The state line of each state, the stage strip (TBD, ranges, one date, statuses)
// - The picture tables: seeds in feed order, the line markers, clinch tags, — in the preseason
// - The play-in: To be decided slots, places, the 8th seed labels, outcomes, links, the collapsed flag
// - The champion hero: tag, result line, four stats, — for a missing record
// - The finals series: tabs, OT, the champion's wins, video, no chart for a missing or bad curve, the deficit marker
// - The road to the title, the head to head bars, the postseason averages
// - The leaders tabs and the awards cards, the All-NBA team names
// - The bracket: 15 series and 16 round 1 slots in every state, slot labels, Currently and To be decided notes,
//   the loser, rows from the top team's point of view, OT, scheduled games, missing values, the Champion flag
// - Spanish copy
//
// What is covered:
// - Pure logic on invented feeds (tests/lib/feed/fixtures/playoffs-*.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/playoffs-props.test.ts
//
// SEE: web/src/lib/feed/playoffs-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed, PlayoffsState } from '../../../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../../../src/lib/contract/playoffs-finals';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import type { PlayoffsView } from '../../../src/lib/playoffs/types';
import { preferLanguages } from '../../prefer-languages';

const read = <T>(name: string): T =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', name), 'utf8')) as T;

const picture = () => read<PlayoffsFeed>('playoffs-picture.json');
const playin = () => read<PlayoffsFeed>('playoffs-playin.json');
const complete = () => read<PlayoffsFeed>('playoffs-complete.json');
const bracket = () => read<PlayoffsFeed>('playoffs-bracket.json');
const finalsFeed = () => read<PlayoffsFinalsFeed>('playoffs-finals.json');

const view = (feed: PlayoffsFeed, finals: PlayoffsFinalsFeed | null = null): PlayoffsView =>
	toPlayoffsView(feed, finals);

// A state derived from the complete fixture, with the fields the state sets.
const inState = (
	state: PlayoffsState,
	change: (f: PlayoffsFeed) => void = () => {}
): PlayoffsFeed => {
	const f = complete();
	f.state = state;
	if (state !== 'complete') f.champion = null;
	change(f);
	return f;
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toPlayoffsView sections', () => {
	it('orders the sections of the picture state: picture, bracket, play-in, leaders, awards', () => {
		expect(view(picture()).sections).toEqual([
			'picture',
			'bracket',
			'play-in',
			'leaders',
			'awards'
		]);
	});

	it('orders the sections of the play-in and playoffs states with the bracket first', () => {
		const expected = ['bracket', 'play-in', 'leaders', 'awards'];
		expect(view(playin()).sections).toEqual(expected);
		expect(view(inState('playoffs', (f) => (f.currentRound = 1))).sections).toEqual(expected);
	});

	it('orders the sections of the finals state with the hype blocks before the leaders', () => {
		const f = inState('finals');
		expect(view(f, finalsFeed()).sections).toEqual([
			'bracket',
			'play-in',
			'finals-mvp',
			'series',
			'road',
			'head-to-head',
			'leaders',
			'awards'
		]);
	});

	it('orders the sections of the complete state as the design sets', () => {
		expect(view(complete(), finalsFeed()).sections).toEqual([
			'finals-mvp',
			'series',
			'road',
			'head-to-head',
			'leaders',
			'bracket',
			'play-in',
			'awards'
		]);
	});

	it('hides the leaders when the feed has none and the awards when the feed has none', () => {
		const f = picture();
		f.leaders = null;
		expect(view(f).sections).toEqual(['picture', 'bracket', 'play-in', 'awards']);
		f.awards = null;
		expect(view(f).sections).toEqual(['picture', 'bracket', 'play-in']);
		expect(view(f).leaders).toEqual([]);
		expect(view(f).awards).toEqual([]);
	});

	it('hides the finals sections when the finals feed is unavailable and keeps the rest', () => {
		const v = view(complete(), null);
		expect(v.sections).toEqual(['leaders', 'bracket', 'play-in', 'awards']);
		expect(v.series).toEqual([]);
		expect(v.road).toEqual([]);
		expect(v.headToHead).toBeNull();
		expect(v.finalsMvp).toBeNull();
	});

	it('hides the series section when the finals feed lists no game', () => {
		const finals = finalsFeed();
		finals.games = [];
		expect(view(complete(), finals).sections).not.toContain('series');
		expect(view(complete(), finals).sections).toContain('road');
	});

	it('shows the conference finals MVPs alone when the finals feed has no Finals MVP', () => {
		const finals = finalsFeed();
		finals.finalsMvp = null;
		const v = view(complete(), finals);
		expect(v.finalsMvp).toBeNull();
		expect(v.sections).toContain('finals-mvp');
		expect(v.conferenceMvps.map((mvp) => [mvp.key, mvp.name, mvp.label, mvp.team])).toEqual([
			['east', 'Kai Lowe', 'East finals MVP', 'QXA'],
			['west', 'Moe Nash', 'West finals MVP', 'QYA']
		]);
	});

	it('hides the Finals MVP section with no Finals MVP and no conference finals MVP', () => {
		const finals = finalsFeed();
		finals.finalsMvp = null;
		const f = complete();
		f.awards = f.awards!.filter((a) => !a.code.endsWith('finals_mvp'));
		const v = view(f, finals);
		expect(v.sections).not.toContain('finals-mvp');
		expect(v.conferenceMvps).toEqual([]);
	});
});

describe('toPlayoffsView header', () => {
	it('writes the state line of each state, with the Finals game and summary when sent', () => {
		expect(view(picture()).header.stateLine).toBe('Playoff picture');
		expect(view(playin()).header.stateLine).toBe('Play-In');
		const round = (n: number | null) =>
			view(inState('playoffs', (f) => (f.currentRound = n))).header.stateLine;
		expect(round(1)).toBe('First round');
		expect(round(2)).toBe('Conference semifinals');
		expect(round(3)).toBe('Conference finals');
		expect(round(null)).toBe('Playoffs');
		expect(view(inState('finals')).header.stateLine).toBe('NBA Finals · Game 5 · QXA win 4-1');
		const before = inState('finals', (f) => {
			f.finalsGame = null;
			f.finalsSummary = null;
		});
		expect(view(before).header.stateLine).toBe('NBA Finals');
		expect(view(complete()).header.stateLine).toBe('Complete');
		expect(view(picture()).header.season).toBe('2026-27');
	});

	it('writes the stage strip with TBD dates and Next for the play-in in the picture state', () => {
		const stages = view(picture()).header.stages;
		expect(stages.map((s) => [s.label, s.dates, s.statusLabel])).toEqual([
			['Play-In', 'TBD', 'Next'],
			['Round 1', 'TBD', 'Upcoming'],
			['Conf. semis', 'TBD', 'Upcoming'],
			['Conf. finals', 'TBD', 'Upcoming'],
			['Finals', 'TBD', 'Upcoming']
		]);
		expect(stages.map((s) => s.key)).toEqual(['playin', 'round_1', 'round_2', 'round_3', 'finals']);
	});

	it('writes stage dates as a range, or one date when the stage has one day', () => {
		const f = complete();
		f.stages[0].lastDate = f.stages[0].firstDate;
		const stages = view(f).header.stages;
		expect(stages[0].dates).toBe('Apr 14');
		expect(stages[1].dates).toBe('Apr 18 – May 3');
		expect(stages[4].statusLabel).toBe('Complete');
	});

	it('builds the champion hero with the tag, the result line, the four stats and — for a missing record', () => {
		const hero = view(complete()).header.hero!;
		expect(hero.tag).toBe('2027 NBA Finals');
		expect(hero.result).toBe('Owls win series 4–1 · Jun 4 – Jun 19');
		expect(hero.title).toBe('Champions');
		expect(hero.plateLabel).toBe('2027 champions');
		expect(hero.team.code).toBe('QXA');
		expect(hero.city).toBe('Harbor');
		expect(hero.strip).toEqual({ primary: '#1d4e89', secondary: '#f2c14e' });
		expect(hero.stats.map((s) => [s.key, s.label, s.value, s.accent])).toEqual([
			['record', 'Postseason record', '16-6', false],
			['home', 'Home', '9-2', false],
			['road', 'Road', '7-4', false],
			['diff', 'Point differential', '+142', true]
		]);
		const f = complete();
		f.champion!.record = null;
		f.champion!.home = null;
		f.champion!.road = null;
		f.champion!.team.colors.secondary = null;
		const missing = view(f).header.hero!;
		expect(missing.stats.map((s) => s.value)).toEqual(['—', '—', '—', '+142']);
		expect(missing.strip).toBeNull();
	});

	it('has no hero before the postseason is complete', () => {
		expect(view(picture()).header.hero).toBeNull();
	});
});

describe('toPlayoffsView picture', () => {
	it('keeps seeds 1 to 10 in feed order with the playoff and play-in line markers', () => {
		const tables = view(picture()).picture;
		expect(tables.map((t) => t.title)).toEqual(['East', 'West']);
		const east = tables[0].rows;
		expect(east.map((r) => r.seed)).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']);
		expect(east.map((r) => r.line)).toEqual([
			null,
			null,
			null,
			null,
			null,
			'playoffs',
			null,
			null,
			null,
			'playin'
		]);
		expect(east[0]).toMatchObject({ record: '56-26', gamesBehind: '—' });
		expect(east[1].gamesBehind).toBe('2.0');
		expect(east.map((r) => r.clinch?.code ?? null).slice(0, 3)).toEqual(['z', 'y', 'x']);
		expect(east[0].strip).toEqual({ primary: '#1d4e89', secondary: '#f2c14e' });
	});

	it('writes — in every value and no clinch tag in the preseason', () => {
		const f = picture();
		for (const table of f.picture) {
			for (const row of table.rows) {
				row.seed = null;
				row.wins = null;
				row.losses = null;
				row.gamesBehind = null;
				row.clinch = null;
			}
		}
		const row = view(f).picture[0].rows[2];
		expect(row).toMatchObject({ seed: '—', record: '—', gamesBehind: '—', clinch: null });
		expect(view(f).picture[0].rows[5].line).toBe('playoffs');
	});
});

describe('toPlayoffsView play-in', () => {
	it('labels undecided play-in slots To be decided with the regular season place', () => {
		const east = view(picture()).playIn[0];
		expect(east.title).toBe('East · Play-In');
		const first = east.games[0];
		expect(first.title).toBe('7th vs 8th');
		expect(first.top).toMatchObject({
			team: null,
			label: 'To be decided',
			place: '7th',
			currently: 'Currently QXG'
		});
		expect(first.bottom.place).toBe('8th');
		expect(first.when).toBeNull();
		expect(first.linked).toBe(false);
		const west = view(playin()).playIn[1].games[1];
		expect(west.top).toMatchObject({ place: '9th', currently: null });
	});

	it('labels the 8th seed game slots Loser of 7th vs 8th and Winner of 9th vs 10th', () => {
		const game = view(picture()).playIn[0].games[2];
		expect(game.title).toBe('8th seed game');
		expect(game.top.place).toBe('Loser of 7th vs 8th');
		expect(game.bottom.place).toBe('Winner of 9th vs 10th');
	});

	it('writes the play-in outcomes QXG → No. 7 and QXJ out once a game is final', () => {
		const east = view(playin()).playIn[0];
		expect(east.games[0].outcomes).toEqual(['QXG → No. 7']);
		expect(east.games[0].top).toMatchObject({ label: 'Falcons', place: null });
		expect(east.games[0].score).toEqual({ top: '108', bottom: '101' });
		expect(east.games[0].when).toBeNull();
		expect(east.games[1].outcomes).toEqual(['QXI out']);
		expect(east.games[1].score).toEqual({ top: '97', bottom: '99' });
		const done = view(complete()).playIn[0].games[2];
		expect(done.outcomes).toEqual(['QXH → No. 8', 'QXJ out']);
	});

	it('shows the date and the tip time of a game that is not final', () => {
		const game = view(playin()).playIn[0].games[2];
		expect(game.when).toMatch(/^Apr 17 · \d{1,2}:\d{2} [AP]M/);
		expect(game.score).toBeNull();
		expect(game.top.label).toBe('Bison');
	});

	it('links a play-in game only when its detail is available', () => {
		const f = playin();
		f.playIn![0].games[1].game!.detailAvailable = true;
		const games = view(f).playIn[0].games;
		expect(games.map((g) => g.linked)).toEqual([false, true, false]);
		expect(games[1].gameId).toBe('g2');
	});

	it('has no play-in section and no play-in view when the feed has none', () => {
		const f = complete();
		f.playIn = null;
		const v = view(f);
		expect(v.sections).not.toContain('play-in');
		expect(v.playIn).toEqual([]);
		expect(view(complete()).sections).toContain('play-in');
	});

	it('collapses the play-in after round 1 starts', () => {
		expect(view(picture()).playInCollapsed).toBe(false);
		expect(view(playin()).playInCollapsed).toBe(false);
		for (const state of ['playoffs', 'finals', 'complete'] as const) {
			expect(view(inState(state)).playInCollapsed).toBe(true);
		}
	});
});

describe('toPlayoffsView finals series', () => {
	it('writes one game tab per game the finals feed lists, with OT and the champion wins in accent', () => {
		const series = view(complete(), finalsFeed()).series;
		expect(series.map((g) => [g.tab, g.winner, g.score, g.overtime, g.championWon])).toEqual([
			['G1', 'QXA', '112–104', false, true],
			['G2', 'QXA', '107–98', false, true],
			['G3', 'QXA', '110–101', false, true],
			['G4', 'QYA', '102–99', true, false],
			['G5', 'QXA', '106–94', false, true]
		]);
		expect(series[0].scoreLine).toBe('QYA 104 – 112 QXA');
	});

	it('gives a game the highlight video when the feed has one and none otherwise', () => {
		const series = view(complete(), finalsFeed()).series;
		expect(series[2].video).toMatchObject({
			title: 'Example highlights G3',
			channel: 'Example Channel',
			thumbnail: 'https://video.example.com/t/3.jpg'
		});
		expect(series[0].video).toBeNull();
		const finals = finalsFeed();
		finals.games[0]!.highlights = [];
		expect(view(complete(), finals).series[0].video).toBeNull();
	});

	it('writes the game leaders with their names and links only when the game exists', () => {
		const series = view(complete(), finalsFeed()).series;
		expect(series[0].leaders?.away).toMatchObject({
			firstName: 'Aaron',
			lastName: 'Away1',
			points: 25
		});
		expect(series[4].leaders).toBeNull();
		expect(series[0].linked).toBe(true);
		expect(series[0].gameId).toBe('g101');
	});

	it('draws no chart when the win probability is missing', () => {
		const series = view(complete(), finalsFeed()).series;
		expect(series[1].chart).toBeNull();
		expect(series[0].chart).not.toBeNull();
	});

	it('draws no chart for a malformed curve', () => {
		const finals = finalsFeed();
		finals.games[0]!.winProbability!.points[1]!.winProbability = 2;
		expect(view(complete(), finals).series[0].chart).toBeNull();
		const early = finalsFeed();
		early.games[0]!.winProbability!.periods.endElapsedSeconds = 100;
		expect(view(complete(), early).series[0].chart).toBeNull();
	});

	it('places the largest deficit marker at its second of the game', () => {
		const series = view(complete(), finalsFeed()).series;
		expect(series[0].chart?.deficit).toEqual({ label: 'Largest deficit: 12', left: 900 / 2880 });
		expect(series[3].chart?.deficit).toBeNull();
		expect(series[0].chart?.boundaries?.periods).toHaveLength(4);
	});

	it('writes the Finals MVP card with — per missing value and the best game in accent', () => {
		const mvp = view(complete(), finalsFeed()).finalsMvp!;
		expect(mvp.name).toBe('Kai Lowe');
		expect(mvp.stats.map((s) => [s.key, s.value, s.accent])).toEqual([
			['ppg', '27.5', false],
			['best', '41', true],
			['rebast', '8.2 · 6.8', false],
			['games', '5', false]
		]);
		const finals = finalsFeed();
		finals.finalsMvp!.bestGame = null;
		finals.finalsMvp!.points = null;
		const missing = view(complete(), finals).finalsMvp!;
		expect(missing.stats.map((s) => s.value)).toEqual(['—', '—', '8.2 · 6.8', '5']);
	});
});

describe('toPlayoffsView road and head to head', () => {
	it('writes the road to the title with seeds, records and W or L results, losses muted', () => {
		const road = view(complete(), finalsFeed()).road;
		expect(road[0].name).toBe('Harbor Owls');
		expect(road[0].seedLine).toBe('#1 seed · 64-18');
		expect(road[0].postseason).toBe('16-6');
		expect(road[0].series.map((s) => [s.round, s.opponentSeed, s.result, s.loss])).toEqual([
			['Round 1', '#8', '4–0 W', false],
			['Conference semifinals', '#4', '4–2 W', false],
			['Conference finals', '#2', '4–3 W', false],
			['NBA Finals', '#2', '4–1 W', false]
		]);
		expect(road[1].postseason).toBe('—');
	});

	it('marks a lost series as a loss', () => {
		const finals = finalsFeed();
		finals.road[1].series[0]!.result = 'loss';
		const row = view(complete(), finals).road[1].series[0];
		expect(row.loss).toBe(true);
		expect(row.result.endsWith(' L')).toBe(true);
	});

	it('shows the rows a finalist road has when a series is missing', () => {
		const road = view(complete(), finalsFeed()).road;
		expect(road[0].series).toHaveLength(4);
		expect(road[1].series).toHaveLength(3);
	});

	it('writes — for a series without a result and a seedLine without seed or record', () => {
		const finals = finalsFeed();
		finals.road[0].series[0]!.wins = null;
		finals.road[0].series[0]!.result = null;
		finals.road[0].series[0]!.opponentSeed = null;
		finals.road[0].seed = null;
		finals.road[0].regularSeason = null;
		const road = view(complete(), finals).road[0];
		expect(road.series[0]).toMatchObject({ result: '—', opponentSeed: '—', loss: false });
		expect(road.seedLine).toBe('—');
	});

	it('writes the eight bars in feed order with the better side colored and — for a missing value', () => {
		const h2h = view(complete(), finalsFeed()).headToHead!;
		expect(h2h.records).toEqual([
			{ team: 'QXA', record: '16-6' },
			{ team: 'QYA', record: '—' }
		]);
		expect(h2h.bars.map((b) => b.label)).toEqual([
			'Points per game',
			'FG%',
			'eFG%',
			'Assists',
			'Rebounds',
			'Blocks',
			'Steals',
			'Technical fouls'
		]);
		expect(h2h.bars[0].sides).toEqual([
			{ value: '112.4', share: 1, better: true, color: '#1d4e89' },
			{ value: '104.1', share: 104.1 / 112.4, better: false, color: '#2e4057' }
		]);
		expect(h2h.bars[1].sides.map((s) => s.value)).toEqual(['48.1%', '45.2%']);
		const missing = h2h.bars[3];
		expect(missing.sides[1]).toMatchObject({ value: '—', share: 0, better: false });
		expect(missing.sides[0].better).toBe(false);
		expect(h2h.bars[5].sides[1]).toMatchObject({ value: '0.0', share: 0 });
	});

	it('marks the lower side better for technical fouls as the feed sends it', () => {
		const tech = view(complete(), finalsFeed()).headToHead!.bars[7];
		expect(tech.sides.map((s) => [s.value, s.better])).toEqual([
			['2', true],
			['5', false]
		]);
		expect(tech.sides[1].share).toBe(1);
	});

	it('falls back to no color for a team without a primary color', () => {
		const finals = finalsFeed();
		finals.road[0].team.colors.primary = null;
		expect(view(complete(), finals).headToHead!.bars[0].sides[0].color).toBeNull();
	});

	it('writes the postseason averages per finalist with — for a player without stats, last', () => {
		const averages = view(complete(), finalsFeed()).headToHead!.averages;
		expect(averages.map((a) => a.key)).toEqual(['QXA', 'QYA']);
		expect(averages[0].rows[0]).toMatchObject({
			name: 'Kai Lowe',
			points: '27.5',
			rebounds: '8.2',
			assists: '6.8',
			blocks: '1.2',
			fieldGoalPct: '51.2%'
		});
		const last = averages[0].rows[2];
		expect(last).toMatchObject({
			name: 'Ned Oakes',
			points: '—',
			rebounds: '—',
			assists: '—',
			blocks: '—',
			fieldGoalPct: '—'
		});
		expect(averages[0].rows[1].photo).toBeNull();
	});
});

describe('toPlayoffsView leaders and awards', () => {
	it('builds nine leader tabs with the first leader and the ranks the feed has', () => {
		const tabs = view(picture()).leaders;
		expect(tabs.map((t) => t.label)).toEqual([
			'Points',
			'Rebounds',
			'Assists',
			'Steals',
			'Blocks',
			'Field goal %',
			'3-pointers made',
			'Double-doubles',
			'Minutes'
		]);
		expect(tabs[0].first).toMatchObject({
			rank: '1',
			name: 'Leader points 1',
			team: 'QXA',
			value: '30.0'
		});
		expect(tabs[0].rest.map((r) => r.rank)).toEqual(['2', '3']);
		expect(tabs[1].rest).toHaveLength(4);
		expect(tabs[2].first).toBeNull();
		expect(tabs[2].rest).toEqual([]);
	});

	it('keeps a rank gap as the feed sends it', () => {
		const f = picture();
		f.leaders![0].leaders[1]!.rank = 3;
		expect(view(f).leaders[0].rest.map((r) => r.rank)).toEqual(['3', '3']);
	});

	it('writes an award card per award with its short code and team awards as lists', () => {
		const awards = view(complete()).awards;
		expect(awards.map((a) => [a.name, a.code, a.kind])).toEqual([
			['Most Valuable Player', 'MVP', 'player'],
			['Finals MVP', 'FMVP', 'player'],
			['East finals MVP', 'ECF MVP', 'player'],
			['West finals MVP', 'WCF MVP', 'player'],
			['Twyman-Stokes Teammate Award', null, 'player'],
			['All-NBA 1st Team', null, 'team']
		]);
		const team = awards[5];
		expect(team.winners).toHaveLength(5);
		expect(team.winners[1]).toMatchObject({ name: 'Eli Fox', team: 'QYA' });
		expect(awards[0].winners).toEqual([{ id: 'a1', name: 'Ada Byrne', photo: null, team: 'QXA' }]);
	});

	it('shows only the first winner of a player award', () => {
		const f = picture();
		f.awards![0].winners = [
			{ playerId: 'x1', name: 'One', photoUrl: null, teamCode: 'QXA' },
			{ playerId: 'x2', name: 'Two', photoUrl: null, teamCode: null }
		];
		expect(view(f).awards[0].winners.map((w) => w.name)).toEqual(['One']);
	});

	it('names the All-NBA team by its number', () => {
		const f = picture();
		const base = f.awards![1];
		f.awards = [2, 3].map((team) => ({ ...base, team }));
		f.awards.push(
			{ ...base, code: 'all_rookie', team: 2 },
			{ ...base, code: 'all_defensive', team: 1 }
		);
		f.awards.push({ ...base, code: 'cup_all_tournament', team: null });
		expect(view(f).awards.map((a) => a.name)).toEqual([
			'All-NBA 2nd Team',
			'All-NBA 3rd Team',
			'All-Rookie 2nd Team',
			'All-Defensive 1st Team',
			'NBA Cup All-Tournament Team'
		]);
		f.awards = [{ ...base, team: null }];
		expect(view(f).awards[0].name).toBe('—');
	});
});

describe('toPlayoffsView bracket', () => {
	const card = (id: string, feed = bracket()) =>
		view(feed).bracket.series.find((series) => series.id === id)!;

	it('has 15 series, 30 sides and 16 round 1 slots in every state', () => {
		for (const feed of [picture(), playin(), bracket(), complete()]) {
			const series = view(feed).bracket.series;
			expect(series).toHaveLength(15);
			expect(series.flatMap((entry) => [entry.top, entry.bottom])).toHaveLength(30);
			expect(series.filter((entry) => entry.id.includes('-r1-'))).toHaveLength(8);
		}
	});

	it('labels the slots of each key', () => {
		expect(card('west-r1-1').bottom.label).toBe('West play-in winner');
		expect(card('east-r2-1').bottom.label).toBe('Winner of East R1 2');
		expect(card('east-r3').top.label).toBe('Winner of East semifinal 1');
		expect(card('finals').top.label).toBe('Winner of East finals');
		expect(card('west-r3').bottom.label).toBe('Winner of West semifinal 2');
		expect(card('east-r2-2').top.label).toBe('Winner of East R1 3');
		expect(view(playin()).bracket.series[0].top.label).toBe('East #1 seed');
	});

	it('writes a missing part of a slot label as a dash', () => {
		const feed = bracket();
		feed.bracket[11].top.label.seed = null;
		expect(card('west-r1-1', feed).top.team).not.toBeNull();
		feed.bracket[11].top.team = null;
		expect(card('west-r1-1', feed).top.label).toBe('West #— seed');
	});

	it('names an undecided side Currently a team when the feed says so, else To be decided', () => {
		const feed = playin();
		feed.bracket[0].top.currently = feed.playIn![0].games[0].top.team;
		const v = view(feed).bracket.series[0];
		expect(v.top.note).toBe('Currently QXG');
		expect(v.bottom.note).toBe('To be decided');
		expect(card('east-r2-1').top.note).toBeNull();
	});

	it('marks the loser of a complete series only', () => {
		const series = card('east-r1-1');
		expect(series.top.loser).toBe(false);
		expect(series.bottom.loser).toBe(true);
		expect(card('east-r1-2').bottom.loser).toBe(false);
		expect(card('east-r2-2').bottom.loser).toBe(false);
	});

	it('lists the games played and the next one, none for the games not scheduled', () => {
		const series = card('east-r1-2');
		expect(series.games).toHaveLength(5);
		expect(series.score).toBe('Series tied 2-2');
		expect(series.games.at(-1)?.final).toBe(false);
		expect(card('east-r1-4').games).toEqual([]);
	});

	it('writes the wins, and a dash for a missing seed or wins', () => {
		expect(card('east-r1-3').top.wins).toBe('0');
		expect(card('east-r1-3').top.seed).toBe('3');
		expect(card('east-r1-4').top.wins).toBe('—');
		expect(card('east-r1-4').bottom.seed).toBe('—');
		expect(card('east-r2-2').top.seed).toBe('');
		expect(card('east-r2-2').top.wins).toBe('');
	});

	it('scores a series by its summary, else by the wins, else with a dash', () => {
		expect(card('east-r1-1').score).toBe('QXA win 4-1');
		expect(card('east-r1-3').score).toBe('0–0');
		expect(card('east-r1-4').score).toBe('—');
	});

	it('flags the overtime game', () => {
		const games = card('east-r1-1').games;
		expect(games[2].overtime).toBe(true);
		expect(games[0].overtime).toBe(false);
	});

	it('reads each row from the top team, vs at home and at away', () => {
		const games = card('east-r1-1').games;
		expect(games[0].label).toBe('G1 · vs QXH');
		expect(games[2].label).toBe('G3 · at QXH');
		expect(games[4].label).toBe('G5 · vs QXH');
	});

	it('mutes the losing side of a final game and writes its scores', () => {
		const game = card('east-r1-1').games[0];
		expect(game.away).toEqual({ code: 'QXH', score: '98', loser: true });
		expect(game.home).toEqual({ code: 'QXA', score: '105', loser: false });
		expect(game.when).toBeNull();
	});

	it('gives a scheduled game its date and venue, and no loser', () => {
		const game = card('east-r1-2').games[4];
		expect(game.final).toBe(false);
		expect(game.when).toBe('Apr 28 · Example Arena');
		expect(game.away.score).toBe('—');
		expect(game.away.loser).toBe(false);
		expect(game.home.loser).toBe(false);
	});

	it('writes a final game with no score as dashes', () => {
		const finals = view(complete()).bracket.series.find((series) => series.final)!;
		expect(finals.games[0].away.score).toBe('—');
		expect(finals.games[0].home.score).toBe('—');
	});

	it('links a game only when the feed has its detail', () => {
		const games = card('east-r1-2').games;
		expect(games[0]).toMatchObject({ gameId: 'b201', linked: true });
		expect(games[4]).toMatchObject({ gameId: 'b205', linked: false });
	});

	it('tells a series with two teams, one team and none apart', () => {
		expect(card('east-r1-1').decided).toBe('both');
		expect(card('east-r2-1').decided).toBe('one');
		expect(card('east-r2-2').decided).toBe('none');
		expect(card('west-r1-1').decided).toBe('one');
	});

	it('titles each round and names the card from its titles and sides', () => {
		expect(card('east-r1-1').roundTitle).toBe('East · Round 1');
		expect(card('west-r2-1').roundTitle).toBe('West · Conference semifinals');
		expect(card('finals').roundTitle).toBe('NBA Finals');
		expect(card('east-r1-1').name).toBe('East · Round 1 · QXA · QXH');
	});

	it('flags the Champion only for a complete Finals', () => {
		const finals = (feed: PlayoffsFeed) =>
			view(feed).bracket.series.find((series) => series.final)!;
		expect(finals(complete()).champion).toBe(true);
		expect(finals(bracket()).champion).toBe(false);
		expect(card('east-r1-1').champion).toBe(false);
		expect(card('east-r1-1').complete).toBe(true);
	});

	it('writes the bracket in Spanish', () => {
		preferLanguages(['es-ES']);
		expect(card('east-r1-1').games[0].label).toBe('P1 · ante QXH');
		expect(card('east-r1-1').games[2].label).toBe('P3 · en QXH');
		expect(card('west-r1-1').bottom.label).toBe('Ganador del play-in del Oeste');
	});
});

describe('toPlayoffsView Spanish', () => {
	it('renders the Spanish strings', () => {
		preferLanguages(['es-ES']);
		const v = view(complete(), finalsFeed());
		expect(v.header.stateLine).toBe('Completa');
		expect(v.header.hero?.tag).toBe('Finales de la NBA 2027');
		expect(v.header.hero?.title).toBe('Campeones');
		expect(v.header.stages[1].label).toBe('Ronda 1');
		expect(v.series[0].tab).toBe('P1');
		expect(v.headToHead?.bars[0].label).toBe('Puntos por partido');
		expect(v.playIn[1].games[0].top.place).toBe('7.º');
		expect(v.road[0].series[0].result).toBe('4–0 G');
		expect(v.road[0].series[0].opponentSeed).toBe('n.º 8');
	});

	it('ends a lost road row with the Spanish loss letter', () => {
		preferLanguages(['es-ES']);
		const finals = finalsFeed();
		finals.road[1].series[0]!.result = 'loss';
		expect(view(complete(), finals).road[1].series[0].result.endsWith(' P')).toBe(true);
	});
});
