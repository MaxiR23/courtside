<script lang="ts">
	// The compact standings of the home with no games: an East / West control, the top 6 rows and
	// the play-in teams as a footnote. In the Finals preview the control holds the two finalists
	// and the table their path. Not the standings page's StandingsTable.
	// SEE: docs/design.md, Home with no games
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { HomeStandingsView } from '#lib/home/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		view: HomeStandingsView;
		layout: RowLayout;
		standingsHref: ResolvedPathname;
	};

	let { view, layout, standingsHref }: Props = $props();

	const headingId = $props.id();
	const mobile = $derived(layout === 'mobile');

	let selected = $state(0);
	const tabsLabel = $derived(
		view.kind === 'standings' ? m.home_standings_tabs_label() : m.home_finals_path_tabs_label()
	);
</script>

<section class="home-standings" class:mobile aria-labelledby={headingId}>
	<header>
		<h2 id={headingId}>{view.title}</h2>
		{#if view.kind === 'standings'}
			<a class="full" href={standingsHref}>{m.home_standings_full()}</a>
		{/if}
	</header>

	<div class="toggle" role="group" aria-label={tabsLabel}>
		{#if view.kind === 'standings'}
			{#each view.tabs as tab, i (tab.key)}
				<button
					type="button"
					class="option"
					class:active={i === selected}
					aria-pressed={i === selected}
					onclick={() => (selected = i)}
				>
					{tab.label}
				</button>
			{/each}
		{:else}
			{#each view.tabs as tab, i (tab.key)}
				<button
					type="button"
					class="option finalist"
					class:active={i === selected}
					aria-pressed={i === selected}
					onclick={() => (selected = i)}
				>
					<TeamMark team={tab.team} part="tile" size="small" logo={tab.team.logo} />
					<TeamMark team={tab.team} part="name" />
				</button>
			{/each}
		{/if}
	</div>

	{#if view.kind === 'standings'}
		{@const current = view.tabs[selected] ?? view.tabs[0]}
		<BlueprintFrame>
			<table class="table">
				<thead>
					<tr>
						<th class="rank" scope="col">#</th>
						<th class="team" scope="col">{m.home_standings_col_team()}</th>
						<th class="num" scope="col">{m.home_standings_col_record()}</th>
						<th class="num" scope="col">{m.home_standings_col_gb()}</th>
					</tr>
				</thead>
				<tbody>
					{#each current.rows as row (row.code)}
						<tr>
							<td class="rank">{row.seed}</td>
							<td class="team">
								<span class="identity">
									<TeamMark team={row.team} part="tile" size="standings" logo={row.team.logo} />
									<TeamMark team={row.team} part="name" />
								</span>
							</td>
							<td class="num">{row.record}</td>
							<td class="num">{row.gamesBehind}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</BlueprintFrame>
		{#if current.playIn.length > 0}
			<p class="play-in">
				<span class="play-in-label">{m.home_standings_play_in()}</span>
				{#each current.playIn as row (row.code)}
					<span class="separator" aria-hidden="true">·</span>
					<span class="play-in-team">{row.seed} <TeamMark team={row.team} part="label" /></span>
				{/each}
			</p>
		{/if}
	{:else}
		{@const current = view.tabs[selected] ?? view.tabs[0]}
		<BlueprintFrame>
			<table class="table">
				<thead>
					<tr>
						<th class="team" scope="col">{m.home_finals_path_col_round()}</th>
						<th class="team" scope="col">{m.home_finals_path_col_opponent()}</th>
						<th class="num" scope="col">{m.home_finals_path_col_result()}</th>
						<th class="num" scope="col"></th>
					</tr>
				</thead>
				<tbody>
					{#each current.series as series (series.key)}
						<tr>
							<td class="round">{series.round}</td>
							<td class="team">
								<span
									class="opponent"
									style:--side-accent={series.accent ?? 'var(--identity-neutral-accent)'}
								>
									<span class="bar" aria-hidden="true"></span>
									<TeamMark
										team={series.opponent}
										part="tile"
										size="small"
										logo={series.opponent.logo}
									/>
									<TeamMark team={series.opponent} part="name" />
								</span>
							</td>
							<td class="num">{series.result}</td>
							<td class="num status" class:lost={!series.won}>
								{series.won ? m.home_finals_path_won() : m.home_finals_path_lost()}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</BlueprintFrame>
	{/if}
</section>

<style>
	.home-standings {
		display: grid;
		gap: var(--game-list-gap);
		min-width: 0;
		align-content: start;
	}

	header {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: var(--game-list-gap);
	}

	h2 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--section-h2-size);
		line-height: var(--section-h2-line-height);
		text-transform: uppercase;
	}

	.full {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-accent-light);
		text-decoration: none;
	}

	.full:hover {
		color: var(--color-accent-hover);
	}

	.toggle {
		justify-self: start;
		display: inline-flex;
		max-width: 100%;
		border: var(--hairline) solid var(--color-divider);
	}

	.option {
		display: inline-flex;
		align-items: center;
		gap: var(--day-strip-gap);
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: 0;
		background: none;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
		cursor: pointer;
	}

	.option + .option {
		border-left: var(--hairline) solid var(--color-divider);
	}

	.option.active {
		background: var(--toggle-active-fill);
		box-shadow: inset 0 0 0 var(--hairline) var(--color-accent);
		color: var(--color-ink);
	}

	.table {
		width: 100%;
		border-collapse: collapse;
		font-variant-numeric: tabular-nums;
	}

	th {
		padding: var(--day-strip-gap) var(--game-list-gap);
		font-size: var(--label-size);
		font-weight: var(--font-weight-regular);
		letter-spacing: var(--label-letter-spacing);
		text-align: left;
		text-transform: uppercase;
		color: var(--color-muted);
	}

	td {
		padding: var(--day-strip-gap) var(--game-list-gap);
		border-top: var(--hairline) solid var(--color-row-rule);
	}

	.rank,
	.num {
		text-align: right;
	}

	.rank {
		color: var(--color-muted);
	}

	.round {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.identity,
	.opponent {
		display: flex;
		align-items: center;
		gap: var(--day-strip-gap);
		min-width: 0;
		font-family: var(--font-heading);
		text-transform: uppercase;
	}

	.bar {
		align-self: stretch;
		width: var(--home-standings-accent-width);
		background: var(--side-accent);
	}

	.lost {
		color: var(--color-muted);
	}

	.play-in {
		margin: 0;
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.play-in-label {
		text-transform: uppercase;
		letter-spacing: var(--label-letter-spacing);
	}

	.separator {
		margin: 0 var(--day-strip-gap);
	}

	.mobile header {
		flex-wrap: wrap;
	}
</style>
