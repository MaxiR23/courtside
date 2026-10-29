<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import AllStarGames from '#lib/components/AllStarGames.svelte';
	import AllStarHeader from '#lib/components/AllStarHeader.svelte';
	import AllStarLastTime from '#lib/components/AllStarLastTime.svelte';
	import AllStarMvp from '#lib/components/AllStarMvp.svelte';
	import AllStarTeams from '#lib/components/AllStarTeams.svelte';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import PageContainer from '#lib/components/PageContainer.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import { LiveTick } from '#lib/all-star/live-tick.svelte.ts';
	import { GameSelection } from '#lib/all-star/selection.svelte.ts';
	import type { AllStarPageState } from '#lib/all-star/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		state: AllStarPageState;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
		seasonSelect?: SeasonControl | null; // null: no selector
		seasonTag?: string | null; // the Season tag of a past season whose feed is unavailable
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let {
		state: page,
		allGamesHref,
		standingsHref,
		layout,
		teamHref,
		playerHref,
		seasonSelect = null,
		seasonTag = null
	}: Props = $props();

	const CARD_BONES = [0, 1, 2, 3];

	const selection = new GameSelection();
	const tick = new LiveTick();
	const mobile = $derived(layout === 'mobile');
	const live = $derived(page.kind === 'ready' && page.view.header.state === 'live');

	// The clock re-reads the feed every second, only while a game can be live.
	$effect(() => (live ? tick.start() : undefined));

	// The section tabs' scroll rule: smooth, or at once under reduced motion.
	function scrollToSection(id: string) {
		const reduced =
			typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
		document
			.getElementById(id)
			?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
	}

	// A tap on the live scoreboard or on the Championship card selects that game and shows it.
	function showGame(id: string) {
		selection.select(id);
		scrollToSection('games');
	}
</script>

{#if page.kind === 'ready'}
	{@const view = page.view}
	<AllStarHeader
		header={view.header}
		{allGamesHref}
		{standingsHref}
		{layout}
		{tick}
		onLive={showGame}
		{seasonSelect}
	/>
	<PageContainer sidePadding={mobile ? 'var(--allstar-side-padding-mobile)' : undefined}>
		<div class="sections" class:mobile>
			{#each view.sections as id (id)}
				<section
					{id}
					class="all-star-section"
					class:mobile
					aria-label={id === 'mvp' ? m.allstar_mvp_label() : undefined}
				>
					{#if id === 'last-time' && view.lastTime}
						<SectionHead title={m.allstar_last_time()} />
						<AllStarLastTime lastTime={view.lastTime} {layout} {playerHref} />
					{:else if id === 'mvp'}
						<AllStarMvp
							mvp={view.mvp}
							scoreline={view.scoreline}
							{layout}
							{teamHref}
							{playerHref}
							onChampionship={() => view.scoreline && showGame(view.scoreline.gameId)}
						/>
					{:else if id === 'games'}
						<AllStarGames
							{view}
							kicker={view.header.tag}
							{selection}
							{tick}
							{layout}
							{teamHref}
							{playerHref}
						/>
					{:else if id === 'teams'}
						<SectionHead title={m.allstar_teams_title()} />
						<AllStarTeams teams={view.teams} {layout} {playerHref} />
					{/if}
				</section>
			{/each}
		</div>
	</PageContainer>
{:else if page.kind === 'loading'}
	<AllStarHeader
		header={null}
		loading
		{allGamesHref}
		{standingsHref}
		{layout}
		{tick}
		onLive={showGame}
		{seasonSelect}
	/>
	<PageContainer sidePadding={mobile ? 'var(--allstar-side-padding-mobile)' : undefined}>
		<section class="page-section" class:mobile aria-busy="true">
			<div class="bones" aria-hidden="true" use:play={shimmer}>
				<span class="bone heading-bone"></span>
				<BlueprintFrame marks="allstar">
					<div class="card-bones">
						{#each CARD_BONES as i (i)}
							<span class="bone card-bone"></span>
						{/each}
					</div>
				</BlueprintFrame>
			</div>
		</section>
	</PageContainer>
{:else}
	<AllStarHeader
		header={null}
		{allGamesHref}
		{standingsHref}
		{layout}
		{tick}
		onLive={showGame}
		{seasonSelect}
		{seasonTag}
	/>
	<PageContainer sidePadding={mobile ? 'var(--allstar-side-padding-mobile)' : undefined}>
		<section class="page-section" class:mobile>
			<MessageRow text={m.feed_unavailable()} />
		</section>
	</PageContainer>
{/if}

<SiteFooter />

<style>
	.sections {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--detail-section-gap);
	}

	.sections.mobile {
		gap: var(--allstar-section-gap-mobile);
	}

	.all-star-section {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
		min-width: 0;
		scroll-margin-top: var(--allstar-scroll-offset);
	}

	.all-star-section.mobile {
		scroll-margin-top: var(--allstar-scroll-offset-mobile);
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

	.card-bones {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--allstar-card-min)), 1fr));
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
	}

	.card-bone {
		height: var(--allstar-mvp-photo-height-mobile);
	}
</style>
