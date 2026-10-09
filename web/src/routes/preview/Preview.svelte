<script lang="ts">
	import { resolve } from '$app/paths';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Button from '#lib/components/Button.svelte';
	import DayStrip from '#lib/components/DayStrip.svelte';
	import GameCard from '#lib/components/GameCard.svelte';
	import GameHeader from '#lib/components/GameHeader.svelte';
	import GamePage from '#lib/components/GamePage.svelte';
	import GameVideos from '#lib/components/GameVideos.svelte';
	import Hero from '#lib/components/Hero.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import LiveBadge from '#lib/components/LiveBadge.svelte';
	import SeasonSeries from '#lib/components/SeasonSeries.svelte';
	import Schedule from '#lib/components/Schedule.svelte';
	import SectionTabs from '#lib/components/SectionTabs.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
	import TeamPage from '#lib/components/TeamPage.svelte';
	import PlayerPage from '#lib/components/PlayerPage.svelte';
	import type {
		BoxRow,
		BoxScoreSection,
		BoxScoreTeam,
		GameHeaderView,
		GameSections,
		GameView,
		HeaderTeam,
		InjuriesSection,
		LastGamesSection,
		LineScoreTeam,
		PlayersSection,
		ScoreSection,
		SeasonSeriesSection,
		SectionTab,
		StandingsSection,
		StatLeads,
		VideosSection,
		WinProbabilitySection
	} from '#lib/game/types.ts';
	import type {
		PlayerPageState,
		PlayerView,
		RecentGameRow,
		StatCell,
		StatRowView
	} from '#lib/player/types.ts';
	import type { RosterRow, ScheduleRowView, TeamPageState, TeamView } from '#lib/team/types.ts';
	import { SpoilerFree } from '#lib/schedule/spoiler-free.svelte.ts';
	import type { TeamMarkTeam } from '#lib/team/mark.ts';
	import type { HeroGame, HeroPlayer } from '#lib/hero/types.ts';
	import type {
		GameDetails,
		GameHighlights,
		Leader,
		PanelPlayer,
		ScheduleDay,
		ScheduleGame
	} from '#lib/schedule/types.ts';
	import awayPhoto from './player-away.svg';
	import highlight1 from './highlight-1.svg';
	import highlight2 from './highlight-2.svg';
	import highlightPlayer from './highlight-player.svg';
	import homePhoto from './player-home.svg';

	const away: HeroPlayer = {
		firstName: 'Stephen',
		lastName: 'Curry',
		shortName: 'Curry',
		teamCode: 'GSW',
		teamName: 'Golden State Warriors',
		photo: awayPhoto
	};
	const home: HeroPlayer = {
		firstName: 'LeBron',
		lastName: 'James',
		shortName: 'James',
		teamCode: 'LAL',
		teamName: 'Los Angeles Lakers',
		photo: homePhoto
	};
	// A league team as the feeds send an opponent, and a guest without a code (ADR 0026).
	const league = (code: string): TeamMarkTeam => ({ code, name: null, city: null, guest: false });
	const versus = (code: string, isHome = true) => ({ team: league(code), isHome });
	const guestMariners: TeamMarkTeam = {
		code: null,
		name: 'Mariners',
		city: 'Harbor City',
		guest: true
	};
	const allGamesHref = resolve('/');
	const standingsHref = resolve('/standings');
	const headerAway: HeaderTeam = {
		code: 'GSW',
		name: 'Warriors',
		city: 'Golden State',
		record: '12–5',
		guest: false
	};
	const headerHome: HeaderTeam = {
		code: 'LAL',
		name: 'Lakers',
		city: 'Los Angeles',
		record: '10–7',
		guest: false
	};
	const venueStrip = {
		arena: 'Chase Center',
		city: 'San Francisco',
		photo: highlight1,
		cells: [
			{ label: 'Tip-off', value: '10:30 PM ET', sub: 'Sunday, October 4' },
			{ label: 'Venue', value: 'Chase Center', sub: 'San Francisco' },
			{ label: 'Broadcast', value: 'Network One', sub: null }
		]
	};
	const preGameHeader = (
		state: 'scheduled' | 'delayed' | 'postponed' | 'canceled'
	): GameHeaderView => ({
		layout: 'pre-game',
		status: { state, text: 'Sunday, October 4 · Chase Center' },
		away: headerAway,
		home: headerHome,
		center:
			state === 'postponed' || state === 'canceled'
				? { kind: 'none' }
				: {
						kind: 'tip-off',
						tipTime: '10:30',
						tipSuffix: 'PM ET',
						broadcast: 'Network One',
						delayed: state === 'delayed'
					},
		venue: venueStrip
	});
	const liveHeader = (text: string): GameHeaderView => ({
		layout: 'live',
		status: { state: 'live', text },
		away: headerAway,
		home: headerHome,
		center: { kind: 'score', away: 63, home: 62, loser: null },
		venue: null
	});
	const finalHeader: GameHeaderView = {
		layout: 'final',
		status: { state: 'final', text: 'Final · Sunday, October 4 · Chase Center' },
		away: headerAway,
		home: headerHome,
		center: { kind: 'score', away: 112, home: 104, loser: 'home' },
		venue: null
	};
	const overtimeHeader: GameHeaderView = {
		...finalHeader,
		center: { kind: 'score', away: 132, home: 130, loser: 'home' }
	};
	const headerStates: { title: string; header: GameHeaderView }[] = [
		{ title: 'GameHeader: scheduled', header: preGameHeader('scheduled') },
		{ title: 'GameHeader: delayed', header: preGameHeader('delayed') },
		{ title: 'GameHeader: postponed', header: preGameHeader('postponed') },
		{ title: 'GameHeader: canceled', header: preGameHeader('canceled') },
		{ title: 'GameHeader: live', header: liveHeader('Q3 · 4:12 · Chase Center') },
		{ title: 'GameHeader: halftime', header: liveHeader('Halftime · Chase Center') },
		{ title: 'GameHeader: overtime', header: liveHeader('OT1 · 2:30 · Chase Center') },
		{ title: 'GameHeader: final', header: finalHeader }
	];
	const mobileHeaders = [
		preGameHeader('scheduled'),
		liveHeader('Q3 · 4:12 · Chase Center'),
		finalHeader
	];
	const noPhotoHeader: GameHeaderView = {
		...preGameHeader('scheduled'),
		venue: { ...venueStrip, photo: null }
	};
	const tabs = (...entries: [SectionTab['id'], string][]): SectionTab[] =>
		entries.map(([id, label]) => ({ id, label }));
	const miniScore = { awayTeam: league('GSW'), away: 63, home: 62, homeTeam: league('LAL') };
	const finalMiniScore = { ...miniScore, away: 112, home: 104 };
	const overtimeMiniScore = { ...miniScore, away: 132, home: 130 };
	const tabStates = [
		{
			title: 'SectionTabs: pre-game',
			tabs: tabs(
				['players', 'Players'],
				['injuries', 'Injuries'],
				['last-games', 'Last 5'],
				['standings', 'Standings'],
				['season-series', 'Season series']
			),
			miniScore: null
		},
		{
			title: 'SectionTabs: live',
			tabs: tabs(
				['score', 'Score'],
				['win-probability', 'Win prob.'],
				['box-score', 'Box score'],
				['injuries', 'Injuries']
			),
			miniScore
		},
		{
			title: 'SectionTabs: final',
			tabs: tabs(
				['highlights', 'Highlights'],
				['score', 'Score'],
				['win-probability', 'Win prob.'],
				['box-score', 'Box score'],
				['injuries', 'Injuries'],
				['season-series', 'Series'],
				['videos', 'Videos']
			),
			miniScore: finalMiniScore
		}
	];
	const noSections: GameSections = {
		highlights: null,
		players: null,
		score: null,
		winProbability: null,
		boxScore: null,
		injuries: null,
		lastGames: null,
		standings: null,
		seasonSeries: null,
		videos: null
	};
	const postponedView: GameView = {
		header: preGameHeader('postponed'),
		tabs: [],
		miniScore: null,
		sections: noSections
	};
	const today = new Date(2026, 9, 4);
	const heroStates = [
		{ title: 'Hero: Tonight', status: 'tonight' },
		{ title: 'Hero: Live now', status: 'live' },
		{ title: 'Hero: Final', status: 'final' }
	] as const;
	const heroGame = (id: string, status: HeroGame['status']): HeroGame => ({
		id,
		status,
		tipTime: '10:30 PM ET',
		arena: 'Chase Center',
		away: { code: 'GSW', name: 'Warriors', star: away },
		home: { code: 'LAL', name: 'Lakers', star: home }
	});
	const heroGames: HeroGame[] = [
		heroGame('one', 'tonight'),
		heroGame('two', 'live'),
		heroGame('three', 'final')
	];

	const warriors = { code: 'GSW', name: 'Warriors', city: 'Golden State', guest: false };
	const lakers = { code: 'LAL', name: 'Lakers', city: 'Los Angeles', guest: false };
	const celtics = { code: 'BOS', name: 'Celtics', city: 'Boston', guest: false };
	const knicks = { code: 'NYK', name: 'Knicks', city: 'New York', guest: false };
	const nuggets = { code: 'DEN', name: 'Nuggets', city: 'Denver', guest: false };
	const suns = { code: 'PHX', name: 'Suns', city: 'Phoenix', guest: false };
	const awayPlayer: PanelPlayer = {
		firstName: away.firstName,
		lastName: away.lastName,
		teamCode: away.teamCode,
		photo: awayPhoto
	};
	const homePlayer: PanelPlayer = {
		firstName: home.firstName,
		lastName: home.lastName,
		teamCode: home.teamCode,
		photo: homePhoto
	};
	const leader = (
		player: PanelPlayer,
		points: number,
		rebounds: number,
		assists: number
	): Leader => ({
		firstName: player.firstName,
		lastName: player.lastName,
		photo: player.photo,
		team: league(player.teamCode),
		points,
		rebounds,
		assists
	});
	const sampleHighlights: GameHighlights = {
		platform: 'Video platform',
		searchUrl: resolve('/preview'),
		videos: [
			{
				id: 'v1',
				title: 'Nuggets at Suns: full game highlights',
				channel: 'Placeholder channel',
				thumbnail: highlight1,
				embedUrl: highlightPlayer
			},
			{
				id: 'v2',
				title: 'Every three from the fourth quarter',
				channel: 'Placeholder channel',
				thumbnail: highlight2,
				embedUrl: highlightPlayer
			}
		]
	};
	const singleHighlights: GameHighlights = {
		...sampleHighlights,
		videos: [{ ...sampleHighlights.videos[0], id: 'v3' }]
	};
	const pendingHighlights: GameHighlights = { ...sampleHighlights, videos: [] };
	const lineScoreTeam = (team: HeaderTeam, periods: number[], total: number): LineScoreTeam => ({
		team,
		periods,
		total
	});
	const detailScore = (away: LineScoreTeam, home: LineScoreTeam): ScoreSection => {
		const leads: StatLeads = {
			fieldGoalPct: 'away',
			threePointPct: 'home',
			freeThrowPct: null,
			rebounds: 'away',
			assists: 'home',
			turnovers: 'home',
			steals: 'away',
			blocks: 'home'
		};
		return {
			lineScore: { away, home },
			stats: {
				away: {
					fieldGoalPct: 0.478,
					threePointPct: 0.391,
					freeThrowPct: 0.8,
					rebounds: 44,
					assists: 27,
					turnovers: 9,
					steals: 8,
					blocks: 3
				},
				home: {
					fieldGoalPct: 0.452,
					threePointPct: 0.417,
					freeThrowPct: 0.8,
					rebounds: 41,
					assists: 30,
					turnovers: 14,
					steals: 6,
					blocks: 5
				},
				leads
			}
		};
	};
	const boxRow = (id: string, name: string, plusMinus: string): BoxRow => ({
		id,
		name,
		minutes: '24:10',
		points: '20',
		fieldGoals: '8-15',
		threePoints: '2-6',
		freeThrows: '2-2',
		offensiveRebounds: '1',
		defensiveRebounds: '4',
		rebounds: '5',
		assists: '6',
		turnovers: '2',
		steals: '1',
		blocks: '0',
		fouls: '2',
		plusMinus,
		plusMinusPositive: plusMinus.startsWith('+')
	});
	const boxTeam = (team: HeaderTeam, names: string[], points: number): BoxScoreTeam => ({
		team,
		starters: names
			.slice(0, 2)
			.map((name, i) => boxRow(`${team.name}-s${i}`, name, i ? '-3' : '+4')),
		bench: names.slice(2).map((name, i) => boxRow(`${team.name}-b${i}`, name, '0')),
		totals: {
			points: String(points),
			fieldGoals: '40-84',
			threePoints: '12-31',
			freeThrows: '20-24',
			offensiveRebounds: '9',
			defensiveRebounds: '35',
			rebounds: '44',
			assists: '27',
			turnovers: '9',
			steals: '8',
			blocks: '3',
			fouls: '18',
			fieldGoalPct: '47.6%',
			threePointPct: '38.7%',
			freeThrowPct: '83.3%'
		}
	});
	const sampleBox = (away: number, home: number): BoxScoreSection => ({
		away: boxTeam(headerAway, ['Stephen Curry', 'Draymond Green', 'Jonathan Kuminga'], away),
		home: boxTeam(headerHome, ['LeBron James', 'Anthony Davis', 'Austin Reaves'], home)
	});
	const liveBox = sampleBox(63, 62);
	const finalBox = sampleBox(112, 104);
	const overtimeBox = sampleBox(132, 130);
	const curve = (seconds: number[], last: number) =>
		seconds.map((elapsedSeconds, i) => ({
			elapsedSeconds,
			homeWinProbability: i === seconds.length - 1 ? last : 0.5 + 0.18 * Math.sin(i / 2)
		}));
	const quarterStarts = [0, 720, 1440, 2160];
	const sampleChart: WinProbabilitySection = {
		away: headerAway,
		home: headerHome,
		middle: '50%',
		meta: 'LAL 68%',
		points: curve([300, 600, 900, 1200, 1500, 1800, 1908], 0.68),
		boundaries: {
			periods: quarterStarts.map((start, i) => ({ label: `Q${i + 1}`, start })),
			end: 2880
		}
	};
	const samplePlayers: PlayersSection = {
		away: { ...away, id: 'preview-away', teamName: 'Golden State Warriors', photo: awayPhoto },
		home: { ...home, id: 'preview-home', teamName: 'Los Angeles Lakers', photo: homePhoto }
	};
	const sampleInjuries: InjuriesSection = {
		away: {
			code: 'GSW',
			name: headerAway.name,
			injuries: [
				{
					id: 'preview-1',
					name: 'Draymond Green',
					status: 'out',
					comment: 'Left knee soreness, out for the game.'
				},
				{ id: null, name: 'Jonathan Kuminga', status: 'doubtful', comment: null },
				{ id: 'preview-3', name: 'Brandin Podziemski', status: 'questionable', comment: null }
			]
		},
		home: {
			code: 'LAL',
			name: headerHome.name,
			injuries: []
		}
	};
	const sampleInjuriesBoth: InjuriesSection = {
		...sampleInjuries,
		home: {
			code: 'LAL',
			name: headerHome.name,
			injuries: [
				{ id: 'preview-4', name: 'Gabe Vincent', status: 'probable', comment: null },
				{ id: null, name: 'Rui Hachimura', status: 'day-to-day', comment: 'Ankle sprain.' }
			]
		}
	};
	const sampleLastGames: LastGamesSection = {
		away: {
			code: 'GSW',
			name: headerAway.name,
			strip: [
				{ result: 'loss', label: 'L' },
				{ result: 'win', label: 'W' },
				{ result: 'win', label: 'W' },
				{ result: 'loss', label: 'L' },
				{ result: 'win', label: 'W' }
			],
			rows: [
				{
					result: 'win',
					resultLabel: 'W',
					date: 'Oct 5',
					opponent: versus('DEN'),
					score: '118–104'
				},
				{
					result: 'loss',
					resultLabel: 'L',
					date: 'Oct 3',
					opponent: versus('PHX', false),
					score: '99–107'
				},
				{
					result: 'win',
					resultLabel: 'W',
					date: 'Oct 1',
					opponent: versus('SAC'),
					score: '121–110'
				},
				{
					result: 'win',
					resultLabel: 'W',
					date: 'Sep 29',
					opponent: versus('LAC', false),
					score: '112–109'
				},
				{
					result: 'loss',
					resultLabel: 'L',
					date: 'Sep 27',
					opponent: versus('DAL'),
					score: '101–113'
				}
			]
		},
		home: {
			code: 'LAL',
			name: headerHome.name,
			strip: [
				{ result: 'win', label: 'W' },
				{ result: 'loss', label: 'L' }
			],
			rows: [
				{
					result: 'loss',
					resultLabel: 'L',
					date: 'Oct 4',
					opponent: versus('OKC', false),
					score: '98–110'
				},
				{
					result: 'win',
					resultLabel: 'W',
					date: 'Oct 2',
					opponent: versus('MIA'),
					score: '115–101'
				}
			]
		}
	};
	const sampleStandings: StandingsSection = {
		away: {
			code: 'GSW',
			name: headerAway.name,
			conference: '3rd West',
			record: '12–5',
			home: '7–2',
			away: '5–3',
			lastTen: '7–3'
		},
		home: {
			code: 'LAL',
			name: headerHome.name,
			conference: '1st West',
			record: '14–3',
			home: '8–1',
			away: '6–2',
			lastTen: '8–2'
		}
	};
	const playedSeries: SeasonSeriesSection['games'] = [
		{
			date: 'Jan 10',
			current: false,
			awayCode: 'GSW',
			awayPoints: 118,
			homePoints: 112,
			homeCode: 'LAL',
			loser: 'home',
			arena: 'Chase Center'
		},
		{
			date: 'Dec 2',
			current: false,
			awayCode: 'LAL',
			awayPoints: 121,
			homePoints: 109,
			homeCode: 'GSW',
			loser: 'home',
			arena: 'Crypto.com Arena'
		},
		{
			date: 'Nov 14',
			current: false,
			awayCode: 'GSW',
			awayPoints: 104,
			homePoints: 99,
			homeCode: 'LAL',
			loser: 'home',
			arena: 'Chase Center'
		}
	];
	const preGameSeries: SeasonSeriesSection = {
		summary: 'GSW lead 2–1',
		meta: '3 of 4 games played',
		games: [
			{
				date: 'This game',
				current: true,
				awayCode: 'GSW',
				awayPoints: null,
				homePoints: null,
				homeCode: 'LAL',
				loser: null,
				arena: 'Chase Center'
			},
			...playedSeries
		]
	};
	const finalSeries: SeasonSeriesSection = {
		summary: 'GSW lead 3–1',
		meta: '4 of 4 games played',
		games: [
			{
				date: 'This game',
				current: true,
				awayCode: 'GSW',
				awayPoints: 112,
				homePoints: 104,
				homeCode: 'LAL',
				loser: 'home',
				arena: 'Chase Center'
			},
			...playedSeries
		]
	};
	const firstMeetingSeries: SeasonSeriesSection = {
		summary: 'First meeting',
		meta: '0 of 4 games played',
		games: []
	};
	const sampleVideos: VideosSection = [
		{
			title: 'Curry hits seven threes',
			duration: '2:14',
			thumbnail: highlight2,
			href: resolve('/preview')
		},
		{ title: 'Full game recap', duration: '5:30', thumbnail: null, href: resolve('/preview') }
	];
	const preGameSections: GameSections = {
		...noSections,
		players: samplePlayers,
		injuries: sampleInjuriesBoth,
		lastGames: sampleLastGames,
		standings: sampleStandings,
		seasonSeries: preGameSeries
	};
	const liveSections: GameSections = {
		...noSections,
		score: detailScore(
			lineScoreTeam(headerAway, [28, 25, 10], 63),
			lineScoreTeam(headerHome, [26, 24, 12], 62)
		),
		winProbability: sampleChart,
		boxScore: liveBox,
		injuries: sampleInjuries
	};
	const finalSections: GameSections = {
		...noSections,
		highlights: sampleHighlights,
		score: detailScore(
			lineScoreTeam(headerAway, [30, 28, 26, 28], 112),
			lineScoreTeam(headerHome, [24, 27, 25, 28], 104)
		),
		winProbability: {
			...sampleChart,
			meta: 'GSW win',
			points: curve([0, 480, 960, 1440, 1920, 2400, 2880], 0)
		},
		boxScore: finalBox,
		injuries: sampleInjuriesBoth,
		seasonSeries: finalSeries,
		videos: sampleVideos
	};
	const overtimeSections: GameSections = {
		...finalSections,
		boxScore: overtimeBox,
		highlights: null,
		injuries: null,
		seasonSeries: null,
		videos: null,
		score: detailScore(
			lineScoreTeam(headerAway, [28, 25, 30, 27, 12, 10], 132),
			lineScoreTeam(headerHome, [30, 26, 24, 30, 12, 8], 130)
		),
		winProbability: {
			...sampleChart,
			meta: 'GSW win',
			points: curve([0, 720, 1440, 2160, 2880, 3180, 3480], 0),
			boundaries: {
				periods: [
					...quarterStarts.map((start, i) => ({ label: `Q${i + 1}`, start })),
					{ label: 'OT1', start: 2880 },
					{ label: 'OT2', start: 3180 }
				],
				end: 3480
			}
		}
	};
	const sectionViews: { title: string; view: GameView }[] = [
		{
			title: 'GamePage: pre-game sections',
			view: {
				header: preGameHeader('scheduled'),
				tabs: tabs(
					['players', 'Players'],
					['injuries', 'Injuries'],
					['last-games', 'Last 5'],
					['standings', 'Standings'],
					['season-series', 'Season series']
				),
				miniScore: null,
				sections: preGameSections
			}
		},
		{
			title: 'GamePage: live sections',
			view: {
				header: liveHeader('Q3 · 4:12 · Chase Center'),
				tabs: tabs(
					['score', 'Score'],
					['win-probability', 'Win prob.'],
					['box-score', 'Box score'],
					['injuries', 'Injuries']
				),
				miniScore,
				sections: liveSections
			}
		},
		{
			title: 'GamePage: final sections',
			view: {
				header: finalHeader,
				tabs: tabs(
					['highlights', 'Highlights'],
					['score', 'Score'],
					['win-probability', 'Win prob.'],
					['box-score', 'Box score'],
					['injuries', 'Injuries'],
					['season-series', 'Series'],
					['videos', 'Videos']
				),
				miniScore: finalMiniScore,
				sections: finalSections
			}
		},
		{
			title: 'GamePage: overtime sections',
			view: {
				header: overtimeHeader,
				tabs: tabs(
					['score', 'Score'],
					['win-probability', 'Win prob.'],
					['box-score', 'Box score']
				),
				miniScore: overtimeMiniScore,
				sections: overtimeSections
			}
		}
	];
	const played = (
		periods: { away: number[]; home: number[] },
		awayTeamCode: string,
		homeTeamCode: string,
		highlights?: GameHighlights
	): GameDetails => ({
		kind: 'played',
		periods,
		leaders: {
			away: leader({ ...awayPlayer, teamCode: awayTeamCode }, 34, 3, 8),
			home: leader({ ...homePlayer, teamCode: homeTeamCode }, 29, 9, 7)
		},
		stats: {
			away: { fieldGoalPct: 0.478, threePointPct: 0.391, rebounds: 44, assists: 27, turnovers: 9 },
			home: { fieldGoalPct: 0.452, threePointPct: 0.417, rebounds: 41, assists: 27, turnovers: 14 }
		},
		...(highlights ? { highlights } : {})
	});
	const sampleGames: ScheduleGame[] = [
		{
			id: 'scheduled',
			away: warriors,
			home: lakers,
			status: { state: 'scheduled', tipTime: '9:00', tipSuffix: 'PM ET', network: 'Courtside TV' },
			details: {
				kind: 'scheduled',
				venue: 'Crypto.com Arena',
				playersToWatch: { away: awayPlayer, home: homePlayer }
			}
		},
		{
			id: 'live',
			away: celtics,
			home: knicks,
			status: { state: 'live', period: 'Q3', clock: '4:12', awayScore: 78, homeScore: 74 },
			details: played({ away: [28, 26, 24], home: [25, 27, 22] }, 'BOS', 'NYK')
		},
		{
			id: 'final',
			away: nuggets,
			home: suns,
			status: { state: 'final', awayScore: 112, homeScore: 104, winner: 'away' },
			details: played(
				{ away: [30, 28, 26, 28], home: [24, 27, 25, 28] },
				'DEN',
				'PHX',
				sampleHighlights
			)
		}
	];
	// Games with no score and no tip time. They have no details, so they do not expand.
	const statusGames: ScheduleGame[] = (['delayed', 'postponed', 'canceled'] as const).map(
		(state) => ({ id: state, away: celtics, home: knicks, status: { state } })
	);
	const overtimeGame: ScheduleGame = {
		id: 'overtime',
		away: celtics,
		home: knicks,
		status: { state: 'final', awayScore: 132, homeScore: 130, winner: 'away' },
		details: played({ away: [28, 25, 30, 27, 12, 10], home: [30, 26, 24, 30, 12, 8] }, 'BOS', 'NYK')
	};
	const singleHighlightGame: ScheduleGame = {
		id: 'single-highlight',
		away: nuggets,
		home: suns,
		status: { state: 'final', awayScore: 112, homeScore: 104, winner: 'away' },
		details: played(
			{ away: [30, 28, 26, 28], home: [24, 27, 25, 28] },
			'DEN',
			'PHX',
			singleHighlights
		)
	};
	const pendingGame: ScheduleGame = {
		id: 'pending',
		away: nuggets,
		home: suns,
		status: { state: 'final', awayScore: 112, homeScore: 104, winner: 'away' },
		details: played(
			{ away: [30, 28, 26, 28], home: [24, 27, 25, 28] },
			'DEN',
			'PHX',
			pendingHighlights
		)
	};
	const expandedGames = [
		{ title: 'GameCard: expanded scheduled', game: sampleGames[0] },
		{ title: 'GameCard: expanded live', game: sampleGames[1] },
		{ title: 'GameCard: expanded final', game: sampleGames[2] },
		{ title: 'GameCard: expanded overtime', game: overtimeGame },
		{ title: 'GameCard: expanded final, one highlight', game: singleHighlightGame },
		{ title: 'GameCard: expanded final, highlights pending', game: pendingGame }
	];
	const sampleDays: ScheduleDay[] = [
		{ date: new Date(2026, 9, 1), games: [sampleGames[2]] },
		{ date: new Date(2026, 9, 2), games: [] },
		{ date: new Date(2026, 9, 3), games: [sampleGames[1], sampleGames[2]] },
		{ date: new Date(2026, 9, 4), games: sampleGames },
		{ date: new Date(2026, 9, 5), games: [sampleGames[0]] },
		{ date: new Date(2026, 9, 6), games: [sampleGames[0], sampleGames[1]] },
		{ date: new Date(2026, 9, 7), games: [sampleGames[0]] }
	];
	const stripDays = sampleDays.map((d) => ({ date: d.date, gameCount: d.games.length }));
	let desktopSelected = $state(3);
	let compactSelected = $state(3);
	let previewPlaying = $state<string | null>(null);
	let spoilerOpen = $state<string | null>(null);
	const spoilerFree = new SpoilerFree();

	$effect(() => spoilerFree.load());
	const teamGameHref = () => resolve('/preview');
	const teamHref = () => resolve('/preview');
	const playerHref = () => resolve('/preview');
	const teamScheduleRow = (
		gameId: string,
		overrides: Partial<ScheduleRowView> = {}
	): ScheduleRowView => ({
		gameId,
		linked: true,
		weekday: 'Thu',
		date: 'Oct 23',
		opponent: versus('HOU'),
		tags: [],
		next: false,
		outcome: { kind: 'played', result: 'win', resultLabel: 'W', score: '118–104', side: 'Home' },
		...overrides
	});
	const teamRoster: RosterRow[] = [
		{
			id: 'p1',
			name: 'Stephen Curry',
			photo: awayPhoto,
			number: '30',
			position: 'G',
			height: '6-2',
			weight: '185',
			age: '37',
			born: 'Mar 14, 1988',
			birthplace: 'Akron, USA',
			college: 'Davidson',
			experience: '17',
			status: { label: 'Active', tone: 'muted' }
		},
		{
			id: 'p2',
			name: 'LeBron James',
			photo: homePhoto,
			number: '23',
			position: 'F',
			height: '6-9',
			weight: '250',
			age: '41',
			born: 'Dec 30, 1984',
			birthplace: 'Akron, USA',
			college: null,
			experience: '23',
			status: { label: 'Out', tone: 'out' }
		},
		{
			id: 'p3',
			name: 'Nikola Rookie',
			photo: null,
			number: '21',
			position: 'G',
			height: '6-4',
			weight: null,
			age: '20',
			born: null,
			birthplace: null,
			college: null,
			experience: 'R',
			status: { label: 'Questionable', tone: 'ink' }
		}
	];
	const teamView: TeamView = {
		header: {
			code: 'GSW',
			city: 'Golden State',
			name: 'Warriors',
			conferenceLine: 'Western Conference · Pacific Division',
			colors: { primary: '#1D428A', secondary: '#FFC72C' },
			record: '57–25',
			winPct: '69.5%',
			recordSeason: '2024-25 record',
			cells: [
				{ label: 'Conference', value: '1st West', sub: null },
				{ label: 'Streak', value: 'W3', sub: null },
				{ label: 'Last 10', value: '8–2', sub: null },
				{ label: 'Playoffs', value: '1st seed', sub: null }
			]
		},
		tabs: [
			{ id: 'overview', label: 'Overview' },
			{ id: 'record', label: 'Record' },
			{ id: 'leaders', label: 'Leaders' },
			{ id: 'roster', label: 'Roster' },
			{ id: 'injuries', label: 'Injuries' },
			{ id: 'schedule', label: 'Schedule' }
		],
		mini: 'GSW 57–25',
		sections: {
			overview: {
				arena: { name: 'Chase Center', city: 'San Francisco', photo: highlight1 },
				coach: {
					label: 'Head coach',
					value: 'Steve Kerr',
					sub: '12 seasons as NBA head coach'
				},
				colors: [{ hex: '#1D428A' }, { hex: '#FFC72C' }],
				nextGame: {
					gameId: 'next',
					linked: true,
					tag: 'NBA Cup',
					date: 'Wednesday, October 7',
					opponent: versus('LAL', false),
					place: 'Crypto.com Arena · Los Angeles',
					time: '7:30 PM ET · Network One'
				}
			},
			record: {
				meta: '2025-26 · regular season',
				large: [
					{ label: 'Overall', value: '57–25', sub: '69.5%' },
					{ label: 'Home', value: '32–9', sub: '78.0%' },
					{ label: 'Away', value: '25–16', sub: '61.0%' },
					{ label: 'Last 10', value: '8–2', sub: '80.0%' }
				],
				detail: [
					{ label: 'Streak', value: 'W3', sub: null },
					{ label: 'Games behind', value: '0', sub: null },
					{ label: 'Playoff position', value: '1st seed', sub: null },
					{ label: 'Conference', value: '1st West', sub: null },
					{ label: 'Division', value: '1st Pacific', sub: null },
					{ label: 'Points for', value: '118.3', sub: '9,701' },
					{ label: 'Points against', value: '109.9', sub: '9,012' },
					{ label: 'Differential', value: '+8.4', sub: '+689' }
				]
			},
			leaders: {
				meta: '2025-26 · per game',
				cards: [
					{
						playerId: 'p1',
						label: 'Points',
						value: '27.8',
						name: 'Stephen Curry',
						line: '#30 · Guard',
						photo: awayPhoto
					},
					{
						playerId: 'p4',
						label: 'Rebounds',
						value: '8.9',
						name: 'Draymond Green',
						line: 'Forward',
						photo: null
					},
					{
						playerId: 'p1',
						label: 'Assists',
						value: '7.4',
						name: 'Stephen Curry',
						line: '#30 · Guard',
						photo: homePhoto
					}
				]
			},
			roster: teamRoster,
			injuries: [
				{
					name: 'LeBron James',
					line: '#23 · F',
					status: 'out',
					comment: 'Left ankle sprain, out for two weeks'
				},
				{ name: 'Nikola Rookie', line: '#21 · G', status: 'questionable', comment: null }
			],
			schedule: {
				defaultKey: '2025-11',
				groups: [
					{ key: '2025-10', label: 'Oct', rows: [teamScheduleRow('s1')] },
					{
						key: '2025-11',
						label: 'Nov',
						rows: [
							teamScheduleRow('s2', {
								linked: false,
								opponent: versus('DEN', false),
								outcome: {
									kind: 'played',
									result: 'loss',
									resultLabel: 'L',
									score: '99–104',
									side: 'Away'
								}
							}),
							teamScheduleRow('next', {
								next: true,
								weekday: 'Wed',
								date: 'Nov 5',
								opponent: versus('LAL', false),
								tags: ['NBA Cup', 'Next'],
								outcome: { kind: 'upcoming', time: '7:30 PM ET', broadcast: 'Network One' }
							}),
							teamScheduleRow('s4', {
								linked: false,
								weekday: 'Sat',
								date: 'Nov 8',
								outcome: { kind: 'upcoming', time: '8:00 PM ET', broadcast: null }
							})
						]
					},
					{
						key: 'playoffs',
						label: 'Playoffs',
						rows: [teamScheduleRow('s5', { tags: ['West R1 · G3'] })]
					}
				]
			}
		}
	};
	const teamPartialView: TeamView = {
		...teamView,
		header: {
			...teamView.header,
			cells: [
				{ label: 'Conference', value: '1st West', sub: null },
				{ label: 'Last 10', value: '8–2', sub: null }
			]
		},
		tabs: [
			{ id: 'overview', label: 'Overview' },
			{ id: 'record', label: 'Record' },
			{ id: 'leaders', label: 'Leaders' },
			{ id: 'roster', label: 'Roster' },
			{ id: 'injuries', label: 'Injuries' }
		],
		sections: {
			overview: {
				arena: { name: 'Chase Center', city: null, photo: null },
				coach: null,
				colors: teamView.sections.overview.colors,
				nextGame: null
			},
			record: {
				meta: teamView.sections.record.meta,
				large: teamView.sections.record.large,
				detail: teamView.sections.record.detail.filter(
					(cell) => cell.label !== 'Streak' && cell.label !== 'Playoff position'
				)
			},
			leaders: {
				meta: '2025-26 · per game',
				cards: [teamView.sections.leaders!.cards[0]!]
			},
			roster: teamRoster,
			injuries: [],
			schedule: null
		}
	};
	const teamStates: { title: string; state: TeamPageState; layout: 'desktop' | 'mobile' }[] = [
		{ title: 'TeamPage: full', state: { kind: 'ready', view: teamView }, layout: 'desktop' },
		{
			title: 'TeamPage: partial data',
			state: { kind: 'ready', view: teamPartialView },
			layout: 'desktop'
		},
		{ title: 'TeamPage: mobile', state: { kind: 'ready', view: teamView }, layout: 'mobile' },
		{ title: 'TeamPage: loading', state: { kind: 'loading' }, layout: 'desktop' },
		{ title: 'TeamPage: feed unavailable', state: { kind: 'unavailable' }, layout: 'desktop' },
		{ title: 'TeamPage: unknown team', state: { kind: 'not-found' }, layout: 'desktop' }
	];

	const playerGameHref = () => resolve('/preview');
	const playerRecent = (gameId: string, overrides: Partial<RecentGameRow> = {}): RecentGameRow => ({
		gameId,
		linked: true,
		result: 'win',
		resultLabel: 'W',
		date: 'Apr 29',
		opponent: versus('MEM', false),
		score: '118–104',
		tag: null,
		points: '31',
		line: '8 REB · 6 AST',
		...overrides
	});
	const statCells = (...values: string[]): StatCell[] => values;
	const averageColumns = [
		{ key: 'gp', label: 'GP', muted: true },
		{ key: 'min', label: 'MIN', muted: true },
		{ key: 'fg', label: 'FG%' },
		{ key: 'tp', label: '3P%' },
		{ key: 'ft', label: 'FT%' },
		{ key: 'reb', label: 'REB' },
		{ key: 'ast', label: 'AST' },
		{ key: 'blk', label: 'BLK' },
		{ key: 'stl', label: 'STL' },
		{ key: 'pf', label: 'PF', muted: true },
		{ key: 'tov', label: 'TOV', muted: true },
		{ key: 'pts', label: 'PTS', points: true }
	];
	const seasonColumns = (totals: boolean) => [
		{ key: 'gp', label: 'GP', muted: true },
		{ key: 'gs', label: 'GS', muted: true },
		...(totals ? [] : [{ key: 'min', label: 'MIN', muted: true }]),
		{ key: 'fg', label: 'FG', wide: true },
		{ key: 'fgp', label: 'FG%' },
		{ key: 'tp', label: '3PT', wide: true },
		{ key: 'tpp', label: '3P%' },
		{ key: 'ft', label: 'FT', wide: true },
		{ key: 'ftp', label: 'FT%' },
		{ key: 'oreb', label: 'OREB' },
		{ key: 'dreb', label: 'DREB' },
		{ key: 'reb', label: 'REB' },
		{ key: 'ast', label: 'AST' },
		{ key: 'blk', label: 'BLK' },
		{ key: 'stl', label: 'STL' },
		{ key: 'pf', label: 'PF', muted: true },
		{ key: 'tov', label: 'TOV', muted: true },
		{ key: 'pts', label: 'PTS', points: true }
	];
	const seasonRow = (
		label: string,
		sub: string | null,
		totals: boolean,
		accent = false
	): StatRowView => ({
		key: label,
		label,
		sub,
		accent,
		cells: totals
			? statCells(
					'70',
					'70',
					'650–1,300',
					'50.0%',
					'98–280',
					'35.0%',
					'520–590',
					'88.1%',
					'63',
					'294',
					'357',
					'448',
					'63',
					'119',
					'182',
					'168',
					'1,928'
				)
			: statCells(
					'70',
					'70',
					'34.2',
					'10.1–20.3',
					'49.8%',
					'1.4–4.0',
					'35.0%',
					'7.9–8.8',
					'89.8%',
					'0.9',
					'4.2',
					'5.1',
					'6.4',
					'0.9',
					'1.7',
					'2.6',
					'2.4',
					'31.8'
				)
	});
	const seasonTable = (totals: boolean) => ({
		columns: seasonColumns(totals),
		rows: [
			seasonRow('2025-26', 'OKC', totals),
			seasonRow('2024-25', 'LAC · OKC', totals),
			seasonRow('2018-19', 'LAC', totals),
			seasonRow('Career', null, totals)
		]
	});
	const gameLogColumns = [
		{ key: 'result', label: 'Result', wide: true },
		{ key: 'min', label: 'MIN', muted: true },
		{ key: 'fg', label: 'FG', wide: true },
		{ key: 'fgp', label: 'FG%' },
		{ key: 'tp', label: '3PT', wide: true },
		{ key: 'tpp', label: '3P%' },
		{ key: 'ft', label: 'FT', wide: true },
		{ key: 'ftp', label: 'FT%' },
		{ key: 'reb', label: 'REB' },
		{ key: 'ast', label: 'AST' },
		{ key: 'blk', label: 'BLK' },
		{ key: 'stl', label: 'STL' },
		{ key: 'pf', label: 'PF', muted: true },
		{ key: 'tov', label: 'TOV', muted: true },
		{ key: 'pts', label: 'PTS', points: true }
	];
	const gameLogRows: StatRowView[] = Array.from({ length: 24 }, (_, i) => ({
		key: `log-${i}`,
		label: `Apr ${28 - i} · ${i % 2 ? 'vs' : '@'} MEM`,
		sub: i === 0 ? 'West R1 · G4' : null,
		link: { gameId: `log-${i}`, linked: i % 3 !== 0 },
		cells: [
			{ mark: i % 4 === 3 ? 'L' : 'W', win: i % 4 !== 3, text: '118–104' },
			'34',
			'11–21',
			'52.4%',
			'2–5',
			'40.0%',
			'7–8',
			'87.5%',
			'8',
			'6',
			'1',
			'2',
			'2',
			'3',
			'31'
		]
	}));
	const playerView: PlayerView = {
		header: {
			teamCode: 'OKC',
			status: { label: 'Active', injured: false },
			firstName: 'Shai',
			lastName: 'Gilgeous-Alexander',
			line: '#2 · Guard · Oklahoma City Thunder',
			injury: null,
			photo: homePhoto,
			stats: {
				label: '2025-26 · per game',
				cells: [
					{ label: 'Points', value: '31.8', sub: '1st in NBA' },
					{ label: 'Rebounds', value: '4.9', sub: '41st in NBA' },
					{ label: 'Assists', value: '6.4', sub: '5th in NBA' },
					{ label: 'FG%', value: '47.3%', sub: '12th in NBA' }
				]
			}
		},
		tabs: [
			{ id: 'profile', label: 'Profile' },
			{ id: 'averages', label: 'Averages' },
			{ id: 'seasons', label: 'Seasons' },
			{ id: 'milestones', label: 'Milestones' },
			{ id: 'game-log', label: 'Game log' },
			{ id: 'awards', label: 'Awards' }
		],
		mini: '#2 S. Gilgeous-Alexander',
		sections: {
			profile: {
				cells: [
					{ label: 'Height', value: '6\'6"', sub: '198 cm' },
					{ label: 'Weight', value: '195 lb', sub: '88 kg' },
					{ label: 'Born', value: 'July 12, 1998', sub: 'Age 28' },
					{ label: 'Birthplace', value: 'Hamilton, Ontario', sub: 'Canada' },
					{ label: 'College', value: 'Kentucky', sub: null },
					{ label: 'Draft', value: '2018 · Round 1 · Pick 11', sub: 'Charlotte Hornets' },
					{ label: 'Seasons', value: '8', sub: 'Debut 2018-19' }
				],
				nextGame: {
					gameId: 'next',
					linked: true,
					tag: null,
					date: 'Wednesday, October 7',
					opponent: versus('DEN'),
					place: 'Paycom Center · Oklahoma City, OK',
					time: '7:30 PM ET · Courtside TV'
				},
				live: null,
				recent: [
					playerRecent('r1', { tag: 'West R1 · G4' }),
					playerRecent('r2', {
						result: 'loss',
						resultLabel: 'L',
						opponent: versus('MEM'),
						score: '101–108',
						points: '24',
						linked: false
					}),
					playerRecent('r3', { date: 'Apr 12', opponent: versus('DEN'), points: '35' }),
					playerRecent('r4', { date: 'Apr 10', opponent: versus('HOU', false), linked: false }),
					playerRecent('r5', {
						date: 'Apr 8',
						result: 'loss',
						resultLabel: 'L',
						tag: 'NBA Cup',
						linked: false
					})
				]
			},
			averages: {
				columns: averageColumns,
				rows: [
					{
						key: 'regular',
						label: 'Regular season',
						sub: '2025-26',
						cells: statCells(
							'70',
							'34.2',
							'47.3%',
							'35.0%',
							'89.8%',
							'4.9',
							'6.4',
							'0.9',
							'1.7',
							'2.6',
							'2.4',
							'31.8'
						)
					},
					{
						key: 'playoffs',
						label: 'Playoffs',
						sub: '2025-26',
						cells: averageColumns.map(() => '—')
					},
					{
						key: 'career',
						label: 'Career',
						sub: null,
						accent: true,
						cells: statCells(
							'480',
							'33.5',
							'49.0%',
							'36.0%',
							'88.0%',
							'4.9',
							'5.0',
							'0.8',
							'1.6',
							'2.7',
							'2.6',
							'24.6'
						)
					}
				]
			},
			seasons: {
				regular: { perGame: seasonTable(false), totals: seasonTable(true) },
				playoffs: { perGame: seasonTable(false), totals: seasonTable(true) }
			},
			milestones: {
				meta: '2025-26',
				cells: [
					{ label: 'Double-doubles', value: '12', sub: 'Career 75' },
					{ label: 'Triple-doubles', value: '1', sub: 'Career 4' },
					{ label: 'Disqualifications', value: '0', sub: 'Career 1' },
					{ label: 'Ejections', value: '0', sub: 'Career 1' },
					{ label: 'Technical fouls', value: '3', sub: 'Career 14' },
					{ label: 'Flagrant fouls', value: '0', sub: 'Career 1' },
					{ label: 'AST/TO', value: '2.67', sub: 'Career 1.92' },
					{ label: 'STL/TO', value: '0.71', sub: 'Career 0.62' }
				]
			},
			gameLog: {
				meta: '2025-26',
				columns: gameLogColumns,
				filters: [
					{ id: 'all', label: 'All', rows: gameLogRows },
					{ id: 'regular', label: 'Regular season', rows: gameLogRows.slice(0, 12) },
					{ id: 'playoffs', label: 'Playoffs', rows: gameLogRows.slice(0, 4) }
				]
			},
			awards: [
				{ count: '2×', name: 'NBA Most Valuable Player', seasons: '2024-25 · 2025-26' },
				{ count: '3×', name: 'All-NBA First Team', seasons: '2022-23 · 2023-24 · 2024-25' }
			]
		}
	};
	const playerLine = [
		{ label: 'MIN', value: '24:10', sub: null },
		{ label: 'PTS', value: '14', sub: null },
		{ label: 'REB', value: '4', sub: null },
		{ label: 'AST', value: '5', sub: null },
		{ label: 'FG', value: '7–15', sub: null }
	];
	const playerLive = (line: typeof playerLine | null): PlayerView => ({
		...playerView,
		sections: {
			...playerView.sections,
			profile: {
				...playerView.sections.profile,
				live: {
					gameId: 'live',
					opponent: versus('DEN', false),
					score: '78–74',
					clock: 'Q3 · 4:12',
					line
				}
			}
		}
	});
	const playerPartialView: PlayerView = {
		...playerView,
		header: { ...playerView.header, photo: null, stats: null },
		tabs: [
			{ id: 'profile', label: 'Profile' },
			{ id: 'averages', label: 'Averages' }
		],
		sections: {
			profile: {
				cells: playerView.sections.profile.cells.slice(0, 3),
				nextGame: null,
				live: null,
				recent: []
			},
			averages: playerView.sections.averages,
			seasons: null,
			milestones: null,
			gameLog: null,
			awards: null
		}
	};
	const playerStates: { title: string; state: PlayerPageState; layout: 'desktop' | 'mobile' }[] = [
		{ title: 'PlayerPage: full', state: { kind: 'ready', view: playerView }, layout: 'desktop' },
		{
			title: "PlayerPage: live, with the player's line",
			state: { kind: 'ready', view: playerLive(playerLine) },
			layout: 'desktop'
		},
		{
			title: 'PlayerPage: live, not in the game yet',
			state: { kind: 'ready', view: playerLive(null) },
			layout: 'desktop'
		},
		{
			title: 'PlayerPage: partial data',
			state: { kind: 'ready', view: playerPartialView },
			layout: 'desktop'
		},
		{ title: 'PlayerPage: mobile', state: { kind: 'ready', view: playerView }, layout: 'mobile' },
		{ title: 'PlayerPage: loading', state: { kind: 'loading' }, layout: 'desktop' },
		{ title: 'PlayerPage: feed unavailable', state: { kind: 'unavailable' }, layout: 'desktop' },
		{ title: 'PlayerPage: unknown player', state: { kind: 'not-found' }, layout: 'desktop' }
	];
</script>

<main>
	<h1>Component preview</h1>

	<section>
		<h2>BlueprintFrame</h2>
		<BlueprintFrame>
			<p>Sample content inside the frame.</p>
		</BlueprintFrame>
	</section>

	<section>
		<h2>Button</h2>
		<div class="row">
			<Button variant="primary" label="Primary action" onclick={() => {}} />
			<Button variant="secondary" label="Secondary link" href={resolve('/')} />
		</div>
	</section>

	<section>
		<h2>LiveBadge</h2>
		<LiveBadge />
	</section>

	<section>
		<h2>StatusTag</h2>
		<div class="row">
			<StatusTag status="tonight" />
			<StatusTag status="live" />
			<StatusTag status="final" />
			<StatusTag status="delayed" />
			<StatusTag status="postponed" />
			<StatusTag status="canceled" />
		</div>
	</section>

	<section>
		<h2>Kicker</h2>
		<Kicker text="10:30 PM ET · Chase Center" />
	</section>

	<section>
		<h2>TeamMonogram</h2>
		<div class="row">
			<TeamMonogram code="GSW" size="large" />
			<TeamMonogram code="GSW" size="small" />
		</div>
	</section>

	{#each heroStates as state (state.status)}
		<section>
			<h2>{state.title}</h2>
			<Hero
				{teamHref}
				games={[heroGame(state.status, state.status)]}
				{today}
				scheduleHref={resolve('/')}
				{standingsHref}
				layout="desktop"
				onMatchDetails={() => {}}
				spoilerFree={spoilerFree.on}
				onSpoilerFreeToggle={() => spoilerFree.toggle()}
			/>
		</section>
	{/each}

	<section>
		<h2>Hero: three games</h2>
		<Hero
			{teamHref}
			games={heroGames}
			{today}
			scheduleHref={resolve('/')}
			{standingsHref}
			layout="desktop"
			onMatchDetails={() => {}}
			spoilerFree={spoilerFree.on}
			onSpoilerFreeToggle={() => spoilerFree.toggle()}
		/>
	</section>

	<section>
		<h2>DayStrip</h2>
		<div class="stack">
			<DayStrip
				days={stripDays}
				selected={desktopSelected}
				compact={false}
				onSelect={(i) => (desktopSelected = i)}
			/>
			<DayStrip
				days={stripDays}
				selected={compactSelected}
				compact={true}
				onSelect={(i) => (compactSelected = i)}
			/>
		</div>
	</section>

	<section>
		<h2>GameCard: desktop row</h2>
		<div class="stack">
			{#each sampleGames as game (game.id)}
				<GameCard {teamHref} {game} layout="desktop" />
			{/each}
			{#each statusGames as game (game.id)}
				<GameCard {teamHref} {game} layout="desktop" />
			{/each}
		</div>
	</section>

	<section>
		<h2>GameCard: mobile row</h2>
		<div class="stack phone">
			{#each sampleGames as game (game.id)}
				<GameCard {teamHref} {game} layout="mobile" />
			{/each}
			{#each statusGames as game (game.id)}
				<GameCard {teamHref} {game} layout="mobile" />
			{/each}
		</div>
	</section>

	<section>
		<h2>GameCard: spoiler-free</h2>
		<div class="stack">
			<GameCard
				{teamHref}
				game={sampleGames[2]}
				layout="desktop"
				spoilerFree
				open={spoilerOpen === 'desktop'}
				onToggle={() => (spoilerOpen = spoilerOpen === 'desktop' ? null : 'desktop')}
			/>
		</div>
		<div class="stack phone">
			<GameCard
				{teamHref}
				game={sampleGames[2]}
				layout="mobile"
				spoilerFree
				open={spoilerOpen === 'mobile'}
				onToggle={() => (spoilerOpen = spoilerOpen === 'mobile' ? null : 'mobile')}
			/>
		</div>
	</section>

	{#each expandedGames as expanded (expanded.title)}
		<section>
			<h2>{expanded.title}</h2>
			<GameCard
				{teamHref}
				game={expanded.game}
				layout="desktop"
				open
				detailHref={resolve('/preview')}
				playingVideoId={previewPlaying}
				onPlay={(id) => (previewPlaying = id)}
			/>
		</section>
	{/each}

	<section>
		<h2>Schedule</h2>
		<Schedule
			{teamHref}
			days={sampleDays}
			updatedMinutesAgo={3}
			spoilerFree={spoilerFree.on}
			gameHref={() => resolve('/preview')}
		/>
	</section>

	<section>
		<h2>Schedule: day with no games</h2>
		<Schedule
			{teamHref}
			days={sampleDays}
			updatedMinutesAgo={3}
			selected={1}
			gameHref={() => resolve('/preview')}
		/>
	</section>

	<section>
		<h2>Schedule: recently updated</h2>
		<Schedule
			{teamHref}
			days={sampleDays}
			updatedMinutesAgo={0}
			gameHref={() => resolve('/preview')}
		/>
	</section>

	{#each headerStates as { title, header } (title)}
		<section>
			<h2>{title}</h2>
			<GameHeader {teamHref} {header} {allGamesHref} {standingsHref} layout="desktop" />
		</section>
	{/each}

	<section>
		<h2>GameHeader: mobile</h2>
		<div class="stack phone">
			{#each mobileHeaders as header (header.layout)}
				<GameHeader {teamHref} {header} {allGamesHref} {standingsHref} layout="mobile" />
			{/each}
		</div>
	</section>

	<section>
		<h2>TeamMark: a guest without a code</h2>
		<TeamMark part="tile" team={guestMariners} size="large" />
		<TeamMark part="tile" team={guestMariners} size="small" />
		<TeamMark part="name" team={guestMariners} />
		<TeamMark part="label" team={guestMariners} versus="away" />
	</section>

	<section>
		<h2>GameHeader: no venue photo</h2>
		<GameHeader {teamHref} header={noPhotoHeader} {allGamesHref} {standingsHref} layout="desktop" />
	</section>

	{#each tabStates as { title, tabs, miniScore } (title)}
		<section>
			<h2>{title}</h2>
			<SectionTabs {tabs} {miniScore} />
		</section>
	{/each}

	<section>
		<h2>GamePage: loading</h2>
		<GamePage
			{teamHref}
			{playerHref}
			state={{ kind: 'loading' }}
			{allGamesHref}
			{standingsHref}
			layout="desktop"
		/>
	</section>

	<section>
		<h2>GamePage: feed unavailable</h2>
		<GamePage
			{teamHref}
			{playerHref}
			state={{ kind: 'unavailable' }}
			{allGamesHref}
			{standingsHref}
			layout="desktop"
		/>
	</section>

	<section>
		<h2>GamePage: unknown game</h2>
		<GamePage
			{teamHref}
			{playerHref}
			state={{ kind: 'not-found' }}
			{allGamesHref}
			{standingsHref}
			layout="desktop"
		/>
	</section>

	<section>
		<h2>GamePage: postponed</h2>
		<GamePage
			{teamHref}
			{playerHref}
			state={{ kind: 'ready', view: postponedView }}
			{allGamesHref}
			{standingsHref}
			layout="desktop"
		/>
	</section>

	{#each sectionViews as { title, view } (title)}
		<section>
			<h2>{title}</h2>
			<GamePage
				{teamHref}
				{playerHref}
				state={{ kind: 'ready', view }}
				{allGamesHref}
				{standingsHref}
				layout="desktop"
			/>
		</section>
	{/each}

	<section>
		<h2>GameVideos: mobile</h2>
		<div class="stack phone">
			<GameVideos videos={sampleVideos} layout="mobile" />
		</div>
	</section>

	<section>
		<h2>SeasonSeries: first meeting</h2>
		<SeasonSeries series={firstMeetingSeries} />
	</section>

	{#each teamStates as { title, state, layout } (title)}
		<section>
			<h2>{title}</h2>
			<TeamPage
				{state}
				{allGamesHref}
				{standingsHref}
				{layout}
				gameHref={teamGameHref}
				playerHref={() => resolve('/preview')}
			/>
		</section>
	{/each}

	{#each playerStates as { title, state, layout } (title)}
		<section>
			<h2>{title}</h2>
			<PlayerPage {state} {allGamesHref} {standingsHref} {layout} gameHref={playerGameHref} />
		</section>
	{/each}

	<section>
		<h2>SiteFooter</h2>
		<SiteFooter />
	</section>
</main>

<style>
	main {
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
	}

	section {
		margin-block: var(--panel-section-gap);
	}

	.stack {
		display: grid;
		gap: var(--game-list-gap);
	}

	.phone {
		max-width: var(--hero-column-min);
	}

	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}
</style>
