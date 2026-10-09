<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import LiveBadge from '#lib/components/LiveBadge.svelte';
	import NavRow from '#lib/components/NavRow.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { GameHeaderView, HeaderTeam, ScoreboardCenter } from '#lib/game/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		header: GameHeaderView | null; // null: only the nav row, or its skeleton while loading
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
	};

	let { header, allGamesHref, standingsHref, layout, teamHref, loading = false }: Props = $props();

	type TipOff = Extract<ScoreboardCenter, { kind: 'tip-off' }>;

	const sides = $derived(
		header
			? ([
					{ side: 'away', team: header.away },
					{ side: 'home', team: header.home }
				] as const)
			: []
	);

	const isLoser = (side: 'away' | 'home') =>
		header?.center.kind === 'score' && header.center.loser === side;

	// The mobile meta line: the city, then the record when the team has one.
	const metaOf = (team: HeaderTeam) => (team.record ? `${team.city} · ${team.record}` : team.city);

	// Keyed by photo URL, so a new URL tries again after a failure.
	let failedPhoto = $state<string | null>(null);
</script>

{#snippet tipOff(center: TipOff, mobile: boolean)}
	<div class="tip-off" class:mobile>
		{#if center.delayed}
			<span class="scheduled">{m.game_scheduled()}</span>
		{/if}
		<span class="tip-time">
			{center.tipTime}
			<span class="tip-suffix">{center.tipSuffix}</span>
		</span>
		{#if center.broadcast}
			<span class="broadcast">{center.broadcast}</span>
		{/if}
	</div>
{/snippet}

{#snippet teamBlock(team: HeaderTeam, side: 'away' | 'home')}
	<div class="team {side}" class:dimmed={isLoser(side)}>
		<TeamMark part="tile" {team} size="header" {teamHref} />
		<span class="city">{team.city}</span>
		<h1 class="name">
			<TeamMark part="name" {team} {teamHref} />
		</h1>
		{#if team.record}<span class="record">{team.record}</span>{/if}
	</div>
{/snippet}

<header class="game-header" aria-busy={loading && !header ? 'true' : undefined}>
	<div class="grid-bg" aria-hidden="true"></div>
	<div class="content">
		<NavRow page="detail" gamesHref={allGamesHref} {standingsHref} {layout} />

		{#if header}
			<p class="status-line">
				{#if header.status.state === 'live'}
					<LiveBadge />
				{:else if header.status.state === 'delayed' || header.status.state === 'postponed' || header.status.state === 'canceled'}
					<StatusTag status={header.status.state} />
				{/if}
				<span>{header.status.text}</span>
			</p>

			{#if layout === 'desktop'}
				<div class="scoreboard">
					{@render teamBlock(header.away, 'away')}
					<div class="center">
						{#if header.center.kind === 'score'}
							<div class="score">
								<span class="points" class:dimmed={isLoser('away')}>{header.center.away}</span>
								<span class="dash" aria-hidden="true">–</span>
								<span class="points" class:dimmed={isLoser('home')}>{header.center.home}</span>
							</div>
						{:else if header.center.kind === 'tip-off'}
							{@render tipOff(header.center, false)}
						{/if}
					</div>
					{@render teamBlock(header.home, 'home')}
				</div>
			{:else}
				<div class="rows">
					{#each sides as entry (entry.side)}
						{@const side = entry.side}
						{@const team = entry.team}
						<div class="row" class:dimmed={isLoser(side)}>
							<TeamMark part="tile" {team} size="header-mobile" {teamHref} />
							<div class="who">
								<h1 class="name">
									<TeamMark part="name" {team} {teamHref} />
								</h1>
								<span class="meta">{metaOf(team)}</span>
							</div>
							{#if header.center.kind === 'score'}
								<span class="points">{header.center[side]}</span>
							{/if}
						</div>
					{/each}
				</div>
				{#if header.center.kind === 'tip-off'}
					{@render tipOff(header.center, true)}
				{/if}
			{/if}

			{#if header.venue}
				{@const venue = header.venue}
				<div class="venue">
					<BlueprintFrame>
						<div class="photo-box">
							{#if venue.photo && venue.photo !== failedPhoto}
								<img
									src={venue.photo}
									alt=""
									loading="lazy"
									onerror={() => (failedPhoto = venue.photo)}
								/>
								<div class="fade" aria-hidden="true"></div>
							{:else}
								<div class="bare-grid" aria-hidden="true"></div>
							{/if}
							<div class="caption">
								<span class="arena">{venue.arena}</span>
								{#if venue.city}
									<span class="arena-city">{venue.city}</span>
								{/if}
							</div>
						</div>
					</BlueprintFrame>
					{#each venue.cells as cell (cell.label)}
						<div class="cell">
							<span class="cell-label">{cell.label}</span>
							<span class="cell-value">{cell.value}</span>
							{#if cell.sub}
								<span class="cell-sub">{cell.sub}</span>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		{:else if loading}
			<div class="skeleton" aria-hidden="true" use:play={shimmer}>
				<span class="bone status-bone"></span>
				<div class="team-bones">
					<span class="bone team-bone"></span>
					<span class="bone center-bone"></span>
					<span class="bone team-bone"></span>
				</div>
				<BlueprintFrame><span class="bone venue-bone"></span></BlueprintFrame>
			</div>
		{/if}
	</div>
</header>

<style>
	.game-header {
		position: relative;
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	.grid-bg {
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(var(--color-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(90deg, var(--color-grid-line) var(--hairline), transparent var(--hairline));
		background-size: var(--hero-grid-size) var(--hero-grid-size);
		pointer-events: none;
	}

	.content {
		position: relative;
		display: grid;
		gap: var(--panel-section-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--game-list-gap) var(--side-padding) var(--panel-section-gap);
	}

	.status-line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: center;
		gap: var(--game-list-gap);
		margin: 0;
		font-size: var(--body-size-small);
		letter-spacing: var(--detail-status-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
		text-align: center;
	}

	.scoreboard {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		gap: var(--detail-scoreboard-gap);
	}

	.team {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--day-strip-gap);
	}

	.team.home {
		align-items: flex-end;
		text-align: end;
	}

	.city {
		font-size: var(--body-size-small);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.name {
		margin: 0;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--detail-h1-size);
		line-height: var(--detail-h1-line-height);
		text-transform: uppercase;
		hyphens: manual;
	}

	.record {
		font-size: var(--body-size);
		color: var(--color-muted);
		font-variant-numeric: tabular-nums;
	}

	.dimmed {
		opacity: var(--detail-dimmed-opacity);
	}

	.center {
		display: flex;
		justify-content: center;
	}

	.score {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--detail-score-size);
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}

	.dash {
		font-size: var(--detail-score-minor-size);
		color: var(--color-muted);
	}

	.tip-off {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--day-strip-gap);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		text-align: center;
	}

	.tip-time {
		font-size: var(--detail-tip-time-size);
		line-height: 1;
	}

	.tip-off.mobile .tip-time {
		font-size: var(--detail-tip-time-size-mobile);
	}

	.tip-suffix {
		font-size: var(--detail-score-minor-size);
		color: var(--color-muted);
	}

	.scheduled {
		font-family: var(--font-body);
		font-weight: var(--font-weight-regular);
		font-size: var(--body-size-small);
		letter-spacing: var(--detail-status-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.broadcast {
		font-family: var(--font-body);
		font-weight: var(--font-weight-regular);
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.rows {
		display: grid;
		gap: var(--game-list-gap);
	}

	.row {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.who {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
	}

	.row .name {
		font-size: var(--detail-team-name-size-mobile);
	}

	.meta {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.row .points {
		margin-inline-start: auto;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--detail-score-size-mobile);
		font-variant-numeric: tabular-nums;
	}

	.venue {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--venue-column-min)), 1fr));
		gap: var(--game-list-gap);
	}

	.photo-box {
		position: relative;
		overflow: hidden;
		aspect-ratio: var(--video-aspect);
	}

	.photo-box img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.fade {
		position: absolute;
		inset: 0;
		background: var(--hero-fade);
		pointer-events: none;
	}

	.caption {
		position: absolute;
		inset-inline: var(--game-list-gap);
		bottom: var(--game-list-gap);
		display: flex;
		flex-direction: column;
	}

	.arena {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--detail-info-value-size);
		text-transform: uppercase;
	}

	.arena-city {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.bare-grid {
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(var(--color-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(90deg, var(--color-grid-line) var(--hairline), transparent var(--hairline));
		background-size: var(--hero-frame-grid-size) var(--hero-frame-grid-size);
	}

	.cell {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: var(--day-strip-gap);
	}

	.cell-label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.cell-value {
		font-family: var(--font-heading);
		font-size: var(--detail-info-value-size);
	}

	.cell-sub {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.skeleton {
		display: grid;
		gap: var(--panel-section-gap);
	}

	.bone {
		display: block;
		background: var(--color-surface);
		border-radius: var(--radius);
	}

	.status-bone {
		justify-self: center;
		width: var(--skeleton-button-width);
		height: var(--body-size-small);
	}

	.team-bones {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		gap: var(--detail-scoreboard-gap);
	}

	.team-bone {
		height: var(--detail-h1-size);
	}

	.center-bone {
		width: var(--detail-score-size);
		height: var(--detail-score-size);
	}

	.venue-bone {
		aspect-ratio: var(--video-aspect);
	}
</style>
