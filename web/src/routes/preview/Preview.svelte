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
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
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
	import { SpoilerFree } from '#lib/schedule/spoiler-free.svelte.ts';
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
	const allGamesHref = resolve('/');
	const headerAway: HeaderTeam = {
		code: 'GSW',
		name: 'Warriors',
		city: 'Golden State',
		record: '12–5'
	};
	const headerHome: HeaderTeam = {
		code: 'LAL',
		name: 'Lakers',
		city: 'Los Angeles',
		record: '10–7'
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
	const miniScore = { awayCode: 'GSW', away: 63, home: 62, homeCode: 'LAL' };
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
			miniScore
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
		away: { name: 'Warriors', star: away },
		home: { name: 'Lakers', star: home }
	});
	const heroGames: HeroGame[] = [
		heroGame('one', 'tonight'),
		heroGame('two', 'live'),
		heroGame('three', 'final')
	];

	const warriors = { code: 'GSW', name: 'Warriors', city: 'Golden State' };
	const lakers = { code: 'LAL', name: 'Lakers', city: 'Los Angeles' };
	const celtics = { code: 'BOS', name: 'Celtics', city: 'Boston' };
	const knicks = { code: 'NYK', name: 'Knicks', city: 'New York' };
	const nuggets = { code: 'DEN', name: 'Nuggets', city: 'Denver' };
	const suns = { code: 'PHX', name: 'Suns', city: 'Phoenix' };
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
		...player,
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
		code: team.code,
		name: team.name,
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
	const boxTeam = (team: HeaderTeam, names: string[]): BoxScoreTeam => ({
		code: team.code,
		name: team.name,
		starters: names
			.slice(0, 2)
			.map((name, i) => boxRow(`${team.code}-s${i}`, name, i ? '-3' : '+4')),
		bench: names.slice(2).map((name, i) => boxRow(`${team.code}-b${i}`, name, '0')),
		totals: {
			points: '112',
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
	const sampleBox: BoxScoreSection = {
		away: boxTeam(headerAway, ['Stephen Curry', 'Draymond Green', 'Jonathan Kuminga']),
		home: boxTeam(headerHome, ['LeBron James', 'Anthony Davis', 'Austin Reaves'])
	};
	const curve = (seconds: number[]) =>
		seconds.map((elapsedSeconds, i) => ({
			elapsedSeconds,
			homeWinProbability: 0.5 + 0.18 * Math.sin(i / 2)
		}));
	const sampleChart: WinProbabilitySection = {
		awayCode: headerAway.code,
		homeCode: headerHome.code,
		middle: '50%',
		meta: 'LAL 68%',
		points: curve([300, 600, 900, 1200, 1500, 1800, 2100])
	};
	const samplePlayers: PlayersSection = {
		away: { ...away, teamName: 'Golden State Warriors', photo: awayPhoto },
		home: { ...home, teamName: 'Los Angeles Lakers', photo: homePhoto }
	};
	const sampleInjuries: InjuriesSection = {
		away: {
			code: headerAway.code,
			name: headerAway.name,
			injuries: [
				{ name: 'Draymond Green', status: 'out', comment: 'Left knee soreness, out for the game.' },
				{ name: 'Jonathan Kuminga', status: 'doubtful', comment: null },
				{ name: 'Brandin Podziemski', status: 'questionable', comment: null }
			]
		},
		home: {
			code: headerHome.code,
			name: headerHome.name,
			injuries: []
		}
	};
	const sampleInjuriesBoth: InjuriesSection = {
		...sampleInjuries,
		home: {
			...sampleInjuries.home,
			injuries: [
				{ name: 'Gabe Vincent', status: 'probable', comment: null },
				{ name: 'Rui Hachimura', status: 'day-to-day', comment: 'Ankle sprain.' }
			]
		}
	};
	const sampleLastGames: LastGamesSection = {
		away: {
			code: headerAway.code,
			name: headerAway.name,
			strip: [
				{ result: 'loss', label: 'L' },
				{ result: 'win', label: 'W' },
				{ result: 'win', label: 'W' },
				{ result: 'loss', label: 'L' },
				{ result: 'win', label: 'W' }
			],
			rows: [
				{ result: 'win', resultLabel: 'W', date: 'Oct 5', opponent: 'vs DEN', score: '118–104' },
				{ result: 'loss', resultLabel: 'L', date: 'Oct 3', opponent: '@ PHX', score: '99–107' },
				{ result: 'win', resultLabel: 'W', date: 'Oct 1', opponent: 'vs SAC', score: '121–110' },
				{ result: 'win', resultLabel: 'W', date: 'Sep 29', opponent: '@ LAC', score: '112–109' },
				{ result: 'loss', resultLabel: 'L', date: 'Sep 27', opponent: 'vs DAL', score: '101–113' }
			]
		},
		home: {
			code: headerHome.code,
			name: headerHome.name,
			strip: [
				{ result: 'win', label: 'W' },
				{ result: 'loss', label: 'L' }
			],
			rows: [
				{ result: 'loss', resultLabel: 'L', date: 'Oct 4', opponent: '@ OKC', score: '98–110' },
				{ result: 'win', resultLabel: 'W', date: 'Oct 2', opponent: 'vs MIA', score: '115–101' }
			]
		}
	};
	const sampleStandings: StandingsSection = {
		away: {
			code: headerAway.code,
			name: headerAway.name,
			conference: '3rd West',
			record: '12–5',
			home: '7–2',
			away: '5–3',
			lastTen: '7–3'
		},
		home: {
			code: headerHome.code,
			name: headerHome.name,
			conference: '1st West',
			record: '14–3',
			home: '8–1',
			away: '6–2',
			lastTen: '8–2'
		}
	};
	const sampleSeries: SeasonSeriesSection = {
		summary: 'GSW lead 2–1',
		meta: '3 of 4 games played',
		games: [
			{
				date: 'Jan 10',
				awayCode: 'GSW',
				awayPoints: 118,
				homePoints: 112,
				homeCode: 'LAL',
				arena: 'Chase Center'
			},
			{
				date: 'Dec 2',
				awayCode: 'LAL',
				awayPoints: 121,
				homePoints: 109,
				homeCode: 'GSW',
				arena: 'Crypto.com Arena'
			},
			{
				date: 'Nov 14',
				awayCode: 'GSW',
				awayPoints: 104,
				homePoints: 99,
				homeCode: 'LAL',
				arena: 'Chase Center'
			}
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
		seasonSeries: sampleSeries
	};
	const liveSections: GameSections = {
		...noSections,
		score: detailScore(
			lineScoreTeam(headerAway, [28, 25, 10], 63),
			lineScoreTeam(headerHome, [26, 24, 12], 62)
		),
		winProbability: sampleChart,
		boxScore: sampleBox,
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
			points: curve([0, 480, 960, 1440, 1920, 2400, 2880])
		},
		boxScore: sampleBox,
		injuries: sampleInjuriesBoth,
		seasonSeries: sampleSeries,
		videos: sampleVideos
	};
	const overtimeSections: GameSections = {
		...finalSections,
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
			points: curve([0, 720, 1440, 2160, 2880, 3180, 3480])
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
				miniScore,
				sections: finalSections
			}
		},
		{
			title: 'GamePage: overtime sections',
			view: {
				header: finalHeader,
				tabs: tabs(
					['score', 'Score'],
					['win-probability', 'Win prob.'],
					['box-score', 'Box score']
				),
				miniScore,
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
			status: { state: 'scheduled', tipTime: '9:00', tipSuffix: 'PM ET', network: 'Prime Video' },
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
			status: { state: 'final', awayScore: 112, homeScore: 104, winner: 'DEN' },
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
		status: { state: 'final', awayScore: 132, homeScore: 130, winner: 'BOS' },
		details: played({ away: [28, 25, 30, 27, 12, 10], home: [30, 26, 24, 30, 12, 8] }, 'BOS', 'NYK')
	};
	const singleHighlightGame: ScheduleGame = {
		id: 'single-highlight',
		away: nuggets,
		home: suns,
		status: { state: 'final', awayScore: 112, homeScore: 104, winner: 'DEN' },
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
		status: { state: 'final', awayScore: 112, homeScore: 104, winner: 'DEN' },
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
				games={[heroGame(state.status, state.status)]}
				{today}
				scheduleHref={resolve('/')}
				onMatchDetails={() => {}}
				spoilerFree={spoilerFree.on}
				onSpoilerFreeToggle={() => spoilerFree.toggle()}
			/>
		</section>
	{/each}

	<section>
		<h2>Hero: three games</h2>
		<Hero
			games={heroGames}
			{today}
			scheduleHref={resolve('/')}
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
				<GameCard {game} layout="desktop" />
			{/each}
			{#each statusGames as game (game.id)}
				<GameCard {game} layout="desktop" />
			{/each}
		</div>
	</section>

	<section>
		<h2>GameCard: mobile row</h2>
		<div class="stack phone">
			{#each sampleGames as game (game.id)}
				<GameCard {game} layout="mobile" />
			{/each}
			{#each statusGames as game (game.id)}
				<GameCard {game} layout="mobile" />
			{/each}
		</div>
	</section>

	<section>
		<h2>GameCard: spoiler-free</h2>
		<div class="stack">
			<GameCard
				game={sampleGames[2]}
				layout="desktop"
				spoilerFree
				open={spoilerOpen === 'desktop'}
				onToggle={() => (spoilerOpen = spoilerOpen === 'desktop' ? null : 'desktop')}
			/>
		</div>
		<div class="stack phone">
			<GameCard
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
			days={sampleDays}
			updatedMinutesAgo={3}
			spoilerFree={spoilerFree.on}
			gameHref={() => resolve('/preview')}
		/>
	</section>

	<section>
		<h2>Schedule: day with no games</h2>
		<Schedule
			days={sampleDays}
			updatedMinutesAgo={3}
			selected={1}
			gameHref={() => resolve('/preview')}
		/>
	</section>

	{#each headerStates as { title, header } (title)}
		<section>
			<h2>{title}</h2>
			<GameHeader {header} {allGamesHref} layout="desktop" />
		</section>
	{/each}

	<section>
		<h2>GameHeader: mobile</h2>
		<div class="stack phone">
			{#each mobileHeaders as header (header.layout)}
				<GameHeader {header} {allGamesHref} layout="mobile" />
			{/each}
		</div>
	</section>

	<section>
		<h2>GameHeader: no venue photo</h2>
		<GameHeader header={noPhotoHeader} {allGamesHref} layout="desktop" />
	</section>

	{#each tabStates as { title, tabs, miniScore } (title)}
		<section>
			<h2>{title}</h2>
			<SectionTabs {tabs} {miniScore} />
		</section>
	{/each}

	<section>
		<h2>GamePage: loading</h2>
		<GamePage state={{ kind: 'loading' }} {allGamesHref} layout="desktop" />
	</section>

	<section>
		<h2>GamePage: feed unavailable</h2>
		<GamePage state={{ kind: 'unavailable' }} {allGamesHref} layout="desktop" />
	</section>

	<section>
		<h2>GamePage: unknown game</h2>
		<GamePage state={{ kind: 'not-found' }} {allGamesHref} layout="desktop" />
	</section>

	<section>
		<h2>GamePage: postponed</h2>
		<GamePage state={{ kind: 'ready', view: postponedView }} {allGamesHref} layout="desktop" />
	</section>

	{#each sectionViews as { title, view } (title)}
		<section>
			<h2>{title}</h2>
			<GamePage state={{ kind: 'ready', view }} {allGamesHref} layout="desktop" />
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
