<script lang="ts">
	// One note: its tags, headline, photo, text and the buttons to what it is about.
	// SEE: docs/design-news.md
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Button from '#lib/components/Button.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import NewsPhoto from '#lib/components/NewsPhoto.svelte';
	import NewsTags from '#lib/components/NewsTags.svelte';
	import PageContainer from '#lib/components/PageContainer.svelte';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';
	import { play } from '#lib/hero/motion.ts';
	import type { NewsArticleState } from '#lib/news/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		state: NewsArticleState;
		layout: RowLayout;
		newsHref: ResolvedPathname;
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
		teamHref: (code: string) => ResolvedPathname;
		gameHref: (id: string) => ResolvedPathname;
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let {
		state: page,
		layout,
		newsHref,
		allGamesHref,
		standingsHref,
		playerHref,
		teamHref,
		gameHref
	}: Props = $props();

	const mobile = $derived(layout === 'mobile');
</script>

{#snippet topBar()}
	<div class="top-bar">
		<a class="back" href={newsHref}>{m.news_back()}</a>
	</div>
{/snippet}

<PageHeader
	nav={{ page: 'detail', gamesHref: allGamesHref, standingsHref }}
	{layout}
	grid={null}
	divider={false}
	busy={page.kind === 'loading'}
	first={topBar}
/>
<PageContainer>
	<article class="content" class:mobile>
		{#if page.kind === 'ready'}
			{@const view = page.view}
			<header class="head">
				<NewsTags card={view.card} date={false} />
				<span class="full-date">{view.fullDate}</span>
				<h1>{view.card.headline}</h1>
			</header>
			{#if view.card.photo}
				<figure class="figure">
					<NewsPhoto photo={view.card.photo} alt={view.card.headline} />
					{#if view.credit}<figcaption>{view.credit}</figcaption>{/if}
				</figure>
			{/if}
			{#if view.card.description}<p class="body">{view.card.description}</p>{/if}

			{#if view.related.players.length || view.related.teams.length || view.related.game}
				<section class="related">
					<SectionHead title={m.news_related()} />
					<div class="buttons">
						{#if view.related.game}
							<Button
								variant="secondary"
								label={view.related.game.label}
								href={gameHref(view.related.game.id)}
								borderColor="var(--color-accent)"
							/>
						{/if}
						{#each view.related.teams as team (team.code)}
							<Button variant="secondary" label={team.label} href={teamHref(team.code)} />
						{/each}
						{#each view.related.players as player (player.id)}
							<Button variant="secondary" label={player.name} href={playerHref(player.id)} />
						{/each}
					</div>
				</section>
			{/if}
		{:else if page.kind === 'loading'}
			<div class="bones" aria-hidden="true" use:play={shimmer}>
				<SkeletonBone
					width="var(--skeleton-short-width)"
					height="var(--news-article-headline-size-mobile)"
				/>
				<BlueprintFrame><SkeletonBone aspect="var(--news-photo-aspect)" /></BlueprintFrame>
			</div>
		{:else if page.kind === 'unavailable'}
			<MessageRow text={m.feed_unavailable()} />
		{:else}
			<MessageRow text={m.news_not_found()} link={{ href: newsHref, label: m.news_back() }} />
		{/if}
	</article>
</PageContainer>
<SiteFooter />

<style>
	.top-bar {
		display: flex;
		align-items: center;
		min-height: var(--hit-target-size);
	}

	.back {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		font-size: var(--body-size);
		color: var(--color-accent-light);
	}

	.back:hover {
		color: var(--color-accent-hover);
	}

	.content {
		display: grid;
		gap: var(--panel-section-gap);
		max-width: var(--news-article-max-width);
		margin-inline: auto;
	}

	.head {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.full-date {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	h1 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--news-article-headline-size);
		line-height: var(--news-headline-line-height);
		text-transform: uppercase;
	}

	.mobile h1 {
		font-size: var(--news-article-headline-size-mobile);
	}

	.figure {
		display: grid;
		gap: var(--day-strip-gap);
		margin: 0;
	}

	.mobile .figure {
		margin-inline: calc(-1 * var(--side-padding));
	}

	figcaption {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.mobile figcaption {
		padding-inline: var(--side-padding);
	}

	.body {
		margin: 0;
		font-size: var(--news-article-body-size);
	}

	.mobile .body {
		font-size: var(--news-article-body-size-mobile);
	}

	.related {
		display: grid;
		gap: var(--game-list-gap);
	}

	.buttons {
		display: flex;
		flex-wrap: wrap;
		gap: var(--day-strip-gap);
	}
</style>
