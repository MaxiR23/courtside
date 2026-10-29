<script lang="ts">
	// SEE: docs/design-cup.md ("Bracket > Mobile (under 680px)")
	import type { ResolvedPathname } from '$app/types';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { SlotId } from '#lib/contract/cup.ts';
	import { TREE_ROWS } from '#lib/cup/bracket-layout.ts';
	import type { BracketNodeView, BracketSideView, BracketView } from '#lib/cup/types.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Props = {
		bracket: BracketView;
		gameHref: (id: string) => ResolvedPathname;
		onOpen: (id: SlotId, button: HTMLButtonElement) => void;
	};

	let { bracket, gameHref, onOpen }: Props = $props();

	const byId = $derived(new Map(bracket.nodes.map((node) => [node.id, node])));
	const name = (node: BracketNodeView) =>
		`${node.roundLabel} · ${node.top.name} · ${node.bottom.name}`;
	const loserOf = (side: BracketSideView, other: BracketSideView): boolean =>
		other.winner && !side.winner;
</script>

{#snippet body(node: BracketNodeView)}
	{#if node.date}<span class="date">{node.date}</span>{/if}
	{#each [node.top, node.bottom] as side, i (i)}
		{@const other = i === 0 ? node.bottom : node.top}
		<span class="side" class:loser={loserOf(side, other)}>
			{#if side.team}
				<span class="mark"
					><TeamMark team={side.team} part="tile" size="fill" logo={side.team.logo} /></span
				>
				<span class="code"><TeamMark team={side.team} part="label" /></span>
			{:else}
				<span class="empty-tile" aria-hidden="true"></span>
				<span class="open">
					<span class="slot-label">{side.label ?? side.name}</span>
					<span class="rule-text">{side.rule}</span>
				</span>
			{/if}
			{#if side.score !== null}<span class="score">{side.score}</span>{/if}
		</span>
	{/each}
	{#if node.rule}
		<span
			class="winner-line"
			style:--side-accent={node.rule.accent ?? 'var(--identity-neutral-accent)'}
		></span>
	{/if}
{/snippet}

<div class="tree" role="group" aria-label={m.cup_bracket()}>
	<SectionHead
		kicker={bracket.kicker}
		title={m.cup_knockout_rounds()}
		titleSize="var(--cup-tree-title-size)"
		kickerSize="var(--cup-tree-kicker-size)"
		kickerGap="var(--cup-tree-gap)"
	/>
	<div class="conferences">
		<span>{m.game_conference_east()}</span><span>{m.game_conference_west()}</span>
	</div>
	{#each TREE_ROWS as row (row.key)}
		<div class="row">
			<p class="row-label" class:final={row.key === 'championship'}>
				{bracket.treeLabels[row.key]}
			</p>
			<ol class="grid">
				{#each row.cards as place (place.id)}
					{@const node = byId.get(place.id)}
					{#if node}
						<li class="cell" style:grid-column={place.column}>
							{#if node.gameLink?.linked}
								<a
									class="card"
									class:final={node.final}
									href={gameHref(node.gameLink.gameId)}
									aria-label={name(node)}>{@render body(node)}</a
								>
							{:else}
								<button
									type="button"
									class="card"
									class:final={node.final}
									aria-label={name(node)}
									onclick={(event) => onOpen(node.id, event.currentTarget)}
									>{@render body(node)}</button
								>
							{/if}
						</li>
					{/if}
				{/each}
			</ol>
		</div>
	{/each}
</div>

<style>
	.tree {
		display: grid;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.row {
		display: grid;
		gap: var(--cup-tree-gap);
	}

	.conferences {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		padding-bottom: var(--cup-tree-gap);
		border-bottom: var(--hairline) solid var(--color-divider);
		font-size: var(--cup-tree-conference-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
		text-align: center;
	}

	.row-label {
		margin: 0;
		text-align: center;
		font-size: var(--cup-tree-label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.row-label.final {
		color: var(--color-accent-light);
	}

	.grid {
		display: grid;
		grid-template-columns: var(--cup-tree-columns);
		gap: var(--cup-tree-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.cell {
		min-width: 0;
		display: grid;
	}

	.card {
		display: grid;
		align-content: start;
		gap: var(--cup-tree-side-gap);
		box-sizing: border-box;
		width: 100%;
		min-width: 0;
		padding: var(--cup-tree-card-padding);
		border: var(--hairline) solid var(--cup-tree-card-border);
		border-radius: var(--radius);
		background: var(--cup-tree-card-bg);
		color: var(--color-ink);
		font: inherit;
		text-align: left;
		text-decoration: none;
		cursor: pointer;
	}

	.card.final {
		padding: var(--cup-tree-final-padding);
		border-color: var(--cup-tree-final-border);
	}

	.date {
		overflow: hidden;
		font-size: var(--cup-tree-date-size);
		text-transform: uppercase;
		color: var(--color-muted);
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.side {
		display: grid;
		grid-template-columns: var(--cup-tree-logo) minmax(0, 1fr) auto;
		align-items: center;
		gap: var(--cup-tree-side-gap);
		min-width: 0;
	}

	.final .side {
		grid-template-columns: var(--cup-tree-final-logo) minmax(0, 1fr) auto;
	}

	.loser {
		opacity: var(--cup-tree-loser-opacity);
	}

	.mark,
	.empty-tile {
		width: var(--cup-tree-logo);
		height: var(--cup-tree-logo);
	}

	.final .mark,
	.final .empty-tile {
		width: var(--cup-tree-final-logo);
		height: var(--cup-tree-final-logo);
	}

	.empty-tile {
		box-sizing: border-box;
		border: var(--hairline) dashed var(--color-divider);
	}

	.code,
	.score {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--cup-tree-code-size);
		line-height: 1;
	}

	.final .code,
	.final .score {
		font-size: var(--cup-tree-final-code-size);
	}

	.code {
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.score {
		font-variant-numeric: tabular-nums;
	}

	.open {
		display: grid;
		min-width: 0;
	}

	.slot-label,
	.rule-text {
		overflow: hidden;
		font-size: var(--cup-tree-date-size);
		color: var(--color-muted);
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.winner-line {
		display: block;
		height: var(--cup-tree-rule);
		background: var(--side-accent);
	}
</style>
