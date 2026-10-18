<script lang="ts">
	import MirroredBar from '#lib/components/MirroredBar.svelte';
	import PostseasonAverages from '#lib/components/PostseasonAverages.svelte';
	import type { HeadToHeadView } from '#lib/playoffs/types.ts';

	type Props = { headToHead: HeadToHeadView };

	let { headToHead }: Props = $props();
</script>

<div class="head-to-head">
	<ul class="records">
		{#each headToHead.records as record (record.team)}
			<li class="record">
				<span class="team">{record.team}</span>
				<span class="value">{record.record}</span>
			</li>
		{/each}
	</ul>
	<div class="bars">
		{#each headToHead.bars as bar (bar.key)}
			<MirroredBar {bar} />
		{/each}
	</div>
	{#if headToHead.averages}
		<PostseasonAverages averages={headToHead.averages} />
	{/if}
</div>

<style>
	.head-to-head {
		display: grid;
		gap: var(--panel-section-gap);
		min-width: 0;
	}

	.records {
		display: flex;
		justify-content: space-between;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.record {
		display: flex;
		align-items: baseline;
		gap: var(--game-list-gap);
	}

	.team {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.value {
		font-family: var(--font-heading);
		font-size: var(--score-size-mobile);
		font-variant-numeric: tabular-nums;
	}

	.bars {
		display: grid;
		gap: var(--game-list-gap);
	}
</style>
