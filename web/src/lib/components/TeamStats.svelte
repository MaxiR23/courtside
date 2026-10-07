<script lang="ts">
	import { barWidth } from '#lib/game/motion.ts';
	import type { DetailTeamStatLine, StatLeads } from '#lib/game/types.ts';
	import { crossfade } from '#lib/hero/motion.ts';
	import { formatNumber } from '#lib/format/locale.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { statBar } from '#lib/schedule/motion.ts';
	import { barShares, leadingSide } from '#lib/schedule/stats.ts';
	import type { TeamStatLine } from '#lib/schedule/types.ts';

	// With `leads` (the game detail page) the feed names the leading side and eight stats show.
	type Props =
		| { away: TeamStatLine; home: TeamStatLine; open: boolean; leads?: undefined }
		| { away: DetailTeamStatLine; home: DetailTeamStatLine; open: boolean; leads: StatLeads };

	let { away, home, open, leads }: Props = $props();

	const percent = (v: number) =>
		formatNumber(v, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
	const count = (v: number) => formatNumber(v);

	type Row = {
		key: string;
		field: keyof DetailTeamStatLine;
		label: string;
		a: number;
		h: number;
		format: (v: number) => string;
		lowerIsBetter: boolean;
	};

	const baseRows = $derived<Row[]>([
		{
			key: 'fg',
			field: 'fieldGoalPct',
			label: m.panel_stat_field_goals(),
			a: away.fieldGoalPct,
			h: home.fieldGoalPct,
			format: percent,
			lowerIsBetter: false
		},
		{
			key: 'tp',
			field: 'threePointPct',
			label: m.panel_stat_three_points(),
			a: away.threePointPct,
			h: home.threePointPct,
			format: percent,
			lowerIsBetter: false
		},
		{
			key: 'reb',
			field: 'rebounds',
			label: m.panel_stat_rebounds(),
			a: away.rebounds,
			h: home.rebounds,
			format: count,
			lowerIsBetter: false
		},
		{
			key: 'ast',
			field: 'assists',
			label: m.panel_stat_assists(),
			a: away.assists,
			h: home.assists,
			format: count,
			lowerIsBetter: false
		},
		{
			key: 'tov',
			field: 'turnovers',
			label: m.panel_stat_turnovers(),
			a: away.turnovers,
			h: home.turnovers,
			format: count,
			lowerIsBetter: true
		}
	]);

	// The detail page's order: FG%, 3P%, FT%, Rebounds, Assists, Turnovers, Steals, Blocks.
	const detailRows = $derived.by<Row[]>(() => {
		const a = away as DetailTeamStatLine;
		const h = home as DetailTeamStatLine;
		const extra = (
			key: string,
			field: keyof DetailTeamStatLine,
			label: string,
			format: (v: number) => string,
			lowerIsBetter = false
		): Row => ({ key, field, label, a: a[field], h: h[field], format, lowerIsBetter });
		const [fg, tp, reb, ast, tov] = baseRows;
		return [
			fg,
			tp,
			extra('ft', 'freeThrowPct', m.panel_stat_free_throws(), percent),
			reb,
			ast,
			tov,
			extra('stl', 'steals', m.panel_stat_steals(), count),
			extra('blk', 'blocks', m.panel_stat_blocks(), count)
		];
	});

	const rows = $derived(
		(leads ? detailRows : baseRows).map((row) => ({
			...row,
			lead: leads ? leads[row.field] : leadingSide(row.a, row.h, row.lowerIsBetter),
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
					{#if leads}
						<span
							class="bar"
							class:lead={row.lead === 'away'}
							style:--share={row.shares.away}
							use:barWidth={row.shares.away}
						></span>
					{:else}
						<span
							class="bar"
							class:lead={row.lead === 'away'}
							style:--share={row.shares.away}
							use:crossfade={statBar(open)}
						></span>
					{/if}
				</span>
				<span class="half home">
					{#if leads}
						<span
							class="bar"
							class:lead={row.lead === 'home'}
							style:--share={row.shares.home}
							use:barWidth={row.shares.home}
						></span>
					{:else}
						<span
							class="bar"
							class:lead={row.lead === 'home'}
							style:--share={row.shares.home}
							use:crossfade={statBar(open)}
						></span>
					{/if}
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
