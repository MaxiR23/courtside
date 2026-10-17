<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamInjuries from '#lib/components/TeamInjuries.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { MatchupSideView, PathRowView } from '#lib/cup/types.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Props = {
		side: MatchupSideView;
		gameHref: (id: string) => ResolvedPathname;
		onPlayer: (index: number, row: HTMLElement) => void;
		rosterNote?: string | null; // a past season: shown in place of the injuries and the roster
	};

	let { side, gameHref, onPlayer, rosterNote = null }: Props = $props();

	const hasStarter = $derived(side.roster.some((player) => player.starter));
</script>

{#snippet pathBody(row: PathRowView)}
	<span class="result" class:win={row.result === 'W'}>{row.result ?? ''}</span>
	<span class="opponent">
		<TeamMark team={row.opponent} part="label" versus={row.isHome ? 'home' : 'away'} />
	</span>
	<span class="path-score">{row.score ?? ''}</span>
{/snippet}

<section class="block">
	<h3 class="team">{side.name}</h3>
	{#if side.team === null}
		{#if side.label !== null}<p class="label">{side.label}</p>{/if}
	{:else}
		<h4 class="heading">{m.cup_path()}</h4>
		<ul class="path">
			{#each side.path as row (row.gameId)}
				<li>
					{#if row.linked}
						<a class="path-row link" href={gameHref(row.gameId)}>{@render pathBody(row)}</a>
					{:else}
						<div class="path-row">{@render pathBody(row)}</div>
					{/if}
				</li>
			{/each}
		</ul>
		{#if rosterNote}
			<p class="label">{rosterNote}</p>
		{:else}
			<TeamInjuries injuries={side.injuries} />
			<div class="roster-head">
				<h4 class="heading">{m.cup_roster()}</h4>
				{#if hasStarter}
					<span class="legend"
						><span class="starter-mark" aria-hidden="true"></span>{m.cup_starting_five()}</span
					>
				{/if}
			</div>
			<table class="roster">
				<thead>
					<tr>
						<th class="number">{m.team_roster_number()}</th>
						<th class="player"></th>
						<th class="position"></th>
						<th class="stat">{m.box_points()}</th>
						<th class="stat">{m.box_rebounds()}</th>
						<th class="stat">{m.box_assists()}</th>
					</tr>
				</thead>
				<tbody>
					{#each side.roster as player, i (player.id)}
						<tr>
							<td class="number">{player.number ?? ''}</td>
							<td class="player">
								<span class="player-cell">
									{#if player.starter}
										<span class="starter-mark" role="img" aria-label={m.cup_starting_five()}></span>
									{/if}
									<button
										type="button"
										class="player-button"
										onclick={(event) => onPlayer(i, event.currentTarget)}
									>
										{player.name}
									</button>
								</span>
							</td>
							<td class="position">
								{#if player.injury}
									<StatusTag injury={player.injury} />
								{:else}
									{player.position ?? ''}
								{/if}
							</td>
							<td class="stat" class:leader={player.leader.points}>{player.points}</td>
							<td class="stat" class:leader={player.leader.rebounds}>{player.rebounds}</td>
							<td class="stat" class:leader={player.leader.assists}>{player.assists}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	{/if}
</section>

<style>
	.block {
		display: grid;
		gap: var(--day-strip-gap);
		align-content: start;
		min-width: 0;
	}

	.team {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--team-name-size);
		font-weight: var(--font-weight-semibold);
	}

	.heading {
		margin: 0;
		font-size: var(--label-size);
		font-weight: var(--font-weight-regular);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.label {
		margin: 0;
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.path {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.path-row {
		display: grid;
		grid-template-columns: var(--game-list-gap) 1fr auto;
		align-items: center;
		gap: var(--game-list-gap);
		padding: var(--day-strip-gap) 0;
		border-bottom: var(--hairline) solid var(--color-row-rule);
		color: inherit;
		font-size: var(--body-size);
		text-decoration: none;
	}

	.link:hover {
		background: var(--box-row-hover);
	}

	.result {
		color: var(--color-muted);
	}

	.result.win {
		color: var(--color-accent-light);
	}

	.path-score {
		font-variant-numeric: tabular-nums;
	}

	.roster-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.legend {
		display: inline-flex;
		align-items: center;
		gap: var(--day-strip-gap);
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.starter-mark {
		display: inline-block;
		flex: none;
		width: var(--day-strip-gap);
		height: var(--day-strip-gap);
		background: var(--color-accent);
	}

	.roster {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--body-size);
	}

	th {
		padding: var(--hairline) var(--day-strip-gap);
		font-size: var(--label-size);
		font-weight: var(--font-weight-regular);
		letter-spacing: var(--label-letter-spacing);
		text-align: left;
		text-transform: uppercase;
		color: var(--color-muted);
	}

	td {
		padding: var(--day-strip-gap);
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.number,
	.stat {
		font-variant-numeric: tabular-nums;
	}

	.stat {
		text-align: right;
	}

	th.stat {
		text-align: right;
	}

	.leader {
		color: var(--color-accent-light);
	}

	.player-cell {
		display: flex;
		align-items: center;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	.player-button {
		padding: 0;
		border: 0;
		background: none;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.player-button:hover {
		color: var(--color-accent-hover);
	}
</style>
