<script lang="ts">
	import InfoCell from '#lib/components/InfoCell.svelte';
	import type { InfoCell as InfoCellData } from '#lib/game/types.ts';

	type Props = {
		cells: InfoCellData[];
		min?: string; // a token reference for the narrowest column
		columns?: number | null; // a fixed column count in place of auto-fit; null: auto-fit
		list?: boolean; // a dl: each label a dt, each value a dd
		size?: 'detail' | 'hero' | 'record'; // forwarded to every cell
		strong?: boolean; // forwarded to every cell
		numeric?: boolean; // forwarded to every cell
		keepEmpty?: boolean; // render the empty grid element for an empty list
	};

	let {
		cells,
		min = 'var(--player-profile-cell-min)',
		columns = null,
		list = false,
		size = 'detail',
		strong = false,
		numeric = false,
		keepEmpty = false
	}: Props = $props();

	const columnCount = $derived(columns === null ? undefined : String(columns));
</script>

{#if cells.length > 0 || keepEmpty}
	<svelte:element
		this={list ? 'dl' : 'div'}
		class="cells"
		class:fixed={columns !== null}
		style:--cells-min={min}
		style:--cells-columns={columnCount}
	>
		{#each cells as cell (cell.label)}
			<InfoCell
				label={cell.label}
				value={cell.value}
				sub={cell.sub}
				{size}
				{strong}
				{numeric}
				term={list}
			/>
		{/each}
	</svelte:element>
{/if}

<style>
	.cells {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--cells-min)), 1fr));
		gap: var(--game-list-gap);
		align-content: start;
		margin: 0;
	}

	.fixed {
		grid-template-columns: repeat(var(--cells-columns), 1fr);
	}
</style>
