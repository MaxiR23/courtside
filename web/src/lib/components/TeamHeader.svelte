<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import DetailNav from '#lib/components/DetailNav.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import type { TeamHeaderView } from '#lib/team/types.ts';

	type Props = {
		header: TeamHeaderView | null; // null: only the nav row, or its skeleton while loading
		allGamesHref: ResolvedPathname;
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
	};

	let { header, allGamesHref, loading = false }: Props = $props();

	const CELL_BONES = [0, 1, 2, 3];
</script>

<header class="team-header" aria-busy={loading && !header ? 'true' : undefined}>
	<div class="grid-bg" aria-hidden="true"></div>
	<div class="content">
		<DetailNav {allGamesHref} />

		{#if header}
			<div class="columns">
				<div class="identity">
					<div class="code-box">
						<TeamMonogram code={header.code} size="team" />
						<span class="strip" aria-hidden="true">
							<span class="half" style:background-color={header.colors.primary}></span>
							<span class="half" style:background-color={header.colors.secondary}></span>
						</span>
					</div>
					<span class="city">{header.city}</span>
					<h1 class="name">{header.name}</h1>
					<span class="conference-line">{header.conferenceLine}</span>
				</div>
				<div class="standing">
					<span class="record">{header.record}</span>
					<span class="win-pct">{header.winPct}</span>
					<div class="cells">
						{#each header.cells as cell (cell.label)}
							<div class="cell">
								<span class="cell-label">{cell.label}</span>
								<span class="cell-value">{cell.value}</span>
								{#if cell.sub}<span class="cell-sub">{cell.sub}</span>{/if}
							</div>
						{/each}
					</div>
				</div>
			</div>
		{:else if loading}
			<div class="columns skeleton" aria-hidden="true" use:play={shimmer}>
				<div class="identity">
					<span class="bone code-bone"></span>
					<span class="bone city-bone"></span>
					<span class="bone name-bone"></span>
				</div>
				<div class="standing">
					<span class="bone record-bone"></span>
					<div class="cells">
						{#each CELL_BONES as i (i)}
							<span class="bone cell-bone"></span>
						{/each}
					</div>
				</div>
			</div>
		{/if}
	</div>
</header>

<style>
	.team-header {
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

	.columns {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--panel-section-gap);
		align-items: start;
	}

	.identity {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--day-strip-gap);
	}

	.code-box {
		display: grid;
		width: var(--team-code-box-size);
	}

	.strip {
		display: flex;
		height: var(--team-color-strip-height);
	}

	.half {
		flex: 1;
	}

	.city {
		font-size: var(--body-size-small);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.name {
		margin: 0;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--team-h1-size);
		line-height: var(--detail-h1-line-height);
		text-transform: uppercase;
		hyphens: manual;
	}

	.conference-line {
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.standing {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.record {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--team-record-size);
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}

	.win-pct {
		font-size: var(--team-win-pct-size);
		color: var(--color-accent-light);
		font-variant-numeric: tabular-nums;
	}

	.cells {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--team-header-cell-min)), 1fr));
		gap: var(--game-list-gap);
		margin-top: var(--game-list-gap);
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
		font-size: var(--detail-info-value-size);
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

	.code-bone {
		width: var(--team-code-box-size);
		height: var(--team-code-box-size);
	}

	.city-bone {
		width: var(--skeleton-button-width);
		height: var(--body-size-small);
	}

	.name-bone {
		width: 100%;
		height: var(--team-h1-size);
	}

	.record-bone {
		width: var(--skeleton-short-width);
		height: var(--team-record-size);
	}

	.cell-bone {
		height: var(--hit-target-size);
	}
</style>
