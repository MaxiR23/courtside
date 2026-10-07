<script lang="ts">
	import { resolve } from '$app/paths';
	import { onMount, tick } from 'svelte';
	import Hero from '#lib/components/Hero.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import Schedule from '#lib/components/Schedule.svelte';
	import ScheduleSkeleton from '#lib/components/ScheduleSkeleton.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import { gamesFeedUrl, videoPlatformName } from '#lib/feed/config.ts';
	import { loadGamesFeed } from '#lib/feed/load.ts';
	import { GamesFeedPoller } from '#lib/feed/poller.svelte.ts';
	import { toHomeView } from '#lib/feed/props.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { cardAnchor } from '#lib/schedule/layout.ts';
	import { SpoilerFree } from '#lib/schedule/spoiler-free.svelte.ts';

	const url = gamesFeedUrl;
	const poller = url ? new GamesFeedPoller(() => loadGamesFeed(url)) : undefined;
	const spoilerFree = new SpoilerFree();
	const gameHref = (id: string) => resolve('/game/[id]', { id });

	$effect(() => poller?.start());
	$effect(() => spoilerFree.load());

	const view = $derived(
		poller?.feed && poller.receivedAt
			? toHomeView(poller.feed, poller.receivedAt, { videoPlatformName })
			: null
	);
	// No URL, a failed first load, or a feed the props layer rejects. While the first load is
	// pending the page is neither available nor unavailable: see `loading`.
	const unavailable = $derived(
		!url || (view === null && (poller?.failed === true || poller?.feed != null))
	);

	// The first load is pending: the hero and the schedule show their skeletons.
	const loading = $derived(!unavailable && view === null);

	// The nav row date until a feed is in. Set in the browser only, so no build-time date is
	// baked into the prerendered page.
	let clockToday = $state<Date | null>(null);
	onMount(() => {
		clockToday = new Date();
	});
	const today = $derived(view?.today ?? clockToday);

	let selected = $state(3);
	let openId = $state<string | null>(null);

	async function matchDetails(id: string) {
		selected = 3;
		openId = id;
		await tick();
		const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
		document
			.getElementById(cardAnchor(id))
			?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
	}
</script>

{#if today}
	<Hero
		games={view?.heroGames ?? []}
		{today}
		{loading}
		scheduleHref={resolve('/#schedule')}
		onMatchDetails={matchDetails}
		spoilerFree={spoilerFree.on}
		onSpoilerFreeToggle={() => spoilerFree.toggle()}
	/>
{/if}

{#if view}
	<Schedule
		days={view.days}
		updatedMinutesAgo={view.updatedMinutesAgo}
		bind:selected
		bind:openId
		spoilerFree={spoilerFree.on}
		{gameHref}
	/>
{:else if unavailable}
	<section class="unavailable" id="schedule">
		<MessageRow text={m.feed_unavailable()} />
	</section>
{:else if loading}
	<ScheduleSkeleton />
{/if}

<SiteFooter />

<style>
	.unavailable {
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
	}
</style>
