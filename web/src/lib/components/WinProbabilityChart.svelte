<script lang="ts">
	import {
		CHART_HEIGHT,
		CHART_WIDTH,
		domain,
		gridlines,
		segments,
		xScale
	} from '#lib/game/win-probability.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { FinalsChartView } from '#lib/playoffs/types.ts';

	// The curve is one team's: the top of the chart is 100% for that team. The parent draws
	// no chart when the feed has no curve.
	type Props = { chart: FinalsChartView };

	let { chart }: Props = $props();

	const segs = $derived(segments(chart.points));
	const scale = $derived(xScale(domain(chart.points, chart.boundaries)));
	const lines = $derived(chart.boundaries ? gridlines(chart.boundaries) : []);
	const middle = CHART_HEIGHT / 2;
</script>

<div class="win-probability-chart">
	<svg
		viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}"
		preserveAspectRatio="none"
		role="img"
		aria-label={m.playoffs_win_probability()}
	>
		{#each lines as x (x)}
			<line class="gridline" x1={x} y1="0" x2={x} y2={CHART_HEIGHT} />
		{/each}
		<line class="midline" x1="0" y1={middle} x2={CHART_WIDTH} y2={middle} />
		<g transform="scale({scale} 1)">
			{#each segs as s, i (i)}
				<path class="line" d="M {s.x0} {s.y0} L {s.x1} {s.y1}" vector-effect="non-scaling-stroke" />
			{/each}
		</g>
	</svg>
	{#if chart.deficit}
		<span
			class="deficit"
			class:flip={chart.deficit.left > 0.6}
			style:left="{chart.deficit.left * 100}%"
		>
			<span class="deficit-label">{chart.deficit.label}</span>
		</span>
	{/if}
</div>

<style>
	.win-probability-chart {
		position: relative;
		max-inline-size: var(--playoffs-wp-width);
	}

	svg {
		display: block;
		inline-size: 100%;
		block-size: var(--playoffs-wp-height);
	}

	.midline {
		stroke: var(--win-prob-midline);
		stroke-dasharray: var(--win-prob-dash);
		vector-effect: non-scaling-stroke;
	}

	.gridline {
		stroke: var(--color-row-rule);
		vector-effect: non-scaling-stroke;
	}

	.line {
		fill: none;
		stroke: var(--color-accent-light);
		stroke-width: var(--win-prob-line-width);
	}

	.deficit {
		position: absolute;
		top: 0;
		bottom: 0;
		border-left: var(--hairline) solid var(--color-accent);
	}

	.deficit.flip .deficit-label {
		right: var(--day-strip-gap);
		left: auto;
	}

	.deficit-label {
		position: absolute;
		bottom: 0;
		left: var(--day-strip-gap);
		font-size: var(--caption-size);
		white-space: nowrap;
		color: var(--color-accent-light);
	}
</style>
