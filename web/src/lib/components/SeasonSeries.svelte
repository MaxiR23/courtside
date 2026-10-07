<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import type { SeasonSeriesSection } from '#lib/game/types.ts';

	type Props = { series: SeasonSeriesSection };

	let { series }: Props = $props();
</script>

<BlueprintFrame>
	<div class="series">
		<p class="summary">{series.summary}</p>
		<ul>
			{#each series.games as game, i (i)}
				<li class="game">
					<span class="date" class:current={game.current}>{game.date}</span>
					<span class="result"
						>{#if game.awayPoints === null}{game.awayCode} – {game.homeCode}{:else}<span
								class="side"
								class:dimmed={game.loser === 'away'}>{game.awayCode} {game.awayPoints}</span
							>
							–
							<span class="side" class:dimmed={game.loser === 'home'}
								>{game.homePoints} {game.homeCode}</span
							>{/if}</span
					>
					<span class="arena">{game.arena}</span>
				</li>
			{/each}
		</ul>
	</div>
</BlueprintFrame>

<style>
	.series {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--side-padding);
		padding: var(--game-list-gap);
	}

	.summary {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--series-summary-size);
		line-height: var(--detail-section-h2-line-height);
		text-transform: uppercase;
	}

	ul {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.game {
		display: grid;
		gap: var(--day-strip-gap);
		padding: var(--game-list-gap) 0;
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.date {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.current {
		color: var(--color-accent-light);
	}

	.dimmed {
		opacity: var(--detail-dimmed-opacity);
	}

	.result {
		font-family: var(--font-heading);
		font-size: var(--detail-info-value-size);
		font-variant-numeric: tabular-nums;
	}

	.arena {
		font-size: var(--body-size-small);
		color: var(--color-muted);
		overflow-wrap: anywhere;
	}
</style>
