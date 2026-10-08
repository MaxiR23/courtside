<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import type { AwardView } from '#lib/player/types.ts';

	type Props = { awards: AwardView[] };

	let { awards }: Props = $props();
</script>

<ul class="awards">
	{#each awards as award, i (i)}
		<li>
			<BlueprintFrame>
				<div class="award">
					<span class="count">{award.count}</span>
					<div class="text">
						<span class="name">{award.name}</span>
						<span class="seasons">{award.seasons}</span>
					</div>
				</div>
			</BlueprintFrame>
		</li>
	{/each}
</ul>

<style>
	.awards {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--player-award-column-min)), 1fr));
		gap: var(--game-list-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.award {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-height: 100%;
		padding: var(--game-list-gap);
	}

	.count {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--player-award-count-size);
		line-height: 1;
		color: var(--color-accent-light);
		font-variant-numeric: tabular-nums;
	}

	.text {
		display: grid;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--player-award-name-size);
		text-transform: uppercase;
	}

	.seasons {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}
</style>
