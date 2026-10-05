<script lang="ts">
	import { crossfade } from '#lib/hero/motion.ts';
	import { formatNumber } from '#lib/format/locale.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { statBar } from '#lib/schedule/motion.ts';
	import { barShares, leadingSide } from '#lib/schedule/stats.ts';
	import type { TeamStatLine } from '#lib/schedule/types.ts';

	type Props = { away: TeamStatLine; home: TeamStatLine; open: boolean };

	let { away, home, open }: Props = $props();

	const percent = (v: number) =>
		formatNumber(v, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
	const count = (v: number) => formatNumber(v);

	const rows = $derived(
		[
			{
				key: 'fg',
				label: m.panel_stat_field_goals(),
				a: away.fieldGoalPct,
				h: home.fieldGoalPct,
				format: percent,
				lowerIsBetter: false
			},
			{
				key: 'tp',
				label: m.panel_stat_three_points(),
				a: away.threePointPct,
				h: home.threePointPct,
				format: percent,
				lowerIsBetter: false
			},
			{
				key: 'reb',
				label: m.panel_stat_rebounds(),
				a: away.rebounds,
				h: home.rebounds,
				format: count,
				lowerIsBetter: false
			},
			{
				key: 'ast',
				label: m.panel_stat_assists(),
				a: away.assists,
				h: home.assists,
				format: count,
				lowerIsBetter: false
			},
			{
				key: 'tov',
				label: m.panel_stat_turnovers(),
				a: away.turnovers,
				h: home.turnovers,
				format: count,
				lowerIsBetter: true
			}
		].map((row) => ({
			...row,
			lead: leadingSide(row.a, row.h, row.lowerIsBetter),
			shares: barShares(row.a, row.h)
		}))
	);
</script>

<div class="team-stats" class:open>
	{#each rows as row (row.key)}
		<div class="stat">
			<div class="stat-head">
				<span class="stat-value away" class:lead={row.lead === 'away'}>{row.format(row.a)}</span>
				<span class="stat-label">{row.label}</span>
				<span class="stat-value home" class:lead={row.lead === 'home'}>{row.format(row.h)}</span>
			</div>
			<div class="bars">
				<span class="half away">
					<span
						class="bar"
						class:lead={row.lead === 'away'}
						style:--share={row.shares.away}
						use:crossfade={statBar(open)}
					></span>
				</span>
				<span class="half home">
					<span
						class="bar"
						class:lead={row.lead === 'home'}
						style:--share={row.shares.home}
						use:crossfade={statBar(open)}
					></span>
				</span>
			</div>
		</div>
	{/each}
</div>

<style>
	.team-stats {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
	}

	.stat {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.stat-head {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: baseline;
		gap: var(--game-list-gap);
		font-variant-numeric: tabular-nums;
	}

	.stat-value {
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
		color: var(--color-muted);
	}

	.stat-value.away {
		text-align: left;
	}

	.stat-value.home {
		text-align: right;
	}

	.stat-value.lead {
		color: var(--color-ink);
	}

	.stat-label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.bars {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--hairline);
	}

	.half {
		display: flex;
	}

	.half.away {
		justify-content: flex-end;
	}

	.bar {
		display: block;
		width: calc(var(--share) * 100%);
		height: var(--stat-bar-height);
		background: var(--color-bar-neutral);
		transform: scaleX(0);
	}

	.open .bar {
		transform: none;
	}

	.away .bar {
		transform-origin: right;
	}

	.home .bar {
		transform-origin: left;
	}

	.bar.lead {
		background: var(--color-accent);
	}
</style>
