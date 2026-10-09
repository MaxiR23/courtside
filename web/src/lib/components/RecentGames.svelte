<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { RecentGameRow } from '#lib/player/types.ts';

	type Props = { rows: RecentGameRow[]; gameHref: (id: string) => ResolvedPathname };

	let { rows, gameHref }: Props = $props();
</script>

{#snippet rowBody(row: RecentGameRow)}
	<span class="result" class:win={row.result === 'win'}>{row.resultLabel}</span>
	<span class="date">{row.date}</span>
	<span class="game">
		<span class="opponent">
			{#if row.opponent}
				<TeamMark
					part="label"
					team={row.opponent.team}
					versus={row.opponent.isHome ? 'home' : 'away'}
				/>
			{:else}
				{m.team_tag_allstar()}
			{/if}
		</span>
		<span class="score">{row.score}</span>
		{#if row.tag}<span class="sub">{row.tag}</span>{/if}
	</span>
	<span class="points">
		<span class="points-value">{row.points}</span>
		<span class="sub">{row.line}</span>
	</span>
{/snippet}

<ul class="rows">
	{#each rows as row (row.gameId)}
		<li>
			{#if row.linked}
				<a class="row link" href={gameHref(row.gameId)}>
					{@render rowBody(row)}
				</a>
			{:else}
				<div class="row">
					{@render rowBody(row)}
				</div>
			{/if}
		</li>
	{/each}
</ul>

<style>
	.rows {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.row {
		display: grid;
		grid-template-columns:
			var(--player-recent-result-width) var(--player-recent-date-width) 1fr
			auto;
		align-items: center;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
		border-bottom: var(--hairline) solid var(--color-row-rule);
		color: inherit;
		text-decoration: none;
	}

	.link:hover {
		background: var(--box-row-hover);
	}

	.result {
		font-family: var(--font-heading);
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.win {
		color: var(--color-accent-light);
	}

	.date {
		font-size: var(--body-size-small);
		color: var(--color-muted);
		white-space: nowrap;
	}

	.game,
	.points {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.points {
		align-items: flex-end;
		text-align: right;
	}

	.opponent {
		font-family: var(--font-heading);
		font-size: var(--injury-name-size);
	}

	.score {
		font-family: var(--font-heading);
		font-size: var(--body-size);
		font-variant-numeric: tabular-nums;
	}

	.points-value {
		font-family: var(--font-heading);
		font-size: var(--player-recent-points-size);
		font-variant-numeric: tabular-nums;
	}

	.sub {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}
</style>
