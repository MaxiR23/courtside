<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import LiveBadge from '#lib/components/LiveBadge.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { CupGameRowView, CupSideView } from '#lib/cup/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		game: CupGameRowView;
		layout: RowLayout;
		gameHref: (id: string) => ResolvedPathname;
	};

	let { game, layout, gameHref }: Props = $props();
</script>

{#snippet side(view: CupSideView)}
	<span class="side" class:loser={view.loser}>
		<span class="code"><TeamMark team={view.team} part="label" /></span>
		{#if view.score !== null}<span class="score">{view.score}</span>{/if}
	</span>
{/snippet}

{#snippet body()}
	<span class="stage">{game.stageLabel}</span>
	<span class="matchup">
		{@render side(game.away)}
		<span class="at">{m.hero_at()}</span>
		{@render side(game.home)}
	</span>
	<span class="status">
		{#if game.status.kind === 'time'}
			<span class="time">{game.status.text}</span>
		{:else if game.status.kind === 'live'}
			<LiveBadge />
		{:else}
			<StatusTag status={game.status.status} />
		{/if}
		{#if game.broadcast}<span class="broadcast">{game.broadcast}</span>{/if}
		{#if game.notCounted}<StatusTag text={m.cup_not_counted()} accent />{/if}
	</span>
{/snippet}

{#if game.linked}
	<a class="cup-game-row link" class:mobile={layout === 'mobile'} href={gameHref(game.gameId)}>
		{@render body()}
	</a>
{:else}
	<div class="cup-game-row" class:mobile={layout === 'mobile'}>
		{@render body()}
	</div>
{/if}

<style>
	.cup-game-row {
		display: grid;
		grid-template-columns: var(--schedule-date-column) 1fr auto;
		align-items: center;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
		border-bottom: var(--hairline) solid var(--color-row-rule);
		color: inherit;
		text-decoration: none;
	}

	.cup-game-row.mobile {
		grid-template-columns: 1fr;
	}

	.link:hover {
		background: var(--box-row-hover);
	}

	.stage {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.matchup {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	.side {
		display: inline-flex;
		align-items: center;
		gap: var(--day-strip-gap);
	}

	.loser {
		opacity: var(--dimmed-opacity);
	}

	.code,
	.score {
		font-family: var(--font-heading);
		font-size: var(--injury-name-size);
	}

	.score {
		font-variant-numeric: tabular-nums;
	}

	.at {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.status {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
		gap: var(--day-strip-gap);
		text-align: right;
	}

	.cup-game-row.mobile .status {
		justify-content: flex-start;
		text-align: left;
	}

	.time {
		font-family: var(--font-heading);
		font-size: var(--body-size);
		white-space: nowrap;
	}

	.broadcast {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}
</style>
