<script lang="ts">
	import { resolve } from '$app/paths';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Button from '#lib/components/Button.svelte';
	import Hero from '#lib/components/Hero.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import LiveBadge from '#lib/components/LiveBadge.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
	import type { HeroPlayer } from '#lib/hero/types.ts';
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

	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}
</style>
