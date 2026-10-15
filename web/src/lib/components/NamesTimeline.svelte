<script lang="ts">
	import Kicker from '#lib/components/Kicker.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { NameRunView } from '#lib/team/types.ts';

	type Props = {
		runs: NameRunView[]; // oldest first; the last one is the current run
		layout: RowLayout;
		seasonHref: (season: number) => string; // the route with ?season=, resolved by the page
	};

	let { runs, layout, seasonHref }: Props = $props();
</script>

<section class="names">
	<Kicker text={m.past_names_title()} />
	<ol class="runs" class:scroll={layout === 'mobile'}>
		{#each runs as run (run.key)}
			<li class="item">
				{#if run.season !== null}
					<a class="run" href={seasonHref(run.season)}>
						<span class="years">{run.years}</span>
						<span class="name">{run.name}</span>
						<TeamMonogram code={run.code} size="names" />
					</a>
				{:else}
					<div class="run current" aria-current="true">
						<span class="years">{run.years}</span>
						<span class="name">{run.name}</span>
						<TeamMonogram code={run.code} size="names" />
					</div>
				{/if}
			</li>
		{/each}
	</ol>
</section>

<style>
	.names {
		display: grid;
		gap: var(--game-list-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding) var(--side-padding) 0;
	}

	.runs {
		display: flex;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.scroll {
		overflow-x: auto;
		scroll-snap-type: x mandatory;
	}

	.item {
		min-width: 0;
	}

	.item + .item {
		border-left: var(--hairline) solid var(--color-divider);
	}

	.scroll .item {
		flex: none;
		scroll-snap-align: start;
	}

	.run {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-height: var(--hit-target-size);
		padding: 0 var(--panel-section-gap);
		color: var(--color-ink);
		text-decoration: none;
	}

	a.run:hover .name {
		color: var(--color-accent-hover);
	}

	.years {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--past-names-year-size);
		color: var(--color-muted);
		white-space: nowrap;
	}

	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		font-size: var(--past-names-name-size);
		color: var(--color-ink);
		white-space: nowrap;
	}

	.current .years,
	.current .name {
		color: var(--color-accent-light);
	}
</style>
