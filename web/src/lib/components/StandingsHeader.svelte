<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import NavRow from '#lib/components/NavRow.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import type { StandingsGrouping, StandingsHeaderView } from '#lib/standings/types.ts';

	type Props = {
		header: StandingsHeaderView | null; // null: only the nav row and the title, or the bones while loading
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		grouping: StandingsGrouping;
		onGroupingChange: (grouping: StandingsGrouping) => void;
	};

	let {
		header,
		loading = false,
		allGamesHref,
		standingsHref,
		layout,
		grouping,
		onGroupingChange
	}: Props = $props();
</script>

<header class="standings-header" aria-busy={loading && !header ? 'true' : undefined}>
	<div class="grid-bg" aria-hidden="true"></div>
	<div class="content">
		<NavRow page="standings" gamesHref={allGamesHref} {standingsHref} {layout} />

		{#if header}
			<div class="columns">
				<div class="intro">
					<div class="season-line">
						<StatusTag text={header.season} accent />
						<span class="state-line">{header.stateLine}</span>
					</div>
					<h1>{m.standings_title()}</h1>
					<p class="note">{m.standings_note()}</p>
				</div>
				<div class="toggle" role="group" aria-label={m.standings_view_toggle()}>
					<button
						type="button"
						class="option"
						class:active={grouping === 'conference'}
						aria-pressed={grouping === 'conference'}
						onclick={() => onGroupingChange('conference')}
					>
						{m.standings_conference()}
					</button>
					<button
						type="button"
						class="option"
						class:active={grouping === 'division'}
						aria-pressed={grouping === 'division'}
						onclick={() => onGroupingChange('division')}
					>
						{m.standings_division()}
					</button>
				</div>
			</div>
		{:else}
			<h1>{m.standings_title()}</h1>
			{#if loading}
				<div class="bones" aria-hidden="true" use:play={shimmer}>
					<span class="bone tag-bone"></span>
					<span class="bone state-bone"></span>
					<span class="bone toggle-bone"></span>
				</div>
			{/if}
		{/if}
	</div>
</header>

<style>
	.standings-header {
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
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: var(--panel-section-gap);
	}

	.intro {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.season-line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.state-line {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	h1 {
		margin: 0;
		font-size: var(--standings-h1-size);
	}

	.note {
		margin: 0;
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.toggle {
		display: inline-flex;
		border: var(--hairline) solid var(--color-divider);
	}

	.option {
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: 0;
		background: none;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
		cursor: pointer;
	}

	.option + .option {
		border-left: var(--hairline) solid var(--color-divider);
	}

	.option.active {
		background: var(--toggle-active-fill);
		box-shadow: inset 0 0 0 var(--hairline) var(--color-accent);
		color: var(--color-ink);
	}

	.bones {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.bone {
		display: block;
		background: var(--color-surface);
		border-radius: var(--radius);
	}

	.tag-bone {
		width: var(--skeleton-short-width);
		height: var(--body-size);
	}

	.state-bone {
		width: var(--skeleton-button-width);
		height: var(--body-size-small);
	}

	.toggle-bone {
		width: var(--skeleton-button-width);
		height: var(--hit-target-size);
	}
</style>
