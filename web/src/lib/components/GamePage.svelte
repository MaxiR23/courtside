<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import BoxScore from '#lib/components/BoxScore.svelte';
	import GameHeader from '#lib/components/GameHeader.svelte';
	import Highlights from '#lib/components/Highlights.svelte';
	import LineScore from '#lib/components/LineScore.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import SectionTabs from '#lib/components/SectionTabs.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import TeamStats from '#lib/components/TeamStats.svelte';
	import WinProbability from '#lib/components/WinProbability.svelte';
	import type { GamePageState } from '#lib/game/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = { state: GamePageState; allGamesHref: ResolvedPathname; layout: RowLayout };

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let { state: page, allGamesHref, layout }: Props = $props();

	const SECTION_BONES = [0, 1]; // the first two sections

	// The highlight playing in place, as on the home.
	let playingId = $state<string | null>(null);
</script>

{#snippet sectionHead(title: string, meta: string | null, emphasis: boolean)}
	<div class="section-head">
		<h2>{title}</h2>
		{#if meta}<span class="meta" class:emphasis>{meta}</span>{/if}
	</div>
{/snippet}

{#if page.kind === 'ready'}
	<GameHeader header={page.view.header} {layout} {allGamesHref} />
	<SectionTabs tabs={page.view.tabs} miniScore={page.view.miniScore} />
	{@const sections = page.view.sections}
	<div class="sections">
		{#if sections.highlights}
			<section id="highlights">
				{@render sectionHead(m.game_tab_highlights(), sections.highlights.platform, false)}
				<div class="highlights-wrap">
					<Highlights
						detail
						{...sections.highlights}
						{playingId}
						onPlay={(id) => (playingId = id)}
					/>
				</div>
			</section>
		{/if}
		{#if sections.score}
			<section id="score">
				{@render sectionHead(m.game_tab_score(), null, false)}
				<div class="score-grid">
					<LineScore
						detail
						away={sections.score.lineScore.away}
						home={sections.score.lineScore.home}
					/>
					{#if sections.score.stats}
						<TeamStats
							open={true}
							away={sections.score.stats.away}
							home={sections.score.stats.home}
							leads={sections.score.stats.leads}
						/>
					{/if}
				</div>
			</section>
		{/if}
		{#if sections.winProbability}
			<section id="win-probability">
				{@render sectionHead(m.game_section_win_probability(), sections.winProbability.meta, true)}
				<WinProbability chart={sections.winProbability} />
			</section>
		{/if}
		{#if sections.boxScore}
			<section id="box-score">
				{@render sectionHead(m.game_tab_box_score(), null, false)}
				<BoxScore box={sections.boxScore} {layout} />
			</section>
		{/if}
	</div>
{:else if page.kind === 'loading'}
	<GameHeader header={null} loading {layout} {allGamesHref} />
	<section class="page-section section-skeleton" aria-busy="true">
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			{#each SECTION_BONES as i (i)}
				<span class="bone heading-bone"></span>
				<BlueprintFrame><span class="bone block-bone"></span></BlueprintFrame>
			{/each}
		</div>
	</section>
{:else if page.kind === 'unavailable'}
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

	.sections {
		display: grid;
		gap: var(--detail-section-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
	}

	.sections section {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
		scroll-margin-top: var(--detail-section-scroll-margin);
	}

	.section-head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--game-list-gap);
	}

	.section-head h2 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--detail-section-h2-size);
		line-height: var(--detail-section-h2-line-height);
		text-transform: uppercase;
	}

	.meta {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.meta.emphasis {
		font-family: var(--font-heading);
		font-size: var(--win-prob-meta-size);
		color: var(--color-accent-light);
	}

	.highlights-wrap {
		max-width: var(--detail-highlights-max-width);
	}

	.score-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--side-padding);
		align-items: start;
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
