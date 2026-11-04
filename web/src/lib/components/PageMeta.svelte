<script lang="ts">
	import { siteUrl } from '#lib/feed/config.ts';
	import { headTags, SHELL_MARK, tagKey } from '#lib/meta/head.ts';
	import { getLocale } from '#lib/paraglide/runtime.js';

	type Props =
		| {
				title: string; // the document title
				description: string; // one sentence on what the page shows
				path: string | null; // the page's pathname and query; null for no canonical address
				noindex?: false;
		  }
		| { noindex: true }; // the development-only preview: a robots tag and nothing else

	const props: Props = $props();

	const tags = $derived(
		props.noindex
			? []
			: headTags({
					title: props.title,
					description: props.description,
					path: props.path,
					siteUrl,
					locale: getLocale()
				})
	);

	// The server hook gives a browser-rendered page's file its tags (web/src/hooks.server.ts);
	// once this piece draws them, those copies go, so the page never carries two of each.
	$effect(() => {
		for (const el of document.head.querySelectorAll(`[${SHELL_MARK}]`)) el.remove();
	});
</script>

<svelte:head>
	{#if props.noindex}
		<meta name="robots" content="noindex" />
	{:else}
		<title>{props.title}</title>
		{#each tags as tag (tagKey(tag))}
			{#if tag.tag === 'link'}
				<link {...tag.attributes} />
			{:else}
				<meta {...tag.attributes} />
			{/if}
		{/each}
	{/if}
</svelte:head>
