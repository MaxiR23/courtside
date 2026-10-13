<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import GroupTable from '#lib/components/GroupTable.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { CupGroupView } from '#lib/cup/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		group: CupGroupView;
		wide: boolean; // the extra columns are shown
		onToggleColumns: () => void;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
	};

	let { group, wide, onToggleColumns, layout, teamHref }: Props = $props();
</script>

<article class="group-card">
	<div class="head">
		<h3>{group.title}</h3>
		<span class="meta">{group.meta}</span>
	</div>
	{#if group.rows.length === 0}
		<ul class="draw">
			{#each group.teams as team, i (i)}
				<li class="draw-team">
					<TeamMark {team} part="tile" size="cup-draw" />
					{#if team.city}<span class="city">{team.city}</span>{/if}
					<span class="name"><TeamMark {team} part="name" {teamHref} /></span>
				</li>
			{/each}
		</ul>
	{:else}
		<GroupTable rows={group.rows} {wide} {layout} {teamHref} />
		<button type="button" class="columns" aria-pressed={wide} onclick={onToggleColumns}>
			{m.cup_more_columns()}
		</button>
	{/if}
</article>

<style>
	.group-card {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
		min-width: 0;
	}

	.head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--game-list-gap);
	}

	h3 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
	}

	.meta {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.draw {
		display: grid;
		gap: var(--day-strip-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.draw-team {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		padding-bottom: var(--day-strip-gap);
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.city {
		color: var(--color-muted);
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}

	.columns {
		justify-self: start;
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: var(--hairline) solid var(--color-divider);
		background: none;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
		cursor: pointer;
	}

	.columns[aria-pressed='true'] {
		border-color: var(--color-accent);
		background: var(--color-selected-day);
		color: var(--color-ink);
	}
</style>
