<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import NameLink from '#lib/components/NameLink.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { LastGamesSection } from '#lib/game/types.ts';

	type Props = {
		lastGames: LastGamesSection;
		teamHref: (code: string) => ResolvedPathname;
	};

	let { lastGames, teamHref }: Props = $props();

	const teams = $derived([lastGames.away, lastGames.home]);
</script>

<div class="last-games">
	{#each teams as team (team.code)}
		<BlueprintFrame>
			<div class="team">
				<div class="head">
					<h3><NameLink href={teamHref(team.code)} text={team.name} /></h3>
					{#if team.rows.length > 0}
						<span class="strip">
							{#each team.strip as square, i (i)}
								<span class="square {square.result}">{square.label}</span>
							{/each}
						</span>
					{/if}
				</div>
				{#if team.rows.length > 0}
					<ul>
						{#each team.rows as row, i (i)}
							<li class="row">
								<span class="result {row.result}">{row.resultLabel}</span>
								<span class="date">{row.date}</span>
								<span class="opponent">{row.opponent}</span>
								<span class="score">{row.score}</span>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="empty">{m.game_last_games_empty()}</p>
				{/if}
			</div>
		</BlueprintFrame>
	{/each}
</div>

<style>
	.last-games {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--game-list-gap);
	}

	.team {
		display: grid;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
	}

	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	h3 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--injury-name-size);
		text-transform: uppercase;
	}

	.strip {
		display: flex;
		gap: var(--day-strip-gap);
	}

	.square {
		display: flex;
		align-items: center;
		justify-content: center;
		width: var(--result-square-size);
		height: var(--result-square-size);
		font-size: var(--label-size);
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
	}

	.square.win {
		background: var(--color-accent);
		border-color: var(--color-accent);
		color: var(--color-bg);
	}

	.empty {
		margin: 0;
		color: var(--color-muted);
		font-size: var(--body-size-small);
	}

	ul {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.row {
		display: grid;
		grid-template-columns: var(--last-game-result-width) var(--last-game-date-width) 1fr auto;
		align-items: baseline;
		gap: var(--day-strip-gap);
		padding: var(--day-strip-gap) 0;
		border-bottom: var(--hairline) solid var(--color-row-rule);
		font-size: var(--body-size-small);
	}

	.result {
		font-family: var(--font-heading);
		color: var(--color-muted);
	}

	.result.win {
		color: var(--color-accent-light);
	}

	.date {
		color: var(--color-muted);
	}

	.score {
		font-variant-numeric: tabular-nums;
	}
</style>
