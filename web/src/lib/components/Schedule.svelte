<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import DayStrip from '#lib/components/DayStrip.svelte';
	import GameCard from '#lib/components/GameCard.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import ScheduleEmptyDay from '#lib/components/ScheduleEmptyDay.svelte';
	import { formatDate, formatNumber } from '#lib/format/locale.ts';
	import type { EmptyDayView } from '#lib/home/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { ListEntrance } from '#lib/schedule/entrance.svelte.ts';
	import { cardAnchor, headerWraps, wideViewport } from '#lib/schedule/layout.ts';
	import { cardEntrance } from '#lib/schedule/motion.ts';
	import type { ScheduleDay } from '#lib/schedule/types.ts';

	type Props = {
		days: ScheduleDay[]; // seven days, today in the middle
		updatedMinutesAgo: number; // freshness, computed by the props layer
		selected?: number; // $bindable, default 3 (today)
		openId?: string | null; // $bindable, the id of the open card, so the page can open one
		spoilerFree?: boolean; // hides final scores until a card is opened
		gameHref: (id: string) => ResolvedPathname; // the detail page of a game
		teamHref: (code: string) => ResolvedPathname; // the page of a team
		emptyDay?: EmptyDayView | null; // the home with no games: the box in place of the no-games row
		windowHref?: (date: string) => ResolvedPathname; // a day of the games feed: /?day=YYYY-MM-DD
	};

	let {
		days,
		updatedMinutesAgo,
		selected = $bindable(3),
		openId = $bindable(null),
		spoilerFree = false,
		gameHref,
		teamHref,
		emptyDay = null,
		windowHref
	}: Props = $props();

	const wide = wideViewport();
	const entrance = new ListEntrance();
	const day = $derived(days[selected]);
	const games = $derived(day?.games ?? []);
	const heading = $derived(
		day ? formatDate(day.date, { weekday: 'long', month: 'long', day: 'numeric' }) : ''
	);
	const countLabel = $derived(m.schedule_game_count({ count: games.length }));
	const updated = $derived(
		updatedMinutesAgo < 1
			? m.schedule_updated_recently()
			: updatedMinutesAgo < 60
				? m.schedule_updated({ minutes: formatNumber(updatedMinutesAgo) })
				: m.schedule_updated_hours({ hours: formatNumber(Math.floor(updatedMinutesAgo / 60)) })
	);
	const strip = $derived(days.map((d) => ({ date: d.date, gameCount: d.games.length })));
	let list: HTMLElement | undefined = $state();
	let headerEl: HTMLElement | undefined = $state();
	let wrapped = $state(false);
	let playingId = $state<string | null>(null);

	$effect(() => {
		if (list) return entrance.observe(list);
	});

	// Whether .meta sits below .heading. No ResizeObserver (server, jsdom) leaves it false.
	$effect(() => {
		if (!headerEl || typeof ResizeObserver === 'undefined') return;
		const headingEl = headerEl.querySelector<HTMLElement>('.heading');
		const metaEl = headerEl.querySelector<HTMLElement>('.meta');
		if (!headingEl || !metaEl) return;
		const measure = () => {
			wrapped = headerWraps(headingEl, metaEl);
		};
		const observer = new ResizeObserver(measure);
		observer.observe(headerEl);
		observer.observe(headingEl);
		observer.observe(metaEl);
		measure();
		return () => observer.disconnect();
	});

	function toggle(id: string) {
		openId = openId === id ? null : id;
		playingId = null;
	}

	function select(i: number) {
		if (i === selected) return;
		playingId = null;
		selected = i;
		entrance.replay();
	}
</script>

<section class="schedule" id="schedule">
	<header class:mobile={!wide.current && wrapped} bind:this={headerEl}>
		<div class="heading">
			<Kicker text={m.schedule_kicker()} />
			<h2>
				{heading}
			</h2>
		</div>
		<div class="meta">
			<span class="count">{countLabel}</span>
			<span class="updated">
				{updated}
			</span>
		</div>
	</header>
	<DayStrip days={strip} {selected} compact={!wide.current} onSelect={select} />
	<div class="list" class:waiting={entrance.waiting} bind:this={list}>
		{#key entrance.run}
			{#if games.length > 0}
				<ul class="games">
					{#each games as game, i (game.id)}
						<li id={cardAnchor(game.id)} use:cardEntrance={{ index: i, run: entrance.run }}>
							<GameCard
								{game}
								{spoilerFree}
								layout={wide.current ? 'desktop' : 'mobile'}
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
			{:else if emptyDay && windowHref}
				<ScheduleEmptyDay view={emptyDay} {windowHref} />
			{:else}
				<MessageRow text={m.schedule_no_games()} />
			{/if}
		{/key}
	</div>
</section>

<style>
	.schedule {
		display: grid;
		gap: var(--game-list-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
	}

	.waiting {
		opacity: 0;
	}

	header {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: var(--game-list-gap);
	}

	.heading {
		display: grid;
	}

	h2 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--section-h2-size);
		line-height: var(--section-h2-line-height);
		text-transform: uppercase;
	}

	.meta {
		display: grid;
		justify-items: end;
	}

	.mobile .meta {
		justify-items: start;
	}

	.updated {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.games {
		display: grid;
		gap: var(--game-list-gap);
		list-style: none;
		padding: 0;
		margin: 0;
	}
</style>
