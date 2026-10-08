<script lang="ts">
	import type { ResolvedPathname } from '$app/types';

	type Props = { href: ResolvedPathname | null; text: string };

	let { href, text }: Props = $props();
</script>

{#if href}<a class="name-link" {href}>{text}</a>{:else}{text}{/if}

<style>
	.name-link {
		color: inherit;
		text-decoration: none;
	}

	.name-link:hover {
		color: var(--color-accent-hover);
	}
</style>
