<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { PlayInSlotView, PlayInView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		playIn: PlayInView[];
		collapsed: boolean; // round 1 has started: only the titles and the outcomes
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		gameHref: (id: string) => ResolvedPathname;
	};

	let { playIn, collapsed, layout, teamHref, gameHref }: Props = $props();
</script>

{#snippet slotRow(side: PlayInSlotView, score: string | null)}
	<div class="slot" class:undecided={side.team === null}>
		{#if side.team}
			<TeamMark team={side.team} part="tile" size="standings" {teamHref} />
			<span class="slot-name">{side.label}</span>
		{:else}
			<span class="slot-text">
				<span class="slot-name">{side.label}</span>
				{#if side.place}<span class="place">{side.place}</span>{/if}
				{#if side.currently}<span class="place">{side.currently}</span>{/if}
			</span>
		{/if}
		{#if score !== null}<span class="score">{score}</span>{/if}
	</div>
{/snippet}

<div class="play-in-strip" class:mobile={layout === 'mobile'}>
	{#each playIn as card (card.key)}
		<BlueprintFrame>
			<section class="card">
				<h3>{card.title}</h3>
				<ul class="games">
					{#each card.games as game (game.key)}
						<li class="game" class:collapsed>
							<span class="game-title">{game.title}</span>
							{#if !collapsed}
								{@render slotRow(game.top, game.score?.top ?? null)}
								{@render slotRow(game.bottom, game.score?.bottom ?? null)}
								{#if game.when}<span class="when">{game.when}</span>{/if}
							{/if}
							{#each game.outcomes as outcome (outcome)}
								<span class="outcome">{outcome}</span>
							{/each}
							{#if !collapsed && game.linked}
								<a class="game-link" href={gameHref(game.gameId)}>{m.playoffs_game_page()}</a>
							{/if}
						</li>
					{/each}
				</ul>
			</section>
		</BlueprintFrame>
	{/each}
</div>

<style>
	.play-in-strip {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--panel-section-gap);
	}

	.card {
		display: grid;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
	}

	h3 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
	}

	.games {
		display: grid;
		gap: var(--game-list-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.game {
		display: grid;
		gap: var(--day-strip-gap);
		padding-bottom: var(--game-list-gap);
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.game-title {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.slot {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-height: var(--hit-target-size);
	}

	.slot-text {
		display: grid;
		min-width: 0;
	}

	.slot-name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}

	.undecided .slot-name {
		color: var(--color-muted);
	}

	.place {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.score {
		margin-left: auto;
		font-family: var(--font-heading);
		font-size: var(--box-points-size);
		font-variant-numeric: tabular-nums;
	}

	.when {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.outcome {
		font-size: var(--body-size-small);
		color: var(--color-accent-light);
	}

	.collapsed {
		padding-bottom: 0;
		border-bottom: 0;
	}

	.game-link {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		font-size: var(--body-size-small);
		color: var(--color-accent-light);
	}

	.game-link:hover {
		color: var(--color-accent-hover);
	}
</style>
