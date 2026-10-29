<script lang="ts">
	import ProfileCells from '#lib/components/ProfileCells.svelte';
	import type { RecordSection } from '#lib/team/types.ts';

	type Props = { record: RecordSection };

	let { record }: Props = $props();
</script>

<div class="record">
	<ProfileCells
		cells={record.large}
		min="var(--team-record-cell-min)"
		size="record"
		strong
		numeric
		keepEmpty
	/>
	<ProfileCells cells={record.detail} min="var(--team-detail-cell-min)" strong numeric keepEmpty />
</div>

<style>
	.record {
		display: grid;
		gap: var(--panel-section-gap);
	}
</style>
