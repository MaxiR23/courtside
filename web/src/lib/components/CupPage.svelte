<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import ClinchTag from '#lib/components/ClinchTag.svelte';
	import CupBracket from '#lib/components/CupBracket.svelte';
	import CupGames from '#lib/components/CupGames.svelte';
	import CupHeader from '#lib/components/CupHeader.svelte';
	import GroupCard from '#lib/components/GroupCard.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import WildCardTable from '#lib/components/WildCardTable.svelte';
	import type { CupMatchupStore } from '#lib/cup/matchup.svelte.ts';
	import type { CupPageState } from '#lib/cup/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		state: CupPageState;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		gameHref: (id: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
		matchup: CupMatchupStore;
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let {
		state: page,
		allGamesHref,
		standingsHref,
		layout,
		teamHref,
		gameHref,
		playerHref,
		matchup
	}: Props = $props();

	// One toggle widens every group card. Not kept between visits.
	let wide = $state(false);

	const ROW_BONES = [0, 1, 2, 3, 4, 5];
</script>

{#if page.kind === 'ready'}
	{@const view = page.view}
	<CupHeader header={view.header} {allGamesHref} {standingsHref} {layout} {teamHref} />
	<div class="sections">
		{#each view.sections as id (id)}
			<section {id} class="cup-section">
				{#if id === 'groups'}
					<SectionHead title={m.cup_groups()} />
					{#if !view.drawn}
						<MessageRow text={m.cup_not_drawn()} />
					{:else}
						<div class="groups" class:wide>
							{#each view.groups as group (group.key)}
								<GroupCard
									{group}
									{wide}
									onToggleColumns={() => (wide = !wide)}
									{layout}
									{teamHref}
								/>
							{/each}
						</div>
						<ul class="legend">
							{#each view.legend as entry (entry.clinch.code)}
								<li class="entry">
									<ClinchTag clinch={entry.clinch} />
									<span class="label">{entry.label}</span>
								</li>
							{/each}
						</ul>
					{/if}
				{:else if id === 'wild-card'}
					<SectionHead title={m.cup_wild_card()} />
					<div class="wild-cards">
						{#each view.wildCard as table (table.key)}
							<WildCardTable {table} {layout} {teamHref} />
						{/each}
					</div>
				{:else if id === 'bracket'}
					<SectionHead title={m.cup_bracket()} />
					<CupBracket bracket={view.bracket} {layout} {matchup} {gameHref} {playerHref} />
				{:else}
					<SectionHead title={m.cup_games()} />
					<CupGames filters={view.filters} {layout} {gameHref} />
				{/if}
			</section>
		{/each}
	</div>
{:else if page.kind === 'loading'}
	<CupHeader header={null} loading {allGamesHref} {standingsHref} {layout} {teamHref} />
	<section class="page-section table-skeleton" aria-busy="true">
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			<span class="bone heading-bone"></span>
			<BlueprintFrame>
				<div class="bones">
					{#each ROW_BONES as i (i)}
						<span class="bone row-bone"></span>
					{/each}
				</div>
			</BlueprintFrame>
		</div>
	</section>
{:else}
	<CupHeader header={null} {allGamesHref} {standingsHref} {layout} {teamHref} />
	<section class="page-section">
		<MessageRow text={m.feed_unavailable()} />
	</section>
{/if}

<SiteFooter />

<style>
	.page-section {
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
	}

	.sections {
		display: grid;
		gap: var(--detail-section-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
	}

	.cup-section {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
		scroll-margin-top: var(--detail-section-scroll-margin);
	}

	.groups {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, var(--cup-group-min)), 1fr));
		gap: var(--detail-section-gap) var(--panel-section-gap);
	}

	.groups.wide {
		grid-template-columns: repeat(auto-fill, minmax(min(100%, var(--cup-group-wide)), 1fr));
	}

	.wild-cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, var(--cup-group-min)), 1fr));
		gap: var(--detail-section-gap) var(--panel-section-gap);
	}

	.legend {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--day-strip-gap) var(--game-list-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.entry {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.label {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.bones {
		display: grid;
		gap: var(--game-list-gap);
	}

	.bone {
		display: block;
		background: var(--color-surface);
		border-radius: var(--radius);
	}

	.heading-bone {
		width: var(--skeleton-short-width);
		height: var(--section-h2-size);
	}

	.row-bone {
		height: var(--hit-target-size);
	}
</style>
