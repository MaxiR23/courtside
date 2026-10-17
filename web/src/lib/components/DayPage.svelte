<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import DayHeader from '#lib/components/DayHeader.svelte';
	import GameCard from '#lib/components/GameCard.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import type { DateCalendar } from '#lib/calendar/types.ts';
	import type { DayPageState } from '#lib/day/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		state: DayPageState;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		previousHref: ResolvedPathname | null;
		nextHref: ResolvedPathname | null;
		calendar: DateCalendar | null;
		layout: RowLayout;
		gameHref: (id: string) => ResolvedPathname;
		teamHref: (code: string) => ResolvedPathname;
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let {
		state: page,
		allGamesHref,
		standingsHref,
		previousHref,
		nextHref,
		calendar,
		layout,
		gameHref,
		teamHref
	}: Props = $props();

	const CARDS = [0, 1, 2]; // placeholder game cards
	let openId = $state<string | null>(null);
	let playingId = $state<string | null>(null);

	function toggle(id: string) {
		openId = openId === id ? null : id;
		playingId = null;
	}
</script>

{#if page.kind === 'ready'}
	<DayHeader
		view={page.view}
		{allGamesHref}
		{standingsHref}
		{previousHref}
		{nextHref}
		{calendar}
		{layout}
	/>
	<section class="page-section">
		{#if page.view.games.length > 0}
			<div class="head"><Kicker text={m.past_day_title()} /></div>
			<ul class="games" aria-label={m.past_day_games({ date: page.view.title })}>
				{#each page.view.games as game (game.id)}
					<li>
						<GameCard
							{game}
							{layout}
							spoilerFree={false}
							open={openId === game.id}
							onToggle={() => toggle(game.id)}
							playingVideoId={openId === game.id ? playingId : null}
							onPlay={(videoId) => (playingId = videoId)}
							detailHref={gameHref(game.id)}
							{teamHref}
						/>
					</li>
				{/each}
			</ul>
		{:else}
			<MessageRow text={m.schedule_no_games()} />
		{/if}
	</section>
{:else if page.kind === 'loading'}
	<DayHeader
		view={null}
		loading
		{allGamesHref}
		{standingsHref}
		previousHref={null}
		nextHref={null}
		calendar={null}
		{layout}
	/>
	<section class="page-section" aria-busy="true">
		<ul class="games bones" aria-hidden="true" use:play={shimmer}>
			{#each CARDS as i (i)}
				<li>
					<BlueprintFrame>
						<div class="card-bone"><span class="bone"></span></div>
					</BlueprintFrame>
				</li>
			{/each}
		</ul>
	</section>
{:else}
	<DayHeader
		view={null}
		{allGamesHref}
		{standingsHref}
		previousHref={null}
		nextHref={null}
		calendar={null}
		{layout}
	/>
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

	.head {
		margin-bottom: var(--game-list-gap);
	}

	.games {
		display: grid;
		gap: var(--game-list-gap);
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.card-bone {
		padding: var(--game-list-gap);
	}

	.bone {
		display: block;
		width: 100%;
		height: var(--monogram-size);
		background: var(--color-surface);
		border-radius: var(--radius);
	}
</style>
