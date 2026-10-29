<script lang="ts">
	import ProfileCells from '#lib/components/ProfileCells.svelte';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { MilestonesSection } from '#lib/player/types.ts';

	type Props = { milestones: MilestonesSection; layout: RowLayout };

	let { milestones, layout }: Props = $props();
</script>

<ProfileCells
	cells={milestones.cells}
	min="var(--player-milestone-cell-min)"
	columns={layout === 'mobile' ? 2 : null}
	numeric
	keepEmpty
/>
