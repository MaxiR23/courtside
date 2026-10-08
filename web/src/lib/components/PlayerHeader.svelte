<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import DetailNav from '#lib/components/DetailNav.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import { play } from '#lib/hero/motion.ts';
	import type { PlayerHeaderView } from '#lib/player/types.ts';
	import { scrollFade } from '#lib/player/scroll-fade.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		header: PlayerHeaderView | null; // null: only the nav row, or its skeleton while loading
		allGamesHref: ResolvedPathname;
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
	};

	let { header, allGamesHref, loading = false }: Props = $props();

	const CELL_BONES = [0, 1, 2, 3];

	// Keyed by photo URL, so a new URL tries again after a failure. A failed photo counts as none.
	let failedPhoto = $state<string | null>(null);
	const photo = $derived(header?.photo && header.photo !== failedPhoto ? header.photo : null);
</script>

<header class="player-header" aria-busy={loading && !header ? 'true' : undefined}>
	<div class="grid-bg" aria-hidden="true"></div>
	<div class="content">
		<DetailNav {allGamesHref} />

		{#if header}
			<div class="top">
				<div class="text">
					<div class="tags">
						<StatusTag text={header.teamCode} />
						<StatusTag text={header.status.label} accent={header.status.injured} />
					</div>
					<span class="first-name">{header.firstName}</span>
					<h1 class="last-name">{header.lastName}</h1>
					<span class="line">{header.line}</span>
					{#if header.injury}
						<BlueprintFrame>
							<div class="injury">
								<StatusTag injury={header.injury.status} />
								{#if header.injury.comment}<p class="comment">{header.injury.comment}</p>{/if}
								<span class="updated">{header.injury.updated}</span>
							</div>
						</BlueprintFrame>
					{/if}
				</div>
				{#if photo}
					<div class="photo" use:scrollFade>
						<img src={photo} alt="" onerror={() => (failedPhoto = photo)} />
					</div>
				{/if}
			</div>
			{#if header.stats}
				<div class="stats">
					<Kicker text={header.stats.label} />
					<div class="cells">
						{#each header.stats.cells as cell (cell.label)}
							<div class="cell">
								<span class="cell-label">{cell.label}</span>
								<span class="cell-value">{cell.value}</span>
								{#if cell.sub}<span class="cell-sub">{cell.sub}</span>{/if}
							</div>
						{/each}
					</div>
				</div>
			{/if}
		{:else if loading}
			<div class="top skeleton" aria-hidden="true" use:play={shimmer}>
				<div class="text">
					<span class="bone tag-bone"></span>
					<span class="bone name-bone"></span>
					<span class="bone line-bone"></span>
				</div>
			</div>
			<div class="cells skeleton" aria-hidden="true" use:play={shimmer}>
				{#each CELL_BONES as i (i)}
					<span class="bone cell-bone"></span>
				{/each}
			</div>
		{/if}
	</div>
</header>

<style>
	.player-header {
		position: relative;
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	.grid-bg {
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(var(--color-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(90deg, var(--color-grid-line) var(--hairline), transparent var(--hairline));
		background-size: var(--hero-grid-size) var(--hero-grid-size);
		pointer-events: none;
	}

	.content {
		position: relative;
		display: grid;
		gap: var(--panel-section-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--game-list-gap) var(--side-padding) var(--panel-section-gap);
	}

	.top {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: var(--panel-section-gap);
	}

	.text {
		display: flex;
		flex: var(--player-text-flex);
		flex-direction: column;
		align-items: flex-start;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: var(--day-strip-gap);
	}

	.first-name {
		font-size: var(--player-first-name-size);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.last-name {
		margin: 0;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--player-h1-size);
		line-height: var(--player-h1-line-height);
		text-transform: uppercase;
		hyphens: manual;
	}

	.line {
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.injury {
		display: grid;
		justify-items: start;
		gap: var(--day-strip-gap);
		padding: var(--game-list-gap);
	}

	.comment {
		margin: 0;
		font-size: var(--body-size);
	}

	.updated {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.photo {
		flex: var(--player-photo-flex);
		aspect-ratio: var(--player-photo-aspect);
		margin-right: calc(-1 * var(--side-padding));
		margin-bottom: calc(-1 * var(--player-photo-overlap));
		mask-image: var(--player-photo-mask);
		filter: var(--player-photo-shadow);
	}

	.photo img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: contain;
		object-position: bottom right;
	}

	.stats {
		position: relative;
		display: grid;
		gap: var(--game-list-gap);
	}

	.cells {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--player-hero-cell-min)), 1fr));
		gap: var(--game-list-gap);
	}

	.cell {
		display: flex;
		flex-direction: column;
		gap: var(--day-strip-gap);
		padding-top: var(--game-list-gap);
		border-top: var(--hairline) solid var(--color-divider);
	}

	.cell-label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.cell-value {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--player-hero-value-size);
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}

	.cell-sub {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.bone {
		display: block;
		background: var(--color-surface);
		border-radius: var(--radius);
	}

	.tag-bone {
		width: var(--skeleton-button-width);
		height: var(--body-size-small);
	}

	.name-bone {
		width: 100%;
		height: var(--player-h1-size);
	}

	.line-bone {
		width: var(--skeleton-short-width);
		height: var(--body-size);
	}

	.cell-bone {
		height: var(--hit-target-size);
	}
</style>
