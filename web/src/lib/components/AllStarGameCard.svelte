<script lang="ts">
	import AllStarLiveDot from '#lib/components/AllStarLiveDot.svelte';
	import AllStarSigla from '#lib/components/AllStarSigla.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { GameCardView } from '#lib/all-star/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import Kicker from '#lib/components/Kicker.svelte';
	import Tag from '#lib/components/Tag.svelte';

	type Props = {
		card: GameCardView;
		selected: boolean;
		layout: RowLayout;
		onSelect: (id: string) => void;
	};

	let { card, selected, layout, onSelect }: Props = $props();
</script>

<button
	type="button"
	class="game-card"
	class:selected
	class:mobile={layout === 'mobile'}
	aria-pressed={selected}
	onclick={() => onSelect(card.id)}
>
	<span class="top">
		{#if card.round}
			<Tag text={card.round.text} variant={card.round.championship ? 'solid' : 'muted'} />
		{/if}
		<Kicker tone="muted" contents
			><span class="status {card.status.kind}">
				{#if card.status.kind === 'live'}<AllStarLiveDot />{/if}
				<span class="status-text">{card.status.text}</span>
			</span></Kicker
		>
	</span>
	<span class="label">{card.label}</span>
	<span class="rows">
		{#each card.rows as row, i (i)}
			<span class="row" class:loser={row.loser}>
				<AllStarSigla team={row.team} size="small" winner={row.winner} />
				<span class="name">
					{#if row.team}<TeamMark team={row.team} part="name" />{:else}{row.name}{/if}
				</span>
				<span class="score">{row.score}</span>
			</span>
		{/each}
	</span>
</button>

<style>
	.game-card {
		display: grid;
		align-content: start;
		gap: var(--game-list-gap);
		min-width: 0;
		padding: var(--game-list-gap);
		border: 0;
		border-left: var(--hairline) solid var(--color-divider);
		background: none;
		font: inherit;
		color: var(--color-ink);
		text-align: left;
		cursor: pointer;
	}

	.game-card:hover {
		background: var(--allstar-card-hover);
	}

	.game-card.selected {
		background: var(--allstar-card-selected);
		box-shadow: inset 0 calc(-1 * var(--allstar-card-bar)) 0 var(--color-accent-light);
	}

	.game-card.mobile {
		flex: 0 0 var(--allstar-card-mobile);
		scroll-snap-align: start;
	}

	.game-card.mobile.selected {
		box-shadow: inset 0 0 0 var(--hairline) var(--color-accent-light);
	}

	.top {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--day-strip-gap);
	}

	.status {
		display: inline-flex;
		align-items: center;
		gap: var(--day-strip-gap);
	}

	.status.live {
		color: var(--color-accent-light);
	}

	.label {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.rows {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.row {
		display: flex;
		align-items: center;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	.row.loser {
		color: var(--color-muted);
	}

	.name {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--allstar-card-name-size);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.score {
		font-family: var(--font-heading);
		font-size: var(--allstar-card-score-size);
		font-variant-numeric: tabular-nums;
	}
</style>
