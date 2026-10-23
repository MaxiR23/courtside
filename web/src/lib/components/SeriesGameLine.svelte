<script lang="ts">
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { SeriesGameRowView } from '#lib/playoffs/types.ts';

	type Props = { game: SeriesGameRowView };

	let { game }: Props = $props();
</script>

<span class="cell">
	<span class="head">
		<span class="number">{game.number}</span>
		<span class="at">{game.at}</span>
		{#if game.overtimeTag}<span class="overtime">{game.overtimeTag}</span>{/if}
	</span>
	{#if game.winner}
		<span class="result">
			<span class="mark">
				<TeamMark team={game.winner.team} part="tile" size="fill" logo={game.winner.team.logo} />
			</span>
			<span class="score">{game.winner.code} {game.winner.score}</span>
		</span>
		<span class="rule" style:--side-accent={game.accent ?? 'var(--identity-neutral-accent)'}></span>
	{:else if game.when}
		<span class="when">{game.when}</span>
	{/if}
</span>

<style>
	.cell {
		position: relative;
		display: grid;
		gap: var(--day-strip-gap);
		box-sizing: border-box;
		min-width: 0;
		width: 100%;
		padding: var(--game-list-gap);
		font-variant-numeric: tabular-nums;
		line-height: 1;
		text-align: left;
	}

	.head {
		display: flex;
		align-items: baseline;
		gap: var(--day-strip-gap);
		min-width: 0;
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.number {
		font-family: var(--font-heading);
		color: var(--color-ink);
	}

	.at {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.overtime {
		margin-left: auto;
		color: var(--color-accent-light);
	}

	.result {
		display: flex;
		align-items: center;
		gap: var(--identity-inline-mark-gap);
		min-width: 0;
	}

	.mark {
		display: block;
		flex: none;
		width: var(--playoffs-game-logo);
		height: var(--playoffs-game-logo);
	}

	.score {
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--body-size-small);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.when {
		overflow: hidden;
		font-size: var(--caption-size);
		color: var(--color-muted);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.rule {
		position: absolute;
		right: 0;
		bottom: 0;
		left: 0;
		height: var(--playoffs-series-game-rule);
		background: var(--side-accent);
	}
</style>
