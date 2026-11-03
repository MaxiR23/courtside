<script lang="ts">
	// The News page: the type filter, the team select, a grid of notes and Load more.
	// SEE: docs/design-news.md
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Button from '#lib/components/Button.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import NewsCard from '#lib/components/NewsCard.svelte';
	import PageContainer from '#lib/components/PageContainer.svelte';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import SegmentedControl from '#lib/components/SegmentedControl.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { filterByKind } from '#lib/feed/news-props.ts';
	import type { NewsKindFilter, NewsListState, NewsTeamOption } from '#lib/news/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		layout: RowLayout;
		list: NewsListState;
		filter: NewsKindFilter;
		onFilter: (filter: NewsKindFilter) => void;
		teams: NewsTeamOption[] | null; // null: the select is not drawn
		team: string; // 'all' or a lowercase team code
		onTeam: (team: string) => void;
		onLoadMore: () => void;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		noteHref: (id: string) => ResolvedPathname;
	};

	let {
		layout,
		list,
		filter,
		onFilter,
		teams,
		team,
		onTeam,
		onLoadMore,
		allGamesHref,
		standingsHref,
		noteHref
	}: Props = $props();

	const kinds = $derived([
		{ value: 'all', label: m.news_filter_all() },
		{ value: 'recap', label: m.news_filter_recaps() },
		{ value: 'news', label: m.news_filter_news() }
	]);
	const shown = $derived(list.kind === 'ready' ? filterByKind(list.cards, filter) : []);
</script>

{#snippet firstLine()}
	<Kicker text={m.news_kicker()} />
	<h1>{m.news_title()}</h1>
{/snippet}

<PageHeader
	nav={{ page: 'detail', gamesHref: allGamesHref, standingsHref }}
	{layout}
	busy={list.kind === 'loading'}
	first={firstLine}
/>
<PageContainer>
	<div class="content">
		{#if list.kind === 'unavailable'}
			<MessageRow text={m.feed_unavailable()} />
		{:else}
			<div class="controls">
				<SegmentedControl
					label={m.news_filter_label()}
					options={kinds}
					value={filter}
					onChange={(value) => onFilter(value as NewsKindFilter)}
				/>
				{#if teams}
					<select
						class="select"
						aria-label={m.news_team_label()}
						value={team}
						onchange={(event) => onTeam(event.currentTarget.value)}
					>
						<option value="all">{m.news_team_all()}</option>
						{#each teams as option (option.code)}
							<option value={option.code}>{option.label}</option>
						{/each}
					</select>
				{/if}
			</div>

			{#if list.kind === 'loading'}
				<div class="grid" aria-hidden="true" use:play={shimmer}>
					{#each [0, 1, 2] as bone (bone)}
						<BlueprintFrame><SkeletonBone aspect="var(--news-photo-aspect)" /></BlueprintFrame>
					{/each}
				</div>
			{:else if shown.length === 0}
				<MessageRow text={m.news_empty()} />
			{:else}
				<ul class="grid">
					{#each shown as card (card.id)}
						<li>
							<NewsCard {card} layout="card" rowLayout={layout} {noteHref} headingLevel={2} />
						</li>
					{/each}
				</ul>
			{/if}

			{#if list.kind === 'ready' && list.hasMore}
				<div class="more">
					<Button variant="secondary" label={m.news_load_more()} onclick={onLoadMore} />
				</div>
			{/if}
		{/if}
	</div>
</PageContainer>
<SiteFooter />

<style>
	h1 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--news-page-h1-size);
		line-height: var(--news-page-h1-line-height);
		text-transform: uppercase;
	}

	.content {
		display: grid;
		gap: var(--panel-section-gap);
	}

	.controls {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.select {
		height: var(--hit-target-size);
		max-width: 100%;
		padding: 0 var(--game-list-gap);
		border: var(--hairline) solid var(--past-select-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		color: var(--color-ink);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--past-select-size);
		letter-spacing: var(--past-select-letter-spacing);
		text-transform: uppercase;
		cursor: pointer;
	}

	.select:hover {
		border-color: var(--color-accent);
	}

	/* At most three columns: the minimum track width is never below a third of the row. */
	.grid {
		display: grid;
		grid-template-columns: repeat(
			auto-fill,
			minmax(
				min(100%, max(var(--news-card-min), calc((100% - 2 * var(--news-carousel-gap)) / 3))),
				1fr
			)
		);
		gap: var(--news-carousel-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.more {
		display: flex;
		justify-content: center;
	}
</style>
