<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import { resolve } from '$app/paths';
	import SearchOverlay from '#lib/components/SearchOverlay.svelte';
	import { searchFeedUrl } from '#lib/feed/config.ts';
	import { loadSearchFeed } from '#lib/feed/load.ts';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { wideViewport } from '#lib/schedule/layout.ts';
	import { SearchFeedStore } from '#lib/search/feed.svelte.ts';
	import { opensSearch } from '#lib/search/keys.ts';
	import { searchOverlay } from '#lib/search/overlay.svelte.ts';
	import favicon from '#lib/assets/favicon.svg';
	import '#lib/styles/tokens.css';
	import '#lib/styles/base.css';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	// The overlay lives here, not in a page: the index stays in memory across navigations.
	const url = searchFeedUrl;
	const searchFeed = new SearchFeedStore(url ? () => loadSearchFeed(url) : undefined);
	const wide = wideViewport();
	const teamHref = (code: string) => resolve('/team/[code]', { code: code.toLowerCase() });
	const playerHref = (id: string) => resolve('/player/[id]', { id });

	function onkeydown(event: KeyboardEvent) {
		if (!searchOverlay.open && opensSearch(event)) {
			event.preventDefault();
			searchOverlay.show();
		}
	}

	// The overlay sits above the page, so any navigation (back and forward too) closes it.
	afterNavigate(() => {
		if (searchOverlay.open) searchOverlay.close();
	});

	$effect(() => {
		document.documentElement.lang = getLocale();
	});
</script>

<svelte:window {onkeydown} />

<svelte:head>
	<link rel="icon" href={favicon} />
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
	<link
		rel="stylesheet"
		href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500&family=Barlow+Condensed:wght@400;500;600&display=swap"
	/>
</svelte:head>

{@render children()}

{#if searchOverlay.open}
	<SearchOverlay
		feed={searchFeed}
		layout={wide.current ? 'desktop' : 'mobile'}
		{teamHref}
		{playerHref}
		onClose={() => searchOverlay.close()}
	/>
{/if}
