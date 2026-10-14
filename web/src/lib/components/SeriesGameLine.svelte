<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';
	import type { SeriesGameRowView } from '#lib/playoffs/types.ts';

	type Props = { game: SeriesGameRowView };

	let { game }: Props = $props();
</script>

<span class="line">
	<span class="label">{game.label}</span>
	{#if game.final}
		<span class="result">
			<span class="side" class:loser={game.away.loser}>
				<span class="code">{game.away.code}</span>
				<span class="score">{game.away.score}</span>
			</span>
			<span class="dash" aria-hidden="true">–</span>
			<span class="side" class:loser={game.home.loser}>
				<span class="score">{game.home.score}</span>
				<span class="code">{game.home.code}</span>
			</span>
			{#if game.overtime}<span class="overtime">{m.playoffs_ot()}</span>{/if}
		</span>
	{:else if game.when}
		<span class="when">{game.when}</span>
	{/if}
</span>

<style>
	.line {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--day-strip-gap);
		min-width: 0;
		width: 100%;
		font-variant-numeric: tabular-nums;
		line-height: 1;
		text-align: left;
	}

	.label,
	.when {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.when,
	.loser,
	.dash {
		color: var(--color-muted);
	}

	.result {
		display: flex;
		flex: none;
		align-items: center;
		gap: var(--hairline);
		white-space: nowrap;
	}

	.side {
		display: inline-flex;
		gap: var(--hairline);
	}

	.overtime {
		margin-left: var(--hairline);
		color: var(--color-accent-light);
	}
</style>
