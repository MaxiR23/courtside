<script lang="ts">
	import { resolve } from '$app/paths';
	import NavRow from '#lib/components/NavRow.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { wideViewport } from '#lib/schedule/layout.ts';

	const wide = wideViewport();
</script>

<header class="content">
	<NavRow
		page="standings"
		gamesHref={resolve('/')}
		standingsHref={resolve('/standings')}
		layout={wide.current ? 'desktop' : 'mobile'}
	/>
	<h1>{m.standings_title()}</h1>
</header>

<SiteFooter />

<style>
	.content {
		display: grid;
		gap: var(--panel-section-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--game-list-gap) var(--side-padding) var(--panel-section-gap);
	}

	h1 {
		margin: 0;
		font-size: var(--standings-h1-size);
	}
</style>
