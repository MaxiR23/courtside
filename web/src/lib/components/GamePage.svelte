<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import GameHeader from '#lib/components/GameHeader.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import SectionTabs from '#lib/components/SectionTabs.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import type { GamePageState } from '#lib/game/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = { state: GamePageState; allGamesHref: ResolvedPathname; layout: RowLayout };

	let { state, allGamesHref, layout }: Props = $props();

	const SECTION_BONES = [0, 1]; // the first two sections
</script>

{#if state.kind === 'ready'}
	<GameHeader header={state.view.header} {layout} {allGamesHref} />
	<SectionTabs tabs={state.view.tabs} miniScore={state.view.miniScore} />
{:else if state.kind === 'loading'}
	<GameHeader header={null} loading {layout} {allGamesHref} />
	<section class="page-section section-skeleton" aria-busy="true">
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			{#each SECTION_BONES as i (i)}
				<span class="bone heading-bone"></span>
				<BlueprintFrame><span class="bone block-bone"></span></BlueprintFrame>
			{/each}
		</div>
	</section>
{:else if state.kind === 'unavailable'}
	<GameHeader header={null} {layout} {allGamesHref} />
	<section class="page-section">
		<MessageRow text={m.feed_unavailable()} />
	</section>
{:else}
	<GameHeader header={null} {layout} {allGamesHref} />
	<section class="page-section">
		<MessageRow
			text={m.game_not_found()}
			link={{ href: allGamesHref, label: m.hero_all_games() }}
		/>
	</section>
{/if}

<SiteFooter />

<style>
	.page-section {
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
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

	.block-bone {
		height: var(--hero-column-min);
	}
</style>
