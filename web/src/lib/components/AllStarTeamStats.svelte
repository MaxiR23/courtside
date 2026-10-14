<script lang="ts">
	import type { TeamStatView } from '#lib/all-star/types.ts';

	type Props = { stats: TeamStatView[] };

	let { stats }: Props = $props();
</script>

<ul class="team-stats">
	{#each stats as stat (stat.key)}
		<li class="stat">
			<span class="value away" class:better={stat.better === 'away'}>{stat.away}</span>
			<span class="label">{stat.label}</span>
			<span class="value home" class:better={stat.better === 'home'}>{stat.home}</span>
			<span class="bar" aria-hidden="true">
				<span class="half away-half">
					<span
						class="fill"
						class:better={stat.better === 'away'}
						style:width="{stat.awayShare * 100}%"
					></span>
				</span>
				<span class="half home-half">
					<span
						class="fill"
						class:better={stat.better === 'home'}
						style:width="{stat.homeShare * 100}%"
					></span>
				</span>
			</span>
		</li>
	{/each}
</ul>

<style>
	.team-stats {
		display: grid;
		gap: var(--game-list-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.stat {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: baseline;
		gap: var(--day-strip-gap) var(--game-list-gap);
	}

	.label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.value {
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
		font-variant-numeric: tabular-nums;
		color: var(--color-muted);
	}

	.value.away {
		text-align: left;
	}

	.value.home {
		text-align: right;
	}

	.value.better {
		color: var(--color-ink);
	}

	.bar {
		display: grid;
		grid-column: 1 / -1;
		grid-template-columns: 1fr 1fr;
		gap: var(--day-strip-gap);
	}

	.half {
		display: flex;
		height: var(--allstar-stat-bar-height);
	}

	.away-half {
		justify-content: flex-end;
	}

	.fill {
		background: var(--allstar-stat-bar-lower);
	}

	.fill.better {
		background: var(--color-accent);
	}
</style>
