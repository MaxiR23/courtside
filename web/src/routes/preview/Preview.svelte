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
	import type { HeroPlayer } from '#lib/hero/types.ts';
	import type { ScheduleDay, ScheduleGame } from '#lib/schedule/types.ts';
	import awayPhoto from './player-away.svg';
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

	const warriors = { code: 'GSW', name: 'Warriors', city: 'Golden State' };
	const lakers = { code: 'LAL', name: 'Lakers', city: 'Los Angeles' };
	const celtics = { code: 'BOS', name: 'Celtics', city: 'Boston' };
	const knicks = { code: 'NYK', name: 'Knicks', city: 'New York' };
	const nuggets = { code: 'DEN', name: 'Nuggets', city: 'Denver' };
	const suns = { code: 'PHX', name: 'Suns', city: 'Phoenix' };
	const sampleGames: ScheduleGame[] = [
		{
			id: 'scheduled',
			away: warriors,
			home: lakers,
			status: { state: 'scheduled', tipTime: '9:00', tipSuffix: 'PM ET', network: 'Prime Video' }
		},
		{
			id: 'live',
			away: celtics,
			home: knicks,
			status: { state: 'live', period: 'Q3', clock: '4:12', awayScore: 78, homeScore: 74 }
		},
		{
			id: 'final',
			away: nuggets,
			home: suns,
			status: { state: 'final', awayScore: 112, homeScore: 104 }
		}
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
				status={state.status}
				tipTime="10:30 PM ET"
				arena="Chase Center"
				away={{ name: 'Warriors', star: away }}
				home={{ name: 'Lakers', star: home }}
				{today}
				scheduleHref={resolve('/')}
				onMatchDetails={() => {}}
			/>
		</section>
	{/each}

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
		</div>
	</section>

	<section>
		<h2>GameCard: mobile row</h2>
		<div class="stack phone">
			{#each sampleGames as game (game.id)}
				<GameCard {game} layout="mobile" />
			{/each}
		</div>
	</section>

	<section>
		<h2>Schedule</h2>
		<Schedule days={sampleDays} updatedMinutesAgo={3} />
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
