<script lang="ts">
	// The home's news: a carousel of the latest notes with previous and next buttons. Nothing is
	// drawn for a null block. SEE: docs/design-news.md
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Button from '#lib/components/Button.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import NewsCard from '#lib/components/NewsCard.svelte';
	import PageContainer from '#lib/components/PageContainer.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { carouselIndex } from '#lib/news/carousel.ts';
	import type { NewsBlock } from '#lib/news/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		block: NewsBlock;
		layout: RowLayout;
		seeAllHref: ResolvedPathname;
		noteHref: (id: string) => ResolvedPathname;
	};

	let { block, layout, seeAllHref, noteHref }: Props = $props();

	const headingId = $props.id();
	let track = $state<HTMLElement>();
	let index = $state(0);
	const count = $derived(block?.kind === 'ready' ? block.notes.length : 0);

	// The distance between the first two cards, from their positions.
	function step(): number {
		const cards = track?.querySelectorAll<HTMLElement>('li');
		if (!cards || cards.length < 2) return track?.clientWidth ?? 0;
		return cards[1].offsetLeft - cards[0].offsetLeft;
	}

	function scrollBy(direction: 1 | -1) {
		const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
		track?.scrollBy({ left: direction * step(), behavior: reduced ? 'auto' : 'smooth' });
	}

	function onscroll() {
		if (track) {
			index = carouselIndex(track.scrollLeft, step(), count, track.scrollWidth - track.clientWidth);
		}
	}
</script>

{#if block}
	<PageContainer>
		<section class="home-news" class:mobile={layout === 'mobile'} aria-labelledby={headingId}>
			<header>
				<SectionHead title={m.news_title()} kicker={m.news_kicker()} size="home" id={headingId} />
				{#if block.kind === 'ready'}
					<div class="controls">
						<a class="all" href={seeAllHref}><Kicker tone="inherit" text={m.news_see_all()} /></a>
						<Button
							variant="secondary"
							label={m.news_previous()}
							ariaLabel={m.news_previous_label()}
							disabled={index <= 0}
							onclick={() => scrollBy(-1)}
						/>
						<Button
							variant="secondary"
							label={m.news_next()}
							ariaLabel={m.news_next_label()}
							disabled={index >= count - 1}
							onclick={() => scrollBy(1)}
						/>
					</div>
				{/if}
			</header>

			{#if block.kind === 'loading'}
				<div class="bones" aria-hidden="true" use:play={shimmer}>
					{#each [0, 1, 2] as bone (bone)}
						<div class="slot">
							<BlueprintFrame><SkeletonBone aspect="var(--news-photo-aspect)" /></BlueprintFrame>
						</div>
					{/each}
				</div>
			{:else}
				<ul class="track" bind:this={track} {onscroll}>
					{#each block.notes as card (card.id)}
						<li><NewsCard {card} layout="card" rowLayout={layout} {noteHref} /></li>
					{/each}
				</ul>
				<div class="indicator" aria-hidden="true">
					{#each block.notes as card, i (card.id)}
						<span class="bar" class:current={i === index}></span>
					{/each}
				</div>
			{/if}
		</section>
	</PageContainer>
{/if}

<style>
	.home-news {
		display: grid;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	header {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: var(--game-list-gap);
	}

	.controls {
		display: flex;
		align-items: center;
		gap: var(--day-strip-gap);
	}

	.all {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		margin-right: var(--day-strip-gap);
		color: var(--color-accent-light);
		text-decoration: none;
	}

	.all:hover {
		color: var(--color-accent-hover);
	}

	.track {
		display: flex;
		gap: var(--news-carousel-gap);
		margin: 0;
		padding: 0;
		list-style: none;
		overflow-x: auto;
		scroll-snap-type: x mandatory;
	}

	.track li {
		flex: 0 0 var(--news-card-width);
		scroll-snap-align: start;
	}

	.indicator {
		display: flex;
		gap: var(--day-strip-gap);
	}

	.bar {
		width: var(--news-indicator-width);
		height: var(--news-indicator-height);
		background: var(--color-divider);
	}

	.bar.current {
		background: var(--color-accent);
	}

	.bones {
		display: flex;
		gap: var(--news-carousel-gap);
		overflow: hidden;
	}

	.slot {
		flex: 0 0 var(--news-card-width);
	}
</style>
