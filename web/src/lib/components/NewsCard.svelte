<script lang="ts">
	// A note, drawn in one of three layouts. The only place a note is drawn (docs/design-news.md).
	// A photo that fails to load is dropped with its wrapper, so the card falls back to text only.
	// The headline is an h3 unless a page asks for another level.
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import NewsPhoto from '#lib/components/NewsPhoto.svelte';
	import NewsTags from '#lib/components/NewsTags.svelte';
	import type { NewsCardView } from '#lib/news/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		card: NewsCardView;
		layout: 'card' | 'row' | 'feature';
		rowLayout: RowLayout; // the feature stacks its photo above its text on mobile
		noteHref: (id: string) => ResolvedPathname;
		headingLevel?: 2 | 3; // the headline's heading level
	};

	let { card, layout, rowLayout, noteHref, headingLevel = 3 }: Props = $props();

	// Keyed by photo URL, so a new URL tries again after a failure.
	let failedPhoto = $state<string | null>(null);
	const fail = () => (failedPhoto = card.photo?.url ?? null);
	const showPhoto = $derived(!!card.photo && card.photo.url !== failedPhoto);
</script>

{#snippet link()}
	<a
		class="note {layout}"
		class:stacked={layout === 'feature' && rowLayout === 'mobile'}
		class:text-only={!showPhoto}
		href={noteHref(card.id)}
	>
		{#if layout === 'row'}
			{#if showPhoto}<div class="thumb">
					<NewsPhoto photo={card.photo} alt={card.headline} onFail={fail} />
				</div>{/if}
			<div class="text">
				<NewsTags {card} date={false} />
				<svelte:element this={`h${headingLevel}`} class="headline">{card.headline}</svelte:element>
				{#if card.description}<p class="description">{card.description}</p>{/if}
			</div>
			<span class="row-date">{card.date}</span>
		{:else}
			{#if showPhoto}<div class="photo">
					<NewsPhoto photo={card.photo} alt={card.headline} onFail={fail} />
				</div>{/if}
			<div class="text">
				<NewsTags {card} />
				<svelte:element this={`h${headingLevel}`} class="headline">{card.headline}</svelte:element>
				{#if card.description}<p class="description">{card.description}</p>{/if}
			</div>
		{/if}
	</a>
{/snippet}

{#if layout === 'row'}
	{@render link()}
{:else}
	<BlueprintFrame hoverable>{@render link()}</BlueprintFrame>
{/if}

<style>
	.note {
		display: grid;
		align-content: start;
		min-width: 0;
		color: var(--color-ink);
		text-decoration: none;
	}

	.photo,
	.thumb {
		display: block;
		min-width: 0;
	}

	.text {
		display: grid;
		align-content: start;
		gap: var(--day-strip-gap);
		min-width: 0;
		padding: var(--game-list-gap);
	}

	.headline {
		margin: 0;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		line-height: var(--news-headline-line-height);
		text-transform: uppercase;
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: var(--news-line-clamp-headline);
		line-clamp: var(--news-line-clamp-headline);
		overflow: hidden;
	}

	.description {
		margin: 0;
		font-size: var(--body-size);
		color: var(--color-muted);
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: var(--news-card-description-lines);
		line-clamp: var(--news-card-description-lines);
		overflow: hidden;
	}

	.note:hover .headline {
		color: var(--color-accent-hover);
	}

	.card .headline {
		font-size: var(--news-card-headline-size);
	}

	.feature {
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		align-items: center;
	}

	.feature.stacked,
	.feature.text-only {
		grid-template-columns: minmax(0, 1fr);
	}

	.feature .headline {
		font-size: var(--news-feature-headline-size);
	}

	.row {
		grid-template-columns: var(--news-row-thumb-width) minmax(0, 1fr) auto;
		align-items: start;
		gap: var(--game-list-gap);
		padding-block: var(--game-list-gap);
		border-top: var(--hairline) solid var(--color-divider);
	}

	.row.text-only {
		grid-template-columns: minmax(0, 1fr) auto;
	}

	.row .text {
		padding: 0;
	}

	.row .headline {
		font-size: var(--news-card-headline-size);
	}

	.row .description {
		-webkit-line-clamp: var(--news-row-description-lines);
		line-clamp: var(--news-row-description-lines);
	}

	.row-date {
		font-size: var(--caption-size);
		color: var(--color-muted);
		white-space: nowrap;
	}
</style>
