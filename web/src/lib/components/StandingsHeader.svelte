<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import SeasonTag from '#lib/components/SeasonTag.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import type { StandingsGrouping, StandingsHeaderView } from '#lib/standings/types.ts';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';

	type Props = {
		header: StandingsHeaderView | null; // null: only the nav row and the title, or the bones while loading
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
		seasonSelect?: SeasonControl | null; // null: no selector
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
		onGroupingChange,
		seasonSelect = null
	}: Props = $props();

	const mobile = $derived(layout === 'mobile');
</script>

{#snippet firstLine()}
	{#if header}
		<div class="intro">
			<div class="season-line">
				{#if !header.tag}<StatusTag text={header.season} accent />{/if}
				{#if header.tag}<SeasonTag text={header.tag} />{/if}
				<span class="state-line">{header.stateLine}</span>
			</div>
			<h1>{m.standings_title()}</h1>
			<p class="note">{m.standings_note()}</p>
		</div>
	{:else}
		<h1>{m.standings_title()}</h1>
	{/if}
{/snippet}

{#snippet bodyRows()}
	{#if loading}
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			<SkeletonBone width="var(--skeleton-short-width)" height="var(--body-size)" />
			<SkeletonBone width="var(--skeleton-button-width)" height="var(--body-size-small)" />
			<SkeletonBone width="var(--skeleton-button-width)" height="var(--hit-target-size)" />
		</div>
	{/if}
{/snippet}

{#snippet viewToggle()}
	<div class="toggle" class:mobile role="group" aria-label={m.standings_view_toggle()}>
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
{/snippet}

<PageHeader
	nav={{ page: 'standings', gamesHref: allGamesHref, standingsHref }}
	{layout}
	{seasonSelect}
	busy={loading && !header}
	first={firstLine}
	body={header ? undefined : bodyRows}
	aside={header ? viewToggle : undefined}
/>

<style>
	.toggle {
		display: inline-flex;
		align-self: flex-end;
		margin-top: auto;
		border: var(--hairline) solid var(--color-divider);
	}

	.toggle.mobile {
		align-self: flex-start;
		margin-top: 0;
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
</style>
