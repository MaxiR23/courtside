<script lang="ts">
	import type { BarView } from '#lib/playoffs/types.ts';

	// Each half is drawn at its value over the larger of the two; the better side is the feed's.
	type Props = { bar: BarView };

	let { bar }: Props = $props();
</script>

<div class="mirrored-bar">
	<span class="value left">{bar.sides[0].value}</span>
	<span class="label">{bar.label}</span>
	<span class="value right">{bar.sides[1].value}</span>
	{#each bar.sides as side, i (i)}
		<span class="half {i === 0 ? 'left' : 'right'}">
			<span
				class="fill"
				class:better={side.better}
				class:muted={!side.better}
				class:ink={side.better && side.color === null}
				style:inline-size="{side.share * 100}%"
				style:background-color={side.better ? side.color : null}
			></span>
		</span>
	{/each}
</div>

<style>
	.mirrored-bar {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
		align-items: baseline;
		gap: var(--day-strip-gap) var(--game-list-gap);
		font-variant-numeric: tabular-nums;
	}

	.label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.value {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}

	.value.left {
		text-align: right;
	}

	.half {
		display: flex;
		grid-row: 2;
		height: var(--stat-bar-height);
		background: var(--color-surface);
	}

	.half.left {
		grid-column: 1;
		justify-content: flex-end;
	}

	.half.right {
		grid-column: 3;
		justify-content: flex-start;
	}

	.fill {
		display: block;
		height: 100%;
	}

	.fill.muted {
		background: var(--color-bar-neutral);
	}

	.fill.ink {
		background: var(--color-ink);
	}
</style>
