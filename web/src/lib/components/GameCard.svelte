<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import LiveBadge from '#lib/components/LiveBadge.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout, ScheduleGame } from '#lib/schedule/types.ts';

	type Props = { game: ScheduleGame; layout: RowLayout };

	let { game, layout }: Props = $props();

	// Display choice: dims the lower score of a final game. Not a game rule.
	const loser = $derived.by(() => {
		const status = game.status;
		if (status.state !== 'final') return null;
		if (status.awayScore < status.homeScore) return 'away';
		if (status.awayScore > status.homeScore) return 'home';
		return null;
	});
	const entries = $derived([
		{ team: game.away, side: 'away' as const },
		{ team: game.home, side: 'home' as const }
	]);
	const scores = $derived(
		game.status.state === 'scheduled'
			? null
			: { away: game.status.awayScore, home: game.status.homeScore }
	);
</script>

{#snippet statusLine()}
	{@const status = game.status}
	<span class="status-line">
		{#if status.state === 'final'}
			{m.status_final()}
		{:else if status.state === 'live'}
			<LiveBadge /> {status.period} · {status.clock}
		{:else if layout === 'desktop'}
			{status.network}
		{:else}
			{status.tipTime} {status.tipSuffix} · {status.network}
		{/if}
	</span>
{/snippet}

{#snippet chevron()}
	<svg class="chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
{/snippet}

<BlueprintFrame>
	{#if layout === 'desktop'}
		<div class="row desktop">
			<div class="team away" class:dimmed={loser === 'away'}>
				<TeamMonogram code={game.away.code} size="large" />
				<span class="names">
					<span class="name">{game.away.name}</span>
					<span class="city">{game.away.city}</span>
				</span>
			</div>
			<div class="center">
				{@render statusLine()}
				{#if scores}
					<span class="scores">
						<span class="score" class:dimmed={loser === 'away'}>{scores.away}</span>
						<span class="score" class:dimmed={loser === 'home'}>{scores.home}</span>
					</span>
				{:else if game.status.state === 'scheduled'}
					<span class="tip-time">
						{game.status.tipTime}<span class="suffix">{game.status.tipSuffix}</span>
					</span>
				{/if}
			</div>
			<div class="team home" class:dimmed={loser === 'home'}>
				<span class="names">
					<span class="name">{game.home.name}</span>
					<span class="city">{game.home.city}</span>
				</span>
				<TeamMonogram code={game.home.code} size="large" />
			</div>
			{@render chevron()}
		</div>
	{:else}
		<div class="row mobile">
			<div class="mobile-head">
				{@render statusLine()}
				{@render chevron()}
			</div>
			{#each entries as entry (entry.side)}
				<div class="mobile-team">
					<TeamMonogram code={entry.team.code} size="small" />
					<span class="names" class:dimmed={loser === entry.side}>
						<span class="name">{entry.team.name}</span>
						<span class="city">{entry.team.city}</span>
					</span>
					{#if scores}
						<span class="score" class:dimmed={loser === entry.side}>{scores[entry.side]}</span>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</BlueprintFrame>

<style>
	.row {
		padding: var(--game-list-gap);
		gap: var(--game-list-gap);
	}

	.desktop {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) var(--chevron-size);
		align-items: center;
	}

	.mobile {
		display: grid;
	}

	.team {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.home {
		justify-content: flex-end;
		text-align: right;
	}

	.names {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.name {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--team-name-size);
		text-transform: uppercase;
		overflow-wrap: anywhere;
	}

	.city {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.center {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--day-strip-gap);
	}

	.status-line {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.scores {
		display: flex;
		gap: var(--game-list-gap);
	}

	.score {
		font-family: var(--font-heading);
		font-size: var(--score-size);
		font-variant-numeric: tabular-nums;
	}

	.tip-time {
		font-family: var(--font-heading);
		font-size: var(--tip-time-size);
	}

	.suffix {
		font-size: var(--tip-time-suffix-size);
		color: var(--color-muted);
	}

	.dimmed {
		opacity: var(--dimmed-opacity);
	}

	.mobile-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.mobile-team {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.mobile-team .names {
		flex: 1;
	}

	.mobile-team .name {
		font-size: var(--team-name-size-mobile);
	}

	.mobile-team .score {
		font-size: var(--score-size-mobile);
		text-align: right;
	}

	.chevron {
		width: var(--chevron-size);
		height: var(--chevron-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
