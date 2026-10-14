<script lang="ts">
	import TitleBadge from '#lib/components/TitleBadge.svelte';
	import type { TitleView } from '#lib/playoffs/types.ts';

	type Props = { titles: TitleView[] };

	let { titles }: Props = $props();
</script>

<ul class="team-titles">
	{#each titles as title (title.text)}
		<li><TitleBadge {title} /></li>
	{/each}
</ul>

<style>
	.team-titles {
		display: flex;
		flex-wrap: wrap;
		gap: var(--playoffs-mark-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}
</style>
