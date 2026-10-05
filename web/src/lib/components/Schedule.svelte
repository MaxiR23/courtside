<script lang="ts">
	import DayStrip from '#lib/components/DayStrip.svelte';
	import GameCard from '#lib/components/GameCard.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import { formatDate, formatNumber } from '#lib/format/locale.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { ListEntrance } from '#lib/schedule/entrance.svelte.ts';
	import { wideViewport } from '#lib/schedule/layout.ts';
	import { cardEntrance } from '#lib/schedule/motion.ts';
	import type { ScheduleDay } from '#lib/schedule/types.ts';

	type Props = {
		days: ScheduleDay[]; // seven days, today in the middle
		updatedMinutesAgo: number; // freshness, computed by the props layer
		selected?: number; // $bindable, default 3 (today)
	};

	let { days, updatedMinutesAgo, selected = $bindable(3) }: Props = $props();

	const wide = wideViewport();
	const entrance = new ListEntrance();
	const day = $derived(days[selected]);
	const games = $derived(day?.games ?? []);
	const heading = $derived(
		day ? formatDate(day.date, { weekday: 'long', month: 'long', day: 'numeric' }) : ''
	);
	const countLabel = $derived(m.schedule_game_count({ count: games.length }));
	const updated = $derived(m.schedule_updated({ minutes: formatNumber(updatedMinutesAgo) }));
	const strip = $derived(days.map((d) => ({ date: d.date, gameCount: d.games.length })));
	let list: HTMLElement | undefined = $state();
	let openId = $state<string | null>(null);
	let playingId = $state<string | null>(null);

	$effect(() => {
		if (list) return entrance.observe(list);
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

<section class="schedule">
	<header>
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
	<div class="list" bind:this={list}>
		{#key entrance.run}
			<ul class="games">
				{#each games as game, i (game.id)}
					<li use:cardEntrance={{ index: i, run: entrance.run }}>
						<GameCard
							{game}
							layout={wide.current ? 'desktop' : 'mobile'}
							open={openId === game.id}
							onToggle={() => toggle(game.id)}
							playingVideoId={openId === game.id ? playingId : null}
							onPlay={(videoId) => (playingId = videoId)}
						/>
					</li>
				{/each}
			</ul>
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
