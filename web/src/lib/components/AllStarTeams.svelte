<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import AllStarLeagueBar from '#lib/components/AllStarLeagueBar.svelte';
	import AllStarSigla from '#lib/components/AllStarSigla.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import type { TeamCardView } from '#lib/all-star/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		teams: TeamCardView[];
		layout: RowLayout;
		playerHref: (id: string) => ResolvedPathname;
	};

	let { teams, layout, playerHref }: Props = $props();
</script>

<div class="teams" class:mobile={layout === 'mobile'}>
	{#each teams as team (team.key)}
		<article class="team-card" class:champion={team.champion}>
			<header class="head">
				<AllStarSigla team={team.team} size="large" winner={team.champion} />
				<span class="identity">
					<span class="name">{team.name}</span>
					<span class="placement" class:champion={team.champion}>{team.placement}</span>
				</span>
				<span class="record">{team.record}</span>
			</header>
			{#if team.results.length > 0}
				<ul class="results">
					{#each team.results as result (result.key)}
						<li class="result">
							<span class="mark" class:win={result.win}>{result.mark}</span>
							<span class="text">{result.text}</span>
							<span class="score">{result.score}</span>
						</li>
					{/each}
				</ul>
			{/if}
			<ul class="roster">
				{#each team.roster as tile (tile.playerId)}
					<li>
						<a class="tile" href={playerHref(tile.playerId)} title={tile.title}>
							<PlayerAvatar
								name={tile.name}
								photo={tile.photo}
								size={layout === 'mobile' ? 'allstar-roster-mobile' : 'allstar-roster'}
							/>
							{#if tile.league}<AllStarLeagueBar league={tile.league} />{/if}
						</a>
					</li>
				{/each}
			</ul>
		</article>
	{/each}
</div>

<style>
	.teams {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--allstar-team-card-min)), 1fr));
		gap: var(--game-list-gap);
	}

	.team-card {
		display: grid;
		align-content: start;
		gap: var(--game-list-gap);
		min-width: 0;
		padding: var(--game-list-gap);
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
	}

	.team-card.champion {
		border-color: var(--color-accent);
		background: var(--allstar-box-total-fill);
	}

	.head {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.identity {
		display: grid;
		flex: 1;
		min-width: 0;
	}

	.name {
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--allstar-team-name-size);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.placement {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.placement.champion {
		color: var(--color-accent-light);
	}

	.record {
		font-family: var(--font-heading);
		font-size: var(--allstar-team-record-size);
		font-variant-numeric: tabular-nums;
	}

	.results {
		display: grid;
		gap: var(--day-strip-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.result {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		font-size: var(--body-size-small);
		font-variant-numeric: tabular-nums;
	}

	.mark {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex: none;
		width: var(--result-square-size);
		height: var(--result-square-size);
		border: var(--hairline) solid var(--color-divider);
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.mark.win {
		border-color: var(--color-accent);
		background: var(--color-accent);
		color: var(--color-bg);
	}

	.text {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.roster {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(var(--allstar-roster-tile-min), 1fr));
		gap: var(--day-strip-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.mobile .roster {
		display: flex;
		overflow-x: auto;
	}

	.tile {
		display: grid;
		color: inherit;
		text-decoration: none;
	}
</style>
