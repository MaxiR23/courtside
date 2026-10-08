<script lang="ts">
	import type { RecordSection } from '#lib/team/types.ts';

	type Props = { record: RecordSection };

	let { record }: Props = $props();
</script>

<div class="record">
	<div class="large">
		{#each record.large as cell (cell.label)}
			<div class="cell">
				<span class="label">{cell.label}</span>
				<span class="value">{cell.value}</span>
				{#if cell.sub}<span class="sub">{cell.sub}</span>{/if}
			</div>
		{/each}
	</div>
	<div class="detail">
		{#each record.detail as cell (cell.label)}
			<div class="cell">
				<span class="label">{cell.label}</span>
				<span class="value">{cell.value}</span>
				{#if cell.sub}<span class="sub">{cell.sub}</span>{/if}
			</div>
		{/each}
	</div>
</div>

<style>
	.record {
		display: grid;
		gap: var(--panel-section-gap);
	}

	.large,
	.detail {
		display: grid;
		gap: var(--game-list-gap);
	}

	.large {
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--team-record-cell-min)), 1fr));
	}

	.detail {
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--team-detail-cell-min)), 1fr));
	}

	.cell {
		display: flex;
		flex-direction: column;
		gap: var(--day-strip-gap);
		padding-top: var(--game-list-gap);
		border-top: var(--hairline) solid var(--color-divider);
	}

	.label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.value {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-variant-numeric: tabular-nums;
	}

	.large .value {
		font-size: var(--team-record-value-size);
		line-height: 1;
	}

	.detail .value {
		font-size: var(--detail-info-value-size);
	}

	.sub {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}
</style>
