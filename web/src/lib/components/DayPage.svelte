<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import DayHeader from '#lib/components/DayHeader.svelte';
	import GameCard from '#lib/components/GameCard.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import PageContainer from '#lib/components/PageContainer.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import type { DateCalendar } from '#lib/calendar/types.ts';
	import type { DayCardStats } from '#lib/day/card-stats.svelte.ts';
	import type { DayPageState } from '#lib/day/types.ts';
	import { cardDetails, withCardDetails } from '#lib/feed/day-props.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout, ScheduleGame } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';

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
		detailReads: DayCardStats; // the game detail reads of the cards opened
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
		teamHref,
		detailReads
	}: Props = $props();

	function cardDetailsOf(id: string) {
		const read = detailReads.feed(id);
		return read ? cardDetails(read) : null;
	}

	const CARDS = [0, 1, 2]; // placeholder game cards
	let openId = $state<string | null>(null);
	let playingId = $state<string | null>(null);

	function toggle(id: string, game: ScheduleGame) {
		const opening = openId !== id;
		openId = opening ? id : null;
		const details = game.details;
		if (
			opening &&
			details?.kind === 'final-without-stats' &&
			details.statsAvailability === 'available'
		) {
			detailReads.open(id);
		}
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
	<PageContainer>
		<section class="page-section">
			{#if page.view.games.length > 0}
				<div class="head"><Kicker text={m.past_day_title()} /></div>
				<ul class="games" aria-label={m.past_day_games({ date: page.view.title })}>
					{#each page.view.games as game (game.id)}
						<li>
							<GameCard
								game={withCardDetails(game, cardDetailsOf(game.id))}
								{layout}
								spoilerFree={false}
								open={openId === game.id}
								onToggle={() => toggle(game.id, game)}
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
	</PageContainer>
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
	<PageContainer>
		<section class="page-section" aria-busy="true">
			<ul class="games bones" aria-hidden="true" use:play={shimmer}>
				{#each CARDS as i (i)}
					<li>
						<BlueprintFrame>
							<div class="card-bone">
								<SkeletonBone width="100%" height="var(--monogram-size)" />
							</div>
						</BlueprintFrame>
					</li>
				{/each}
			</ul>
		</section>
	</PageContainer>
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
	<PageContainer>
		<section class="page-section">
			<MessageRow text={m.feed_unavailable()} />
		</section>
	</PageContainer>
{/if}

<SiteFooter />

<style>
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
</style>
