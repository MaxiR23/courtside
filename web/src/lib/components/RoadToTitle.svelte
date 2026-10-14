<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { RoadCardView } from '#lib/playoffs/types.ts';

	type Props = {
		road: RoadCardView[];
		teamHref: (code: string) => ResolvedPathname;
	};

	let { road, teamHref }: Props = $props();
</script>

<div class="road-to-title">
	{#each road as card, i (i)}
		<div class="finalist">
			<BlueprintFrame>
				<div class="card">
					<TeamMark team={card.team} part="tile" size="header" {teamHref} />
					<div class="who">
						<span class="name">{card.name}</span>
						<span class="seed-line">{card.seedLine}</span>
					</div>
					<span class="postseason">{card.postseason}</span>
				</div>
			</BlueprintFrame>
			<ul class="series">
				{#each card.series as row (row.key)}
					<li class="row" class:loss={row.loss}>
						<span class="round">{row.round}</span>
						<span class="seed">{row.opponentSeed}</span>
						<span class="opponent">
							<span class="tile" class:plain={!row.strip}>
								<TeamMark team={row.opponent} part="tile" size="standings" />
								{#if row.strip}
									<span class="strip" aria-hidden="true">
										<span class="half" style:background-color={row.strip.primary}></span>
										<span class="half" style:background-color={row.strip.secondary}></span>
									</span>
								{/if}
							</span>
							<span class="opponent-name"
								><TeamMark team={row.opponent} part="name" {teamHref} /></span
							>
						</span>
						<span class="result">{row.result}</span>
					</li>
				{/each}
			</ul>
		</div>
	{/each}
</div>

<style>
	.road-to-title {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--panel-section-gap);
	}

	.finalist {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
		min-width: 0;
	}

	.card {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
	}

	.who {
		display: grid;
		flex: 1;
		min-width: 0;
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--team-name-size);
	}

	.seed-line {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.postseason {
		font-family: var(--font-heading);
		font-size: var(--score-size-mobile);
		font-variant-numeric: tabular-nums;
	}

	.series {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.row {
		display: grid;
		grid-template-columns: minmax(0, 3fr) auto minmax(0, 4fr) auto;
		align-items: center;
		gap: var(--game-list-gap);
		padding: var(--day-strip-gap);
		border-bottom: var(--hairline) solid var(--color-row-rule);
		font-variant-numeric: tabular-nums;
	}

	.row.loss {
		color: var(--color-muted);
	}

	.round {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.opponent {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.tile {
		display: grid;
		width: var(--standings-monogram-size);
	}

	.plain {
		background: var(--color-surface);
	}

	.strip {
		display: flex;
		height: var(--standings-strip-height);
	}

	.half {
		flex: 1;
	}

	.opponent-name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}

	.result {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		white-space: nowrap;
	}
</style>
