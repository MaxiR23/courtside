<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import NextGameCard from '#lib/components/NextGameCard.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { OverviewSection } from '#lib/team/types.ts';

	type Props = { overview: OverviewSection; gameHref: (id: string) => ResolvedPathname };

	let { overview, gameHref }: Props = $props();

	// Keyed by photo URL, so a new URL tries again after a failure.
	let failedPhoto = $state<string | null>(null);
	const arena = $derived(overview.arena);
	const photo = $derived(arena.photo && arena.photo !== failedPhoto ? arena.photo : null);
</script>

<div class="overview">
	<div class="left">
		{#if photo}
			<BlueprintFrame>
				<div class="photo-box">
					<img src={photo} alt="" loading="lazy" onerror={() => (failedPhoto = photo)} />
					<div class="fade" aria-hidden="true"></div>
					<div class="caption">
						<span class="label">{m.team_arena_label()}</span>
						<span class="arena">{arena.name}</span>
						{#if arena.city}<span class="arena-city">{arena.city}</span>{/if}
					</div>
				</div>
			</BlueprintFrame>
		{:else}
			<div class="cell arena-cell">
				<span class="label">{m.team_arena_label()}</span>
				<span class="cell-value">{arena.name}</span>
				{#if arena.city}<span class="cell-sub">{arena.city}</span>{/if}
			</div>
		{/if}
	</div>
	<div class="right">
		{#if overview.coach}
			<div class="cell coach-cell">
				<span class="label">{overview.coach.label}</span>
				<span class="cell-value">{overview.coach.value}</span>
				{#if overview.coach.sub}<span class="cell-sub">{overview.coach.sub}</span>{/if}
			</div>
		{/if}
		<div class="cell colors-cell">
			<span class="label">{m.team_colors_label()}</span>
			<ul class="swatches">
				{#each overview.colors as color, i (i)}
					<li class="swatch">
						<span class="chip" style:background-color={color.hex} aria-hidden="true"></span>
						<span class="hex">{color.hex}</span>
					</li>
				{/each}
			</ul>
		</div>
		<NextGameCard game={overview.nextGame} {gameHref} />
	</div>
</div>

<style>
	.overview {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--side-padding);
		align-items: start;
	}

	.right {
		display: grid;
		gap: var(--side-padding);
	}

	.photo-box {
		position: relative;
		overflow: hidden;
		aspect-ratio: var(--arena-aspect);
	}

	.photo-box img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.fade {
		position: absolute;
		inset: 0;
		background: var(--hero-fade);
		pointer-events: none;
	}

	.caption {
		position: absolute;
		inset-inline: var(--game-list-gap);
		bottom: var(--game-list-gap);
		display: flex;
		flex-direction: column;
	}

	.arena {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--detail-info-value-size);
		text-transform: uppercase;
	}

	.arena-city {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.cell {
		display: flex;
		flex-direction: column;
		gap: var(--day-strip-gap);
		padding-top: var(--game-list-gap);
		border-top: var(--hairline) solid var(--color-divider);
	}

	.label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.cell-value {
		font-family: var(--font-heading);
		font-size: var(--detail-info-value-size);
	}

	.cell-sub {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.swatches {
		display: flex;
		flex-wrap: wrap;
		gap: var(--panel-section-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.swatch {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.chip {
		width: var(--team-swatch-size);
		height: var(--team-swatch-size);
		border: var(--hairline) solid var(--color-divider);
	}

	.hex {
		font-family: var(--font-heading);
		font-size: var(--body-size);
		font-variant-numeric: tabular-nums;
	}
</style>
