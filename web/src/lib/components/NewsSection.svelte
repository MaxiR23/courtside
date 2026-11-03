<script lang="ts">
	// The News section of a team, player or game page (docs/design-news.md). While the notes load it
	// holds bones and no tab; a null block is not drawn by the page.
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import NewsCard from '#lib/components/NewsCard.svelte';
	import NewsRows from '#lib/components/NewsRows.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';
	import { play } from '#lib/hero/motion.ts';
	import type { NewsBlock } from '#lib/news/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		id: string; // the anchor of the tab
		title: string;
		block: Exclude<NewsBlock, null>;
		shape: 'feature-rows' | 'rows' | 'feature'; // team: newest as feature then rows; player: rows; game: one feature
		columns?: 1 | 2; // the rows' columns; default 1
		layout: RowLayout;
		noteHref: (id: string) => ResolvedPathname;
	};

	let { id, title, block, shape, columns = 1, layout, noteHref }: Props = $props();
</script>

<section {id} aria-busy={block.kind === 'loading'}>
	<SectionHead {title} />
	{#if block.kind === 'loading'}
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			<BlueprintFrame><SkeletonBone aspect="var(--news-photo-aspect)" /></BlueprintFrame>
		</div>
	{:else if shape === 'rows'}
		<NewsRows cards={block.notes} {columns} rowLayout={layout} {noteHref} />
	{:else}
		<NewsCard card={block.notes[0]} layout="feature" rowLayout={layout} {noteHref} />
		{#if shape === 'feature-rows' && block.notes.length > 1}
			<NewsRows cards={block.notes.slice(1)} {columns} rowLayout={layout} {noteHref} />
		{/if}
	{/if}
</section>

<style>
	section {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
	}
</style>
