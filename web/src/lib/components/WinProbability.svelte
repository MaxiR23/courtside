<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import type { WinProbabilitySection } from '#lib/game/types.ts';
	import {
		CHART_HEIGHT,
		CHART_WIDTH,
		markerPosition,
		segments,
		span,
		xScale
	} from '#lib/game/win-probability.ts';
	import { m } from '#lib/paraglide/messages.js';

	// The section header draws the meta, so the chart does not take it.
	type Props = { chart: Omit<WinProbabilitySection, 'meta'> };

	let { chart }: Props = $props();

	const segs = $derived(segments(chart.points));
	const scale = $derived(xScale(span(chart.points)));
	const marker = $derived(markerPosition(chart.points));
	const middle = CHART_HEIGHT / 2;
</script>

<BlueprintFrame>
	<div class="win-probability">
		<div class="axis">
			<span>{chart.homeCode}</span>
			<span>{chart.middle}</span>
			<span>{chart.awayCode}</span>
		</div>
		<div class="plot">
			<svg
				viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}"
				preserveAspectRatio="none"
				role="img"
				aria-label={m.game_section_win_probability()}
			>
				<line class="midline" x1="0" y1={middle} x2={CHART_WIDTH} y2={middle} />
				<g class="series" transform="scale({scale} 1)">
					{#each segs as s, i (i)}
						<path
							class="area"
							d="M {s.x0} {middle} L {s.x0} {s.y0} L {s.x1} {s.y1} L {s.x1} {middle} Z"
						/>
						<path
							class="line"
							d="M {s.x0} {s.y0} L {s.x1} {s.y1}"
							vector-effect="non-scaling-stroke"
						/>
					{/each}
				</g>
			</svg>
			<span
				class="marker"
				style:left="{marker.left * 100}%"
				style:top="{marker.top * 100}%"
				aria-hidden="true"
			></span>
		</div>
	</div>
</BlueprintFrame>

<style>
	.win-probability {
		display: grid;
		grid-template-columns: var(--win-prob-axis-width) 1fr;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
	}

	.axis {
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-muted);
	}

	.plot {
		position: relative;
	}

	svg {
		display: block;
		width: 100%;
		height: var(--win-prob-height);
	}

	.midline {
		stroke: var(--win-prob-midline);
		stroke-dasharray: var(--win-prob-dash);
		vector-effect: non-scaling-stroke;
	}

	.area {
		fill: var(--win-prob-fill);
		stroke: none;
	}

	.line {
		fill: none;
		stroke: var(--color-accent-light);
		stroke-width: var(--win-prob-line-width);
	}

	.marker {
		position: absolute;
		width: var(--win-prob-marker-size);
		height: var(--win-prob-marker-size);
		translate: -50% -50%;
		background: var(--color-accent-light);
		box-shadow: 0 0 0 var(--win-prob-marker-ring) var(--win-prob-marker-ring-color);
	}
</style>
