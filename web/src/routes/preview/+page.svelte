<script lang="ts">
	import PageMeta from '#lib/components/PageMeta.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<PageMeta noindex />

<data.Preview />
