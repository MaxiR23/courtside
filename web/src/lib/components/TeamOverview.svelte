<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import InfoCell from '#lib/components/InfoCell.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
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
						<Kicker text={m.team_arena_label()} />
						<span class="arena">{arena.name}</span>
						{#if arena.city}<span class="arena-city">{arena.city}</span>{/if}
					</div>
				</div>
			</BlueprintFrame>
		{:else}
			<InfoCell label={m.team_arena_label()} value={arena.name} sub={arena.city} />
		{/if}
	</div>
	<div class="right">
		{#if overview.coach}
			<InfoCell
				label={overview.coach.label}
				value={overview.coach.value}
				sub={overview.coach.sub}
			/>
		{/if}
		<InfoCell label={m.team_colors_label()}>
			<ul class="swatches">
				{#each overview.colors as color, i (i)}
					<li class="swatch">
						<span class="chip" style:background-color={color.hex} aria-hidden="true"></span>
						<span class="hex">{color.hex}</span>
					</li>
				{/each}
			</ul>
		</InfoCell>
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
