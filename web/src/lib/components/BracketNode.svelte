<script lang="ts">
	import Tag from '#lib/components/Tag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { BracketNodeView, BracketSideView } from '#lib/cup/types.ts';
	import type { SlotId } from '#lib/contract/cup.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Props = {
		node: BracketNodeView;
		level: 1 | 2;
		onOpen: (id: SlotId, button: HTMLButtonElement) => void;
		onFocusChange: (focused: boolean) => void;
	};

	let { node, level, onOpen, onFocusChange }: Props = $props();

	const sides = $derived<BracketSideView[]>([node.top, node.bottom]);
	const name = $derived(`${node.roundLabel} · ${node.top.name} · ${node.bottom.name}`);
	const loserOf = (side: BracketSideView, other: BracketSideView): boolean =>
		other.winner && !side.winner;
</script>

<button
	type="button"
	class="node"
	class:mirrored={node.mirrored}
	class:final={node.final}
	aria-label={name}
	onclick={(event) => onOpen(node.id, event.currentTarget)}
	onfocus={(event) => onFocusChange(event.currentTarget.matches(':focus-visible'))}
	onblur={() => onFocusChange(false)}
>
	{#each sides as side, i (i)}
		<span class="side" class:winner={side.winner} class:loser={loserOf(side, sides[1 - i])}>
			{#if level === 1}
				{#if side.team}
					<span class="code"
						><TeamMark
							team={side.team}
							part="tile"
							size="cup-node"
							logo={side.team.logo}
						/><TeamMark team={side.team} part="label" /></span
					>
				{:else if side.label !== null}
					<span class="slot-label">{side.label}</span>
				{/if}
				{#if side.score !== null}<span class="score">{side.score}</span>{/if}
			{:else}
				{#if side.team}
					<TeamMark team={side.team} part="tile" size="cup-node" logo={side.team.logo} />
				{:else}
					<span class="empty-tile"></span>
				{/if}
				<span class="who">
					<span class="name">{side.name}</span>
					{#if side.team}
						{#if side.meta}<span class="meta">{side.meta}</span>{/if}
					{:else}
						<span class="meta"
							>{[side.label, side.rule].filter((part) => part !== null).join(' · ')}</span
						>
						{#if side.currently}<span class="meta">{side.currently}</span>{/if}
					{/if}
				</span>
				{#if side.score !== null}<span class="score">{side.score}</span>{/if}
			{/if}
		</span>
	{/each}
	{#if level === 2 && (node.date || node.venue || node.broadcast || node.neutral)}
		<span class="footer">
			{#if node.date}<span class="meta">{node.date}</span>{/if}
			{#if node.venue}<span class="meta">{node.venue}</span>{/if}
			<!-- A tag at the page's 11px would be unreadable in the scaled world, so it takes the bracket's sizes. -->
			{#if node.neutral}<Tag
					text={m.cup_neutral()}
					size="var(--bracket-meta-size)"
					tracking="var(--label-letter-spacing)"
					padding="var(--hairline) var(--bracket-tick-size)"
					wrap="nowrap"
				/>{/if}
			{#if node.broadcast}<span class="meta">{node.broadcast}</span>{/if}
		</span>
	{/if}
</button>

<style>
	.node {
		display: grid;
		align-content: center;
		gap: var(--bracket-node-padding);
		box-sizing: border-box;
		width: var(--bracket-node-width);
		height: var(--bracket-node-height);
		padding: var(--bracket-node-padding);
		border: 0;
		border-radius: var(--radius);
		background: var(--bracket-node-bg);
		color: var(--color-ink);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	/* The frame and the focus ring are drawn in the connectors layer. */
	.node:focus-visible {
		outline: none;
	}

	.side {
		display: flex;
		align-items: center;
		gap: var(--bracket-node-padding);
		min-width: 0;
	}

	.mirrored .side {
		flex-direction: row-reverse;
		text-align: right;
	}

	.loser {
		color: var(--color-muted);
	}

	.code,
	.score {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		line-height: 1;
	}

	.code {
		display: flex;
		align-items: center;
		gap: var(--bracket-node-padding);
		flex: 1;
		min-width: 0;
		font-size: var(--bracket-code-size);
	}

	.score {
		font-size: var(--bracket-score-size);
		font-variant-numeric: tabular-nums;
	}

	.slot-label {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--bracket-label-size);
		color: var(--color-muted);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.empty-tile {
		flex: none;
		box-sizing: border-box;
		width: var(--bracket-tile-size);
		height: var(--bracket-tile-size);
		border: var(--hairline) dashed var(--color-divider);
	}

	.who {
		display: grid;
		flex: 1;
		gap: var(--hairline);
		min-width: 0;
	}

	.name {
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--bracket-name-size);
		line-height: 1;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.meta {
		overflow: hidden;
		font-size: var(--bracket-meta-size);
		color: var(--color-muted);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.footer {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--bracket-node-padding);
		min-width: 0;
	}

	.mirrored .footer {
		flex-direction: row-reverse;
	}
</style>
