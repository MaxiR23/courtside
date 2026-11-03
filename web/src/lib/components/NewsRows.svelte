<script lang="ts">
	// A list of notes as rows, in one column or two.
	import type { ResolvedPathname } from '$app/types';
	import NewsCard from '#lib/components/NewsCard.svelte';
	import type { NewsCardView } from '#lib/news/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		cards: NewsCardView[];
		columns: 1 | 2;
		rowLayout: RowLayout;
		noteHref: (id: string) => ResolvedPathname;
	};

	let { cards, columns, rowLayout, noteHref }: Props = $props();
</script>

<ul class="rows" class:two={columns === 2}>
	{#each cards as card (card.id)}
		<li><NewsCard {card} layout="row" {rowLayout} {noteHref} /></li>
	{/each}
</ul>

<style>
	.rows {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		column-gap: var(--panel-section-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.rows.two {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
</style>
