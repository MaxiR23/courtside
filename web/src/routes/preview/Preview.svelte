<script lang="ts">
	import { resolve } from '$app/paths';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Button from '#lib/components/Button.svelte';
	import DayStrip from '#lib/components/DayStrip.svelte';
	import GameCard from '#lib/components/GameCard.svelte';
	import Hero from '#lib/components/Hero.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import LiveBadge from '#lib/components/LiveBadge.svelte';
	import Schedule from '#lib/components/Schedule.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
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
	const pendingHighlights: GameHighlights = { ...sampleHighlights, videos: [] };
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
				playingVideoId={previewPlaying}
				onPlay={(id) => (previewPlaying = id)}
			/>
		</section>
	{/each}

	<section>
		<h2>Schedule</h2>
		<Schedule days={sampleDays} updatedMinutesAgo={3} spoilerFree={spoilerFree.on} />
	</section>

	<section>
		<h2>Schedule: day with no games</h2>
		<Schedule days={sampleDays} updatedMinutesAgo={3} selected={1} />
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
