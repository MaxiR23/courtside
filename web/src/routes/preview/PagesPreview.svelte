<script lang="ts">
	// The dev-only catalog of every page: its header, body and loading skeleton, on both layouts.
	// Every entry is a section with a stable id, so /preview#standings-mobile opens it.
	// The clubs and the players are invented and no fixture names a real source.
	import { resolve } from '$app/paths';
	import AllStarPage from '#lib/components/AllStarPage.svelte';
	import CupPage from '#lib/components/CupPage.svelte';
	import DayPage from '#lib/components/DayPage.svelte';
	import GamePage from '#lib/components/GamePage.svelte';
	import Hero from '#lib/components/Hero.svelte';
	import PlayerPage from '#lib/components/PlayerPage.svelte';
	import PlayoffsPage from '#lib/components/PlayoffsPage.svelte';
	import Schedule from '#lib/components/Schedule.svelte';
	import ScheduleSkeleton from '#lib/components/ScheduleSkeleton.svelte';
	import SeriesPage from '#lib/components/SeriesPage.svelte';
	import StandingsPage from '#lib/components/StandingsPage.svelte';
	import TeamPage from '#lib/components/TeamPage.svelte';
	import type {
		AllStarHeaderView,
		AllStarPageState,
		AllStarView,
		ScoreRowView
	} from '#lib/all-star/types.ts';
	import type { SlotId } from '#lib/contract/cup.ts';
	import type { Conference, SeriesId } from '#lib/contract/playoffs.ts';
	import type {
		BracketNodeView,
		BracketSideView,
		BracketView,
		CupPageState,
		CupView,
		GroupRowView
	} from '#lib/cup/types.ts';
	import { CupMatchupStore } from '#lib/cup/matchup.svelte.ts';
	import { DayCardStats } from '#lib/day/card-stats.svelte.ts';
	import type { DayPageState, DayView } from '#lib/day/types.ts';
	import type {
		BoxRow,
		BoxScoreTeam,
		BoxTotals,
		GamePageState,
		GameView,
		HeaderTeam
	} from '#lib/game/types.ts';
	import type { HeroGame, HeroPlayer, HeroSide } from '#lib/hero/types.ts';
	import type { PlayerPageState, PlayerView, RecentGameRow, StatCell } from '#lib/player/types.ts';
	import type {
		PictureRowView,
		PlayoffsPageState,
		PlayoffsView,
		PlayoffStageView,
		SeriesCardView,
		SeriesPageState,
		SeriesPageView,
		SeriesSideView
	} from '#lib/playoffs/types.ts';
	import type {
		GameDetails,
		Leader,
		PanelPlayer,
		RowLayout,
		ScheduleDay,
		ScheduleGame
	} from '#lib/schedule/types.ts';
	import type {
		StandingsGroupView,
		StandingsLine,
		StandingsPageState,
		StandingsRowView,
		StandingsView
	} from '#lib/standings/types.ts';
	import type { RosterRow, TeamPageState, TeamView } from '#lib/team/types.ts';
	import awayPhoto from './player-away.svg';
	import homePhoto from './player-home.svg';

	type Club = { code: string; name: string; city: string; guest: false };
	const club = (code: string, name: string, city: string): Club => ({
		code,
		name,
		city,
		guest: false
	});
	const owls = club('QXA', 'Owls', 'Alderton');
	const summit = club('QXB', 'Summit', 'Brookfield');
	const rivers = club('QXC', 'Rivers', 'Carlton');
	const comets = club('QXD', 'Comets', 'Dunmore');
	const harriers = club('QXE', 'Harriers', 'Eastport');
	const pines = club('QXF', 'Pines', 'Fairview');
	const clubs = [owls, summit, rivers, comets, harriers, pines];
	const clubAt = (i: number) => clubs[i % clubs.length]!;

	const href = () => resolve('/preview');
	const allGamesHref = resolve('/');
	const standingsHref = resolve('/standings');
	const today = new Date(2026, 9, 4);
	const arena = 'Example Arena';
	const network = 'Network One';

	// Home: the hero and the schedule.
	const star = (c: Club, firstName: string, lastName: string, photo: string): HeroPlayer => ({
		firstName,
		lastName,
		shortName: lastName,
		teamCode: c.code,
		teamName: `${c.city} ${c.name}`,
		photo
	});
	const heroSide = (c: Club, player: HeroPlayer): HeroSide => ({
		...c,
		logo: null,
		accent: null,
		star: player
	});
	const heroGame = (id: string, status: HeroGame['status'], a: Club, h: Club): HeroGame => ({
		id,
		status,
		tipTime: '10:30 PM',
		arena,
		away: heroSide(a, star(a, 'Aaron', 'Example', awayPhoto)),
		home: heroSide(h, star(h, 'Bea', 'Sample', homePhoto))
	});
	const heroGames: HeroGame[] = [
		heroGame('hero-1', 'tonight', owls, summit),
		heroGame('hero-2', 'live', rivers, comets),
		heroGame('hero-3', 'final', harriers, pines)
	];

	const panel = (c: Club, firstName: string, lastName: string, photo: string): PanelPlayer => ({
		firstName,
		lastName,
		teamCode: c.code,
		photo
	});
	const leader = (c: Club, firstName: string, lastName: string, photo: string): Leader => ({
		firstName,
		lastName,
		photo,
		team: c,
		points: 31,
		rebounds: 8,
		assists: 6
	});
	const played = (a: Club, h: Club): GameDetails => ({
		kind: 'played',
		periods: { away: [28, 30, 25, 29], home: [24, 27, 26, 27] },
		leaders: {
			away: leader(a, 'Aaron', 'Example', awayPhoto),
			home: leader(h, 'Bea', 'Sample', homePhoto)
		},
		stats: {
			away: { fieldGoalPct: 0.478, threePointPct: 0.391, rebounds: 44, assists: 27, turnovers: 9 },
			home: { fieldGoalPct: 0.452, threePointPct: 0.417, rebounds: 41, assists: 24, turnovers: 14 }
		}
	});
	const scheduledGame = (id: string, a: Club, h: Club): ScheduleGame => ({
		id,
		away: a,
		home: h,
		status: { state: 'scheduled', tipTime: '9:00', tipSuffix: 'PM', network },
		cupTag: null,
		postseasonMark: null,
		allStarMark: null,
		details: {
			kind: 'scheduled',
			venue: arena,
			playersToWatch: {
				away: panel(a, 'Aaron', 'Example', awayPhoto),
				home: panel(h, 'Bea', 'Sample', homePhoto)
			}
		}
	});
	const liveGame = (id: string, a: Club, h: Club): ScheduleGame => ({
		id,
		away: a,
		home: h,
		status: { state: 'live', period: 'Q3', clock: '4:12', awayScore: 78, homeScore: 74 },
		cupTag: null,
		postseasonMark: null,
		allStarMark: null,
		details: played(a, h)
	});
	const finalGame = (id: string, a: Club, h: Club): ScheduleGame => ({
		id,
		away: a,
		home: h,
		status: { state: 'final', awayScore: 112, homeScore: 104, winner: 'away' },
		cupTag: null,
		postseasonMark: null,
		allStarMark: null,
		details: played(a, h)
	});
	const dayGames = [
		scheduledGame('day-1', owls, summit),
		liveGame('day-2', rivers, comets),
		finalGame('day-3', harriers, pines)
	];
	const homeDays: ScheduleDay[] = [
		{ date: new Date(2026, 9, 1), games: [dayGames[2]!] },
		{ date: new Date(2026, 9, 2), games: [] },
		{ date: new Date(2026, 9, 3), games: [dayGames[1]!, dayGames[2]!] },
		{ date: new Date(2026, 9, 4), games: dayGames },
		{ date: new Date(2026, 9, 5), games: [dayGames[0]!] },
		{ date: new Date(2026, 9, 6), games: [dayGames[0]!, dayGames[1]!] },
		{ date: new Date(2026, 9, 7), games: [dayGames[0]!] }
	];

	// Standings.
	const clinchKey = [
		{ clinch: { code: '*', tone: 'accent' as const }, label: 'Best record' },
		{ clinch: { code: 'z', tone: 'accent' as const }, label: 'Top seed' },
		{ clinch: { code: 'y', tone: 'ink' as const }, label: 'Division title' },
		{ clinch: { code: 'x', tone: 'ink' as const }, label: 'Playoffs' },
		{ clinch: { code: 'xp', tone: 'ink' as const }, label: 'Play-in' },
		{ clinch: { code: 'pb', tone: 'muted' as const }, label: 'Play-in berth' },
		{ clinch: { code: 'e', tone: 'muted' as const }, label: 'Eliminated' }
	];
	const standingsRow = (
		c: Club,
		seed: number,
		wins: number,
		losses: number,
		lineAfter: StandingsLine | null
	): StandingsRowView => ({
		code: c.code,
		team: c,
		seed: String(seed),
		city: c.city,
		name: c.name,
		strip: null,
		clinch: seed === 1 ? { code: 'x', tone: 'ink' } : null,
		eliminated: false,
		wins: String(wins),
		losses: String(losses),
		pct: (wins / (wins + losses)).toFixed(3).replace(/^0/, ''),
		gamesBehind: seed === 1 ? '—' : String(seed - 1),
		streak: { text: seed === 1 ? 'W3' : 'L1', win: seed === 1 },
		home: '9-3',
		away: '8-4',
		lastTen: '7-3',
		division: '6-2',
		conference: '12-5',
		pointsFor: '114.2',
		pointsAgainst: '108.9',
		differential: { value: '+5.3', accent: true },
		total: { value: '+90', accent: true },
		lineAfter
	});
	const standingsGroup = (
		key: string,
		title: string,
		meta: string,
		teams: Club[],
		lines: boolean
	): StandingsGroupView => ({
		key,
		title,
		meta,
		rows: teams.map((c, i) =>
			standingsRow(c, i + 1, 17 - i * 2, 5 + i * 2, lines && i === 1 ? 'playoff' : null)
		)
	});
	const standingsView: StandingsView = {
		header: { season: '2026-27', stateLine: 'Regular season · 22 games played', tag: null },
		conference: [
			standingsGroup('east', 'East', '3 teams', [owls, summit, rivers], true),
			standingsGroup('west', 'West', '3 teams', [comets, harriers, pines], true)
		],
		division: [
			standingsGroup('division-one', 'Division One', '3 teams', [owls, rivers, harriers], false),
			standingsGroup('division-two', 'Division Two', '3 teams', [summit, comets, pines], false)
		],
		key: clinchKey,
		lines: true
	};

	// Team.
	const info = (label: string, value: string, sub: string | null = null) => ({
		label,
		value,
		sub
	});
	const rosterRow = (id: string, name: string, number: string, position: string): RosterRow => ({
		id,
		name,
		photo: null,
		number,
		position,
		height: '6\'5"',
		weight: '205 lb',
		age: '27',
		born: 'Mar 3, 1999',
		birthplace: 'Alderton',
		college: 'Example State',
		experience: '5',
		status: { label: 'Active', tone: 'ink' }
	});
	const teamView: TeamView = {
		header: {
			team: owls,
			city: owls.city,
			name: owls.name,
			conferenceLine: 'Eastern Conference · Division One',
			cupLine: null,
			titles: null,
			colors: { primary: '#1d4ed8', secondary: '#facc15' },
			record: '12–5',
			winPct: '70.6%',
			recordSeason: '2026-27 record',
			cells: [
				info('Conference', '1st East'),
				info('Streak', 'W3'),
				info('Last 10', '7–3'),
				info('Playoffs', 'Clinched')
			]
		},
		tabs: [
			{ id: 'overview', label: 'Overview' },
			{ id: 'record', label: 'Record' },
			{ id: 'leaders', label: 'Leaders' },
			{ id: 'roster', label: 'Roster' },
			{ id: 'injuries', label: 'Injuries' }
		],
		mini: 'QXA 12–5',
		sections: {
			overview: {
				arena: { name: arena, city: owls.city, photo: null },
				coach: info('Coach', 'Sam Example'),
				colors: [{ hex: '#1d4ed8' }, { hex: '#facc15' }],
				nextGame: {
					gameId: 'next',
					linked: false,
					tag: null,
					date: 'Wednesday, October 7',
					opponent: { team: summit, isHome: true },
					place: `${arena} · ${owls.city}`,
					time: `7:30 PM · ${network}`
				}
			},
			record: {
				meta: '2026-27 regular season',
				large: [info('Home', '9–3'), info('Away', '3–2')],
				detail: [info('Streak', 'W3'), info('Last 10', '7–3')]
			},
			leaders: {
				meta: '2026-27 · per game',
				cards: [
					{
						playerId: 'p1',
						label: 'Points',
						value: '27.4',
						name: 'Aaron Example',
						line: '#2 · Guard',
						photo: null
					}
				]
			},
			roster: [rosterRow('p1', 'Aaron Example', '2', 'G'), rosterRow('p2', 'Cal Sample', '9', 'F')],
			injuries: [{ name: 'Cal Sample', line: '#9 · F', status: 'questionable', comment: null }],
			schedule: null
		}
	};

	// Player.
	const recentGame = (gameId: string): RecentGameRow => ({
		gameId,
		linked: false,
		result: 'win',
		resultLabel: 'W',
		date: 'Oct 2',
		opponent: { team: summit, isHome: false },
		score: '118–104',
		tag: null,
		points: '31',
		line: '8 REB · 6 AST'
	});
	const averageColumns = [
		{ key: 'gp', label: 'GP', muted: true },
		{ key: 'reb', label: 'REB' },
		{ key: 'ast', label: 'AST' },
		{ key: 'pts', label: 'PTS', points: true }
	];
	const averageCells: StatCell[] = ['17', '4.9', '6.4', '27.4'];
	const playerView: PlayerView = {
		header: {
			teamCode: owls.code,
			team: owls,
			status: { label: 'Active', injured: false },
			firstName: 'Aaron',
			lastName: 'Example',
			line: '#2 · Guard · Alderton Owls',
			allStarTag: null,
			injury: null,
			photo: homePhoto,
			stats: {
				label: '2026-27 · per game',
				cells: [info('Points', '27.4'), info('Rebounds', '4.9'), info('Assists', '6.4')]
			}
		},
		tabs: [
			{ id: 'profile', label: 'Profile' },
			{ id: 'averages', label: 'Averages' }
		],
		mini: '#2 A. Example',
		sections: {
			profile: {
				cells: [info('Height', '6\'5"', '196 cm'), info('Weight', '205 lb', '93 kg')],
				nextGame: {
					gameId: 'next',
					linked: false,
					tag: null,
					date: 'Wednesday, October 7',
					opponent: { team: summit, isHome: true },
					place: `${arena} · ${owls.city}`,
					time: `7:30 PM · ${network}`
				},
				live: null,
				recent: [recentGame('r1'), recentGame('r2')]
			},
			averages: {
				columns: averageColumns,
				rows: [
					{
						key: 'regular',
						label: 'Regular season',
						sub: '2026-27',
						cells: averageCells
					}
				]
			},
			seasons: null,
			milestones: null,
			gameLog: null,
			awards: null
		}
	};

	// Day.
	const dayView: DayView = {
		date: '2026-10-04',
		title: 'October 4, 2026',
		weekday: 'Sunday',
		seasonLabel: '2026-27',
		season: 2027,
		games: [dayGames[2]!, dayGames[0]!]
	};
	const detailReads = new DayCardStats(undefined);

	// Game.
	const headerTeam = (c: Club, record: string): HeaderTeam => ({ ...c, record });
	const boxRow = (id: string, name: string): BoxRow => ({
		id,
		name,
		minutes: '34:10',
		points: '24',
		fieldGoals: '9-17',
		threePoints: '3-7',
		freeThrows: '3-4',
		offensiveRebounds: '1',
		defensiveRebounds: '5',
		rebounds: '6',
		assists: '7',
		turnovers: '2',
		steals: '1',
		blocks: '0',
		fouls: '2',
		plusMinus: '+8',
		plusMinusPositive: true
	});
	const boxTotals: BoxTotals = {
		points: '110',
		fieldGoals: '40-85',
		threePoints: '12-31',
		freeThrows: '18-22',
		offensiveRebounds: '9',
		defensiveRebounds: '35',
		rebounds: '44',
		assists: '27',
		turnovers: '9',
		steals: '7',
		blocks: '4',
		fouls: '16',
		fieldGoalPct: '47.1%',
		threePointPct: '38.7%',
		freeThrowPct: '81.8%'
	};
	const boxTeam = (c: Club, prefix: string): BoxScoreTeam => ({
		team: c,
		starters: [boxRow(`${prefix}1`, 'Aaron Example'), boxRow(`${prefix}2`, 'Bea Sample')],
		bench: [boxRow(`${prefix}3`, 'Cal Sample')],
		totals: boxTotals
	});
	const gameView: GameView = {
		header: {
			layout: 'final',
			status: { state: 'final', text: `Final · Sunday, October 4 · ${arena}` },
			cupTag: null,
			postseasonMark: null,
			allStarMark: null,
			away: headerTeam(owls, '12–5'),
			home: headerTeam(summit, '10–7'),
			center: { kind: 'score', away: 110, home: 102, loser: 'home' },
			venue: null
		},
		tabs: [
			{ id: 'score', label: 'Score' },
			{ id: 'box-score', label: 'Box score' }
		],
		miniScore: { awayTeam: owls, away: 110, home: 102, homeTeam: summit },
		sections: {
			highlights: null,
			players: null,
			score: {
				lineScore: {
					away: { team: owls, periods: [28, 30, 25, 27], total: 110 },
					home: { team: summit, periods: [24, 27, 26, 25], total: 102 }
				},
				stats: null
			},
			winProbability: null,
			boxScore: { away: boxTeam(owls, 'a'), home: boxTeam(summit, 'h'), plusMinus: true },
			injuries: null,
			lastGames: null,
			standings: null,
			seasonSeries: null
		}
	};

	// Playoffs.
	const seriesIds: SeriesId[] = [
		'east-r1-1',
		'east-r1-2',
		'east-r1-3',
		'east-r1-4',
		'east-r2-1',
		'east-r2-2',
		'east-r3',
		'finals',
		'west-r3',
		'west-r2-1',
		'west-r2-2',
		'west-r1-1',
		'west-r1-2',
		'west-r1-3',
		'west-r1-4'
	];
	const roundTitle = (id: SeriesId) =>
		id === 'finals'
			? 'NBA Finals'
			: `${id.startsWith('east') ? 'East' : 'West'} · ${
					id.includes('r1') ? 'Round 1' : id.includes('r2') ? 'Round 2' : 'Conference finals'
				}`;
	const seriesSide = (c: Club, seed: string, wins: number, loser: boolean): SeriesSideView => ({
		team: c,
		seed,
		wins: String(wins),
		strip: null,
		accent: null,
		filled: wins,
		label: c.code,
		note: null,
		loser
	});
	const seriesCard = (id: SeriesId, i: number, complete: boolean): SeriesCardView => {
		const top = clubAt(i);
		const bottom = clubAt(i + 3);
		const topWins = complete ? 4 : i % 4;
		const bottomWins = complete ? i % 4 : (i + 1) % 4;
		const final = id === 'finals';
		return {
			id,
			name: `${roundTitle(id)} · ${top.code} · ${bottom.code}`,
			roundTitle: roundTitle(id),
			top: seriesSide(top, '1', topWins, false),
			bottom: seriesSide(bottom, '8', bottomWins, complete),
			decided: 'both',
			final,
			complete,
			champion: final && complete,
			score: `${topWins}–${bottomWins}`,
			headline: complete
				? `${top.code} wins ${topWins}–${bottomWins}`
				: `${top.code} leads ${topWins}–${bottomWins}`,
			lead: 'top',
			games: []
		};
	};
	const stages = (complete: boolean): PlayoffStageView[] =>
		(
			[
				['playin', 'Play-In'],
				['round_1', 'Round 1'],
				['round_2', 'Round 2'],
				['round_3', 'Conference finals'],
				['finals', 'NBA Finals']
			] as const
		).map(([key, label]) => ({
			key,
			label,
			dates: 'Apr 14 – Apr 18',
			status: complete ? 'complete' : key === 'round_1' ? 'in_progress' : 'upcoming',
			statusLabel: complete ? 'Complete' : key === 'round_1' ? 'In progress' : 'Upcoming'
		}));
	const pictureRow = (c: Club, i: number): PictureRowView => ({
		team: c,
		seed: String(i + 1),
		record: `${17 - i * 2}-${5 + i * 2}`,
		gamesBehind: i === 0 ? '—' : String(i),
		clinch: null,
		strip: null,
		line: i === 2 ? 'playoffs' : null
	});
	const pictureTable = (key: Conference, title: string, teams: Club[]) => ({
		key,
		title,
		rows: teams.map(pictureRow)
	});
	const playInGame = (conference: Conference) => ({
		key: 'seven_eight' as const,
		gameId: `play-in-${conference}`,
		linked: false,
		title: '7th vs 8th',
		top: { team: owls, label: owls.code, place: null, currently: null, loser: false },
		bottom: { team: summit, label: summit.code, place: null, currently: null, loser: false },
		score: null,
		when: `Apr 14 · 7:30 PM`,
		notes: []
	});
	const leaderRow = (id: string, name: string) => ({
		id,
		rank: '1',
		name,
		photo: null,
		team: owls.code,
		value: '31.8'
	});
	const playoffsBase = {
		picture: [
			pictureTable('east', 'East', [owls, summit, rivers]),
			pictureTable('west', 'West', [comets, harriers, pines])
		],
		playIn: [
			{ key: 'east' as const, title: 'East', games: [playInGame('east')] },
			{ key: 'west' as const, title: 'West', games: [playInGame('west')] }
		],
		playInCollapsed: false,
		conferenceMvps: [],
		leaders: [
			{
				key: 'points' as const,
				label: 'Points',
				first: leaderRow('p1', 'Aaron Example'),
				rest: [leaderRow('p2', 'Bea Sample')]
			}
		],
		awards: [
			{
				key: 'mvp',
				name: 'Most Valuable Player',
				code: 'mvp',
				kind: 'player' as const,
				winners: [{ id: 'p1', name: 'Aaron Example', photo: null, team: owls.code }]
			}
		]
	};
	const playoffsPicture: PlayoffsView = {
		...playoffsBase,
		header: {
			season: '2026-27',
			stateLine: 'Round 1 in progress',
			stages: stages(false),
			hero: null,
			tag: null
		},
		sections: ['picture', 'bracket', 'play-in', 'leaders', 'awards'],
		finalsMvp: null,
		series: [],
		bracket: {
			kicker: '2027 NBA Playoffs',
			series: seriesIds.map((id, i) => seriesCard(id, i, false))
		},
		road: [],
		headToHead: null
	};
	const playoffsChampion: PlayoffsView = {
		...playoffsBase,
		header: {
			season: '2026-27',
			stateLine: 'Postseason complete',
			stages: stages(true),
			hero: {
				label: '2027 NBA Champions',
				team: owls,
				city: owls.city,
				name: owls.name,
				subline: 'Won the series 4–1 over Summit · Jun 4 – Jun 19',
				accent: null,
				games: [
					{ key: 'f1', label: 'G1', score: '105–95', win: true, spoken: 'Game 1, 105–95, won' },
					{ key: 'f2', label: 'G2', score: '98–101', win: false, spoken: 'Game 2, 98–101, lost' }
				]
			},
			tag: null
		},
		sections: [
			'finals-mvp',
			'series',
			'road',
			'head-to-head',
			'leaders',
			'bracket',
			'play-in',
			'awards'
		],
		finalsMvp: {
			name: 'Aaron Example',
			photo: null,
			team: owls.code,
			teamName: `${owls.city} ${owls.name}`,
			mark: owls,
			accent: null,
			stats: [
				{ key: 'ppg', label: 'PPG', value: '31.8', accent: true },
				{ key: 'games', label: 'Games', value: '5', accent: false }
			]
		},
		series: [
			{
				key: 'f1',
				gameId: 'f1',
				linked: false,
				tab: 'G1',
				winner: owls.code,
				championWon: true,
				score: '105–95',
				overtime: false,
				video: null,
				chart: null,
				scoreLine: `${summit.code} 95 – 105 ${owls.code}`,
				leaders: null
			}
		],
		bracket: {
			kicker: '2027 NBA Playoffs',
			series: seriesIds.map((id, i) => seriesCard(id, i, true))
		},
		road: [
			{
				team: owls,
				name: `${owls.city} ${owls.name}`,
				seedLine: '#1 seed · 64-18',
				postseason: '16-6',
				series: [
					{
						key: 'r1',
						round: 'Round 1',
						opponentSeed: '#8',
						opponent: summit,
						strip: null,
						result: '4–1 W',
						loss: false
					}
				]
			}
		],
		headToHead: {
			records: [
				{ team: owls.code, record: '4–1' },
				{ team: summit.code, record: '1–4' }
			],
			bars: [
				{
					key: 'points',
					label: 'Points',
					sides: [
						{ value: '112.4', share: 1, better: true, color: null },
						{ value: '101.2', share: 0.9, better: false, color: null }
					]
				}
			],
			averages: null
		}
	};

	// Series.
	const seriesHeroSide = (c: Club, wins: string, lead: boolean, loser: boolean) => ({
		team: c,
		code: c.code,
		seed: 'No. 1 seed',
		wins,
		accent: null,
		lead,
		loser
	});
	const seriesGame = (n: number) => ({
		gameId: `series-${n}`,
		linked: false,
		key: `series-${n}`,
		title: `Game ${n}`,
		meta: `Apr ${18 + n} · ${arena}`,
		overtimeTag: null,
		sides: [
			{ team: owls, code: owls.code, score: '105', loser: false },
			{ team: summit, code: summit.code, score: '95', loser: true }
		] as [
			{ team: Club; code: string; score: string; loser: boolean },
			{ team: Club; code: string; score: string; loser: boolean }
		],
		leaders: null,
		rule: { accent: null }
	});
	const seriesView: SeriesPageView = {
		kicker: '2027 NBA Playoffs',
		round: 'East · Round 1',
		top: seriesHeroSide(owls, '4', true, false),
		bottom: seriesHeroSide(summit, '1', false, true),
		status: 'QXA wins the series 4–1',
		dates: 'Apr 19 – Apr 29',
		games: [seriesGame(1), seriesGame(2)]
	};

	// Cup.
	const slots: SlotId[] = [
		'east-qf-1',
		'east-qf-2',
		'east-sf',
		'final',
		'west-sf',
		'west-qf-1',
		'west-qf-2'
	];
	const cupSide = (c: Club, label: string): BracketSideView => ({
		team: c,
		name: c.name,
		label,
		rule: 'Best group winner',
		currently: null,
		meta: null,
		score: null,
		winner: false
	});
	const cupNode = (id: SlotId, i: number): BracketNodeView => ({
		id,
		roundLabel:
			id === 'final' ? 'Championship' : id.endsWith('sf') ? 'Semifinals' : 'Quarterfinals',
		mirrored: id.startsWith('west'),
		final: id === 'final',
		top: cupSide(clubAt(i), 'East #1 seed'),
		bottom: cupSide(clubAt(i + 3), 'East #2 seed'),
		date: 'Dec 13',
		venue: arena,
		broadcast: network,
		neutral: id === 'final',
		gameLink: null,
		rule: null
	});
	const cupBracket: BracketView = {
		nodes: slots.map(cupNode),
		known: Object.fromEntries(
			slots.flatMap((id) => [
				[`${id}:top`, true],
				[`${id}:bottom`, true]
			])
		) as BracketView['known'],
		rounds: {
			quarterfinals: 'Quarterfinals',
			semifinals: 'Semifinals',
			championship: 'Championship'
		},
		champion: null,
		kicker: '2026 NBA Cup',
		treeLabels: {
			quarterfinals: 'Quarterfinals',
			semifinals: 'Semifinals',
			championship: 'Championship'
		}
	};
	const groupRow = (c: Club, i: number): GroupRowView => ({
		team: c,
		position: String(i + 1),
		record: `${4 - i}-${i}`,
		gamesBehind: i === 0 ? '—' : String(i),
		perGame: { value: '+6.5', accent: true },
		total: { value: '+26', accent: true },
		streak: { text: 'W2', win: true },
		pointsFor: '452',
		pointsAgainst: '426',
		home: '2-0',
		away: '2-1',
		overtime: '0-0',
		tag: null,
		eliminated: false
	});
	const cupView: CupView = {
		header: {
			season: '2026-27',
			stateLine: 'Group play',
			team: null,
			stages: (
				[
					['group', 'Group play'],
					['quarterfinals', 'Quarterfinals'],
					['semifinals', 'Semifinals'],
					['championship', 'Championship']
				] as const
			).map(([key, label]) => ({
				key,
				label,
				dates: 'Nov 4 – Dec 2',
				status: key === 'group' ? 'in_progress' : 'upcoming',
				statusLabel: key === 'group' ? 'In progress' : 'Upcoming',
				note: null
			})),
			tag: null
		},
		sections: ['groups', 'wild-card', 'bracket', 'games'],
		drawn: true,
		groups: [
			{
				key: 'east-a',
				title: 'East Group A',
				meta: '3 teams',
				teams: [owls, summit, rivers],
				rows: [owls, summit, rivers].map(groupRow)
			}
		],
		legend: [{ clinch: { code: 'x', tone: 'ink' }, label: 'Clinched' }],
		wildCard: [
			{
				key: 'east',
				title: 'East',
				rows: [
					{
						team: owls,
						rank: '1',
						group: 'East Group A',
						record: '3-1',
						total: { value: '+26', accent: true },
						pointsFor: '452',
						tag: null,
						lineAfter: false
					}
				]
			}
		],
		bracket: cupBracket,
		filters: [
			{
				key: 'all',
				label: 'All',
				count: '1',
				days: [
					{
						key: '2026-11-04',
						label: 'Wednesday, November 4',
						games: [
							{
								gameId: 'cup-1',
								linked: false,
								stageLabel: 'Group play',
								away: { team: owls, score: null, loser: false },
								home: { team: summit, score: null, loser: false },
								status: { kind: 'time', text: '7:30 PM' },
								broadcast: network,
								notCounted: false
							}
						]
					}
				]
			}
		]
	};
	const matchup = new CupMatchupStore(undefined);

	// All-Star.
	const scoreRow = (c: Club, name: string, score: string, winner: boolean): ScoreRowView => ({
		team: c,
		name,
		score,
		winner,
		loser: !winner
	});
	const stripes = scoreRow(owls, 'Team Stripes', '25', true);
	const waves = scoreRow(summit, 'Team Waves', '23', false);
	const allStarHeader = (
		state: AllStarHeaderView['state'],
		fields: Partial<AllStarHeaderView>
	): AllStarHeaderView => ({
		state,
		tag: 'All-Star 2027',
		meta: `Feb 14 · ${arena}`,
		kicker: '',
		title: 'All-Star',
		score: null,
		stats: [],
		rows: [],
		buttons: [],
		plate: { kind: 'year', year: '2027' },
		seasonTag: null,
		...fields
	});
	const asgGame = {
		id: 'asg-1',
		round: { text: 'Championship', championship: true },
		status: { kind: 'final' as const, text: 'Final' },
		label: 'STR · WAV',
		rows: [stripes, waves]
	};
	const asgDetail = {
		id: 'asg-1',
		scheduled: null,
		video: null,
		placeholder: 'Highlights are not in yet',
		live: false,
		venueStrip: [],
		top5: [],
		scoreboard: { rows: [stripes, waves], status: 'Final' },
		leaders: null,
		teamStats: null
	};
	const asgTeam = (c: Club, name: string, champion: boolean) => ({
		key: c.code,
		team: c,
		name,
		placement: champion ? 'Champion' : 'Runner-up',
		champion,
		record: champion ? '2–0' : '1–1',
		results: [],
		roster: []
	});
	const allStarShared = {
		lastTime: null,
		mvp: null,
		scoreline: null,
		formatLine: null,
		games: [],
		details: {},
		boxes: {},
		defaultGame: null,
		teams: [],
		editionVideo: null
	};
	const allStarBefore: AllStarView = {
		...allStarShared,
		header: allStarHeader('before', {
			kicker: 'All-Star weekend is coming',
			rows: [
				{ key: 'date', label: 'Date', value: 'Feb 14' },
				{ key: 'venue', label: 'Venue', value: arena },
				{ key: 'format', label: 'Format', value: 'Round robin' }
			]
		}),
		sections: ['last-time'],
		lastTime: {
			champion: { kicker: '2026 champion', name: 'Team Stripes', meta: arena, score: '41–38' },
			mvp: null,
			video: null,
			link: 'Every game from 2026'
		}
	};
	const allStarLive: AllStarView = {
		...allStarShared,
		header: allStarHeader('live', {
			kicker: 'All-Star live now',
			stats: [
				{ key: 'pts', label: 'Points', value: '48', accent: true, countTo: 48 },
				{ key: 'reb', label: 'Rebounds', value: '21', accent: false, countTo: 21 },
				{ key: 'ast', label: 'Assists', value: '19', accent: false, countTo: 19 },
				{ key: 'stl', label: 'Steals', value: '6', accent: false, countTo: 6 }
			],
			plate: {
				kind: 'live',
				gameId: 'asg-1',
				header: 'Live · Semifinals',
				formatLine: null,
				rows: [
					scoreRow(owls, 'Team Stripes', '14', false),
					scoreRow(summit, 'Team Waves', '12', false)
				],
				clock: 'Q2 · 5:12',
				status: 'Q2 5:12',
				next: 'Next: Championship'
			}
		}),
		sections: ['games', 'teams'],
		games: [{ ...asgGame, status: { kind: 'live', text: 'Q2 5:12' } }],
		details: { 'asg-1': { ...asgDetail, live: true } },
		boxes: { 'asg-1': null },
		defaultGame: 'asg-1',
		teams: [asgTeam(owls, 'Team Stripes', false), asgTeam(summit, 'Team Waves', false)]
	};
	const allStarAfter: AllStarView = {
		...allStarShared,
		header: allStarHeader('after', {
			kicker: 'All-Star recap',
			title: 'Team Stripes',
			score: '25–23',
			plate: { kind: 'score', rows: [stripes, waves] }
		}),
		sections: ['mvp', 'games', 'teams'],
		mvp: {
			playerId: 'p1',
			name: 'Aaron Example',
			photo: null,
			jersey: '2',
			league: null,
			lines: [
				{
					key: 'l1',
					round: 'Championship',
					championship: true,
					result: 'W 25–23 vs Team Waves',
					stat: '27 PTS · 5 REB · 4 AST'
				}
			],
			total: '27 PTS · across 1 game'
		},
		scoreline: { gameId: 'asg-1', rows: [stripes, waves], overtime: false },
		games: [asgGame],
		details: { 'asg-1': asgDetail },
		boxes: { 'asg-1': null },
		defaultGame: 'asg-1',
		teams: [asgTeam(owls, 'Team Stripes', true), asgTeam(summit, 'Team Waves', false)]
	};

	// The entries: one section per page, state and layout.
	type PageEntry =
		| { kind: 'hero'; loading: boolean }
		| { kind: 'home-body' }
		| { kind: 'home-body-loading' }
		| { kind: 'standings'; state: StandingsPageState }
		| { kind: 'team'; state: TeamPageState }
		| { kind: 'player'; state: PlayerPageState }
		| { kind: 'day'; state: DayPageState }
		| { kind: 'game'; state: GamePageState }
		| { kind: 'playoffs'; state: PlayoffsPageState }
		| { kind: 'series'; state: SeriesPageState }
		| { kind: 'cup'; state: CupPageState }
		| { kind: 'all-star'; state: AllStarPageState };
	type Entry = PageEntry & { id: string; title: string; layout: RowLayout };

	const layouts: RowLayout[] = ['desktop', 'mobile'];
	// The id of an entry is its base and its layout; the title says the same in words.
	const both = (base: string, label: string, make: () => PageEntry): Entry[] =>
		layouts.map((layout) => ({
			...make(),
			id: `${base}-${layout}`,
			title: `Pages · ${label}${layout}`,
			layout
		}));
	const pair = <K extends Extract<PageEntry, { state: unknown }>['kind']>(
		name: string,
		kind: K,
		label: string,
		ready: Extract<PageEntry, { kind: K }>['state'],
		loading: Extract<PageEntry, { kind: K }>['state']
	): Entry[] => [
		...both(name, `${label}: `, () => ({ kind, state: ready }) as PageEntry),
		...both(`${name}-loading`, `${label}: loading, `, () => ({ kind, state: loading }) as PageEntry)
	];
	const ready = <V,>(view: V) => ({ kind: 'ready' as const, view });
	const loadingState = { kind: 'loading' as const };

	const entries: Entry[] = [
		...both('home-hero', 'Home hero: ', () => ({ kind: 'hero', loading: false })),
		...both('home-hero-loading', 'Home hero: loading, ', () => ({ kind: 'hero', loading: true })),
		{ id: 'home-body', title: 'Pages · Home body', layout: 'desktop', kind: 'home-body' },
		{
			id: 'home-body-loading',
			title: 'Pages · Home body: loading',
			layout: 'desktop',
			kind: 'home-body-loading'
		},
		...pair('standings', 'standings', 'Standings', ready(standingsView), loadingState),
		...pair('team', 'team', 'Team', ready(teamView), loadingState),
		...pair('player', 'player', 'Player', ready(playerView), loadingState),
		...pair('day', 'day', 'Day', ready(dayView), loadingState),
		...pair('game', 'game', 'Game', ready(gameView), loadingState),
		...both('playoffs-picture', 'Playoffs, picture: ', () => ({
			kind: 'playoffs',
			state: ready(playoffsPicture)
		})),
		...both('playoffs-champion', 'Playoffs, champion hero: ', () => ({
			kind: 'playoffs',
			state: ready(playoffsChampion)
		})),
		...both('playoffs-loading', 'Playoffs: loading, ', () => ({
			kind: 'playoffs',
			state: loadingState
		})),
		...pair('series', 'series', 'Series', ready(seriesView), loadingState),
		...pair('cup', 'cup', 'Cup', ready(cupView), loadingState),
		...both('all-star-before', 'All-Star, before: ', () => ({
			kind: 'all-star',
			state: ready(allStarBefore)
		})),
		...both('all-star-live', 'All-Star, live: ', () => ({
			kind: 'all-star',
			state: ready(allStarLive)
		})),
		...both('all-star-after', 'All-Star, after: ', () => ({
			kind: 'all-star',
			state: ready(allStarAfter)
		})),
		...both('all-star-loading', 'All-Star: loading, ', () => ({
			kind: 'all-star',
			state: loadingState
		}))
	];
</script>

{#each entries as entry (entry.id)}
	<section id={entry.id}>
		<h2>{entry.title}</h2>
		<div class:phone={entry.layout === 'mobile'}>
			{#if entry.kind === 'hero'}
				<Hero
					teamHref={href}
					games={entry.loading ? [] : heroGames}
					loading={entry.loading}
					{today}
					scheduleHref={allGamesHref}
					{standingsHref}
					layout={entry.layout}
					onMatchDetails={() => {}}
					spoilerFree={false}
					onSpoilerFreeToggle={() => {}}
					autoplay={false}
				/>
			{:else if entry.kind === 'home-body'}
				<Schedule teamHref={href} gameHref={href} days={homeDays} updatedMinutesAgo={3} />
			{:else if entry.kind === 'home-body-loading'}
				<ScheduleSkeleton />
			{:else if entry.kind === 'standings'}
				<StandingsPage
					state={entry.state}
					{allGamesHref}
					{standingsHref}
					layout={entry.layout}
					teamHref={href}
				/>
			{:else if entry.kind === 'team'}
				<TeamPage
					state={entry.state}
					{allGamesHref}
					{standingsHref}
					layout={entry.layout}
					gameHref={href}
					playerHref={href}
				/>
			{:else if entry.kind === 'player'}
				<PlayerPage
					state={entry.state}
					{allGamesHref}
					{standingsHref}
					layout={entry.layout}
					gameHref={href}
				/>
			{:else if entry.kind === 'day'}
				<DayPage
					state={entry.state}
					{allGamesHref}
					{standingsHref}
					previousHref={null}
					nextHref={href()}
					calendar={null}
					layout={entry.layout}
					gameHref={href}
					teamHref={href}
					{detailReads}
				/>
			{:else if entry.kind === 'game'}
				<GamePage
					state={entry.state}
					{allGamesHref}
					{standingsHref}
					layout={entry.layout}
					teamHref={href}
					playerHref={href}
				/>
			{:else if entry.kind === 'playoffs'}
				<PlayoffsPage
					state={entry.state}
					{allGamesHref}
					{standingsHref}
					layout={entry.layout}
					bracketLayout={entry.layout}
					mvpLayout={entry.layout}
					teamHref={href}
					gameHref={href}
					seriesHref={href}
					openSeries={() => {}}
				/>
			{:else if entry.kind === 'series'}
				<SeriesPage
					state={entry.state}
					{allGamesHref}
					{standingsHref}
					layout={entry.layout}
					bracketHref={href()}
					gameHref={href}
				/>
			{:else if entry.kind === 'cup'}
				<CupPage
					state={entry.state}
					{allGamesHref}
					{standingsHref}
					layout={entry.layout}
					teamHref={href}
					gameHref={href}
					playerHref={href}
					{matchup}
				/>
			{:else}
				<AllStarPage
					state={entry.state}
					{allGamesHref}
					{standingsHref}
					layout={entry.layout}
					teamHref={href}
					playerHref={href}
				/>
			{/if}
		</div>
	</section>
{/each}

<style>
	section {
		margin-block: var(--panel-section-gap);
	}

	.phone {
		max-width: var(--hero-column-min);
	}
</style>
