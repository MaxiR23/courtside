<script lang="ts">
	// The tags of a note: its kind, its team, EN for an English note in Spanish, then its date.
	import Tag from '#lib/components/Tag.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { NewsCardView } from '#lib/news/types.ts';

	type Props = {
		card: NewsCardView;
		date?: boolean; // default true: the date after the tags; false: the row draws it apart
	};

	let { card, date = true }: Props = $props();
</script>

<span class="tags">
	<Tag variant={card.kind === 'recap' ? 'accent' : 'muted'} text={card.kindLabel} />
	{#if card.teamTag}<Tag text={card.teamTag} />{/if}
	{#if card.english}<Tag text={m.news_english()} />{/if}
	{#if date}<span class="date">{card.date}</span>{/if}
</span>

<style>
	.tags {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--day-strip-gap);
	}

	.date {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}
</style>
