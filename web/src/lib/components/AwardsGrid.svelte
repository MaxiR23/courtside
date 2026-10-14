<script lang="ts">
	import AwardCard from '#lib/components/AwardCard.svelte';
	import type { AwardView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = { awards: AwardView[]; layout: RowLayout };

	let { awards, layout }: Props = $props();
</script>

<ul class="awards-grid" class:mobile={layout === 'mobile'}>
	{#each awards as award (award.key)}
		<li class="item"><AwardCard {award} /></li>
	{/each}
</ul>

<style>
	.awards-grid {
		display: grid;
		grid-template-columns: repeat(
			auto-fill,
			minmax(min(100%, var(--playoffs-award-card-min)), 1fr)
		);
		gap: var(--panel-section-gap) var(--game-list-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.awards-grid.mobile {
		display: flex;
		overflow-x: auto;
		scroll-snap-type: x mandatory;
		gap: var(--game-list-gap);
	}

	.mobile .item {
		flex: 0 0 var(--playoffs-award-card-mobile);
		scroll-snap-align: start;
	}

	.item {
		min-width: 0;
	}
</style>
