<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import AllStarLeagueBar from '#lib/components/AllStarLeagueBar.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import type { Top5RowView } from '#lib/all-star/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		rows: Top5RowView[]; // in the order the feed sends them
		layout: RowLayout;
		playerHref: (id: string) => ResolvedPathname;
	};

	let { rows, layout, playerHref }: Props = $props();
</script>

<ol class="top5" class:mobile={layout === 'mobile'}>
	{#each rows as row (row.key)}
		<li>
			<a class="row" href={playerHref(row.playerId)}>
				<span class="rank" class:top={row.top}>{row.rank}</span>
				<span class="photo">
					<PlayerAvatar
						name={row.name}
						photo={row.photo}
						size={layout === 'mobile' ? 'allstar-top5-mobile' : 'allstar-top5'}
					/>
					{#if row.league}<AllStarLeagueBar league={row.league} />{/if}
				</span>
				<span class="who">
					<span class="name">{row.name}</span>
					<span class="team-line">{row.teamLine}</span>
				</span>
				<span class="numbers">
					<span class="points">{row.points}</span>
					<span class="line">{row.line}</span>
				</span>
			</a>
		</li>
	{/each}
</ol>

<style>
	.top5 {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	li {
		border-top: var(--hairline) solid var(--color-row-rule);
	}

	.row {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-height: var(--hit-target-size);
		padding: var(--day-strip-gap) 0;
		color: inherit;
		text-decoration: none;
	}

	.row:hover .name {
		color: var(--color-accent-hover);
	}

	.rank {
		flex: none;
		min-width: 2ch;
		font-family: var(--font-heading);
		font-size: var(--allstar-top5-rank-size);
		color: var(--color-muted);
	}

	.rank.top {
		color: var(--color-accent-light);
	}

	.mobile .rank {
		font-size: var(--player-name-size);
	}

	.photo {
		display: grid;
		flex: none;
	}

	.who {
		display: grid;
		flex: 1;
		min-width: 0;
	}

	.name {
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.team-line {
		overflow: hidden;
		font-size: var(--caption-size);
		color: var(--color-muted);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.numbers {
		display: grid;
		justify-items: end;
		flex: none;
	}

	.points {
		font-family: var(--font-heading);
		font-size: var(--allstar-top5-points-size);
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}

	.mobile .points {
		font-size: var(--player-name-size);
	}

	.line {
		font-size: var(--caption-size);
		color: var(--color-muted);
		white-space: nowrap;
	}
</style>
