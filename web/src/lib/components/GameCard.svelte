<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Highlights from '#lib/components/Highlights.svelte';
	import Leaders from '#lib/components/Leaders.svelte';
	import LineScore from '#lib/components/LineScore.svelte';
	import LiveBadge from '#lib/components/LiveBadge.svelte';
	import NameLink from '#lib/components/NameLink.svelte';
	import PlayerPhoto from '#lib/components/PlayerPhoto.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
	import TeamStats from '#lib/components/TeamStats.svelte';
	import { crossfade } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { panelContent, panelExpand, panelTint } from '#lib/schedule/motion.ts';
	import type { RowLayout, ScheduleGame, ScheduleTeam } from '#lib/schedule/types.ts';

	type Props = {
		game: ScheduleGame;
		layout: RowLayout;
		open?: boolean;
		onToggle?: () => void;
		playingVideoId?: string | null;
		onPlay?: (videoId: string) => void;
		spoilerFree?: boolean;
		detailHref?: ResolvedPathname;
		teamHref: (code: string) => ResolvedPathname;
	};

	let {
		game,
		layout,
		open = false,
		onToggle,
		playingVideoId = null,
		onPlay,
		spoilerFree = false,
		detailHref,
		teamHref
	}: Props = $props();

	const panelId = $props.id();

	// Spoiler-free mode: a final card that can expand hides its score until it is open.
	const hidden = $derived(spoilerFree && game.status.state === 'final' && !!game.details && !open);

	// The team that is not the winner of a final game is dimmed; the winner comes from the feed.
	const loser = $derived.by(() => {
		if (hidden) return null;
		const status = game.status;
		if (status.state !== 'final') return null;
		if (status.winner === game.home.code) return 'away';
		if (status.winner === game.away.code) return 'home';
		return null;
	});
	const entries = $derived([
		{ team: game.away, side: 'away' as const },
		{ team: game.home, side: 'home' as const }
	]);
	const scores = $derived.by(() => {
		const status = game.status;
		if (hidden || (status.state !== 'live' && status.state !== 'final')) return null;
		return { away: status.awayScore, home: status.homeScore };
	});
</script>

{#snippet statusLine()}
	{@const status = game.status}
	<span class="status-line">
		{#if status.state === 'final'}
			{m.status_final()}
		{:else if status.state === 'live'}
			<LiveBadge /> {status.period} · {status.clock}
		{:else if status.state === 'scheduled'}
			{#if layout === 'desktop'}
				{status.network ?? ''}
			{:else}
				{status.tipTime + ' ' + status.tipSuffix + (status.network ? ' · ' + status.network : '')}
			{/if}
		{:else if status.state === 'delayed'}
			{m.status_delayed()}
		{:else if status.state === 'postponed'}
			{m.status_postponed()}
		{:else}
			{m.status_canceled()}
		{/if}
	</span>
{/snippet}

{#snippet chevron()}
	<svg class="chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
{/snippet}

{#snippet row()}
	{@const rowHref = (team: ScheduleTeam) =>
		game.details || team.guest ? null : teamHref(team.code)}
	<!-- The row is the expand button when the card has details: no link inside a button. -->
	{#if layout === 'desktop'}
		<span class="row desktop">
			<span class="team away">
				<TeamMonogram code={game.away.code} size="large" href={rowHref(game.away) ?? undefined} />
				<span class="names" class:dimmed={loser === 'away'}>
					<span class="name"><NameLink href={rowHref(game.away)} text={game.away.name} /></span>
					<span class="city">{game.away.city}</span>
				</span>
			</span>
			<span class="center">
				{@render statusLine()}
				{#if scores}
					<span class="scores">
						<span class="score" class:dimmed={loser === 'away'}>{scores.away}</span>
						<span class="score" class:dimmed={loser === 'home'}>{scores.home}</span>
					</span>
				{:else if game.status.state === 'scheduled'}
					<span class="tip-time">
						{game.status.tipTime}<span class="suffix">{game.status.tipSuffix}</span>
					</span>
				{:else if hidden}
					<span class="reveal">{m.schedule_tap_to_reveal()}</span>
				{/if}
			</span>
			<span class="team home">
				<span class="names" class:dimmed={loser === 'home'}>
					<span class="name"><NameLink href={rowHref(game.home)} text={game.home.name} /></span>
					<span class="city">{game.home.city}</span>
				</span>
				<TeamMonogram code={game.home.code} size="large" href={rowHref(game.home) ?? undefined} />
			</span>
			{@render chevron()}
		</span>
	{:else}
		<span class="row mobile">
			<span class="mobile-head">
				<span class="mobile-status">
					{@render statusLine()}
					{#if hidden}<span class="reveal">{m.schedule_tap_to_reveal()}</span>{/if}
				</span>
				{@render chevron()}
			</span>
			{#each entries as entry (entry.side)}
				<span class="mobile-team">
					<TeamMonogram
						code={entry.team.code}
						size="small"
						href={rowHref(entry.team) ?? undefined}
					/>
					<span class="names" class:dimmed={loser === entry.side}>
						<span class="name"><NameLink href={rowHref(entry.team)} text={entry.team.name} /></span>
						<span class="city">{entry.team.city}</span>
					</span>
					{#if scores}
						<span class="score" class:dimmed={loser === entry.side}>{scores[entry.side]}</span>
					{/if}
				</span>
			{/each}
		</span>
	{/if}
{/snippet}

{#snippet gameCenter()}
	{#if detailHref}
		<a class="game-center" href={detailHref}>
			{m.game_center()}
			<svg viewBox="0 0 24 24" aria-hidden="true"
				><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg
			>
		</a>
	{/if}
{/snippet}

{#snippet panelBody()}
	{@const status = game.status}
	{@const details = game.details}
	{#if (details?.kind === 'played' || details?.kind === 'final-without-stats') && (status.state === 'live' || status.state === 'final')}
		<div class="panel-grid">
			<LineScore
				{teamHref}
				away={{
					code: game.away.code,
					guest: game.away.guest,
					periods: details.periods.away,
					total: status.awayScore
				}}
				home={{
					code: game.home.code,
					guest: game.home.guest,
					periods: details.periods.home,
					total: status.homeScore
				}}
			/>
			{#if details.kind === 'played'}
				<Leaders away={details.leaders.away} home={details.leaders.home} {teamHref} />
				<div class="stats-column">
					<TeamStats away={details.stats.away} home={details.stats.home} {open} />
					{@render gameCenter()}
				</div>
			{:else}
				<div class="stats-column">
					<p class="stats-notice">
						{details.statsAvailability === 'pending'
							? m.panel_stats_pending()
							: m.panel_stats_unavailable()}
					</p>
					{@render gameCenter()}
				</div>
			{/if}
		</div>
		{#if status.state === 'live'}
			<p class="notice">{m.panel_live_highlights()}</p>
		{/if}
		{#if status.state === 'final' && details.highlights}
			<div class="panel-highlights">
				<Highlights
					platform={details.highlights.platform}
					searchUrl={details.highlights.searchUrl}
					videos={details.highlights.videos}
					playingId={open ? playingVideoId : null}
					onPlay={(id) => onPlay?.(id)}
				/>
			</div>
		{/if}
	{:else if details?.kind === 'scheduled' && status.state === 'scheduled'}
		<dl class="facts">
			<div class="fact">
				<dt>{m.panel_tip_off()}</dt>
				<dd>{status.tipTime} {status.tipSuffix}</dd>
			</div>
			<div class="fact">
				<dt>{m.panel_venue()}</dt>
				<dd>{details.venue}</dd>
			</div>
			{#if status.network}
				<div class="fact">
					<dt>{m.panel_broadcast()}</dt>
					<dd>{status.network}</dd>
				</div>
			{/if}
		</dl>
		<p class="watch-title">{m.panel_players_to_watch()}</p>
		<div class="watch">
			{#each [details.playersToWatch.away, details.playersToWatch.home].filter((p) => p !== null) as player (player.teamCode)}
				<div class="watch-player">
					<PlayerPhoto {player} />
					<span class="watch-name">{player.firstName} {player.lastName}</span>
				</div>
			{/each}
		</div>
		{@render gameCenter()}
	{/if}
{/snippet}

<BlueprintFrame active={open && !!game.details}>
	<div class="card" class:open>
		<span class="tint" aria-hidden="true" use:crossfade={panelTint(open)}></span>
		{#if game.details}
			<button
				type="button"
				class="toggle"
				aria-expanded={open}
				aria-controls={panelId}
				onclick={() => onToggle?.()}
			>
				{@render row()}
			</button>
			<div class="panel" id={panelId} inert={!open} use:crossfade={panelExpand(open)}>
				<div class="panel-inner">
					<div class="panel-content" use:crossfade={panelContent(open)}>
						{@render panelBody()}
					</div>
				</div>
			</div>
		{:else}
			{@render row()}
		{/if}
	</div>
</BlueprintFrame>

<style>
	.row {
		padding: var(--game-list-gap);
		gap: var(--game-list-gap);
	}

	.desktop {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) var(--chevron-size);
		align-items: center;
	}

	.mobile {
		display: grid;
	}

	.team {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.home {
		justify-content: flex-end;
		text-align: right;
	}

	.names {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.name {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--team-name-size);
		text-transform: uppercase;
		overflow-wrap: anywhere;
	}

	.city {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.center {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--day-strip-gap);
	}

	.status-line {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.scores {
		display: flex;
		gap: var(--game-list-gap);
	}

	.score {
		font-family: var(--font-heading);
		font-size: var(--score-size);
		font-variant-numeric: tabular-nums;
	}

	.tip-time {
		font-family: var(--font-heading);
		font-size: var(--tip-time-size);
	}

	.suffix {
		font-size: var(--tip-time-suffix-size);
		color: var(--color-muted);
	}

	.dimmed {
		opacity: var(--dimmed-opacity);
	}

	.reveal {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.mobile-status {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.mobile-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.mobile-team {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.mobile-team .names {
		flex: 1;
	}

	.mobile-team .name {
		font-size: var(--team-name-size-mobile);
	}

	.mobile-team .score {
		font-size: var(--score-size-mobile);
		text-align: right;
	}

	.toggle {
		display: block;
		width: 100%;
		padding: 0;
		background: none;
		border: 0;
		font: inherit;
		color: inherit;
		text-align: inherit;
		cursor: pointer;
	}

	.card {
		position: relative;
		isolation: isolate;
	}

	.tint {
		position: absolute;
		inset: 0;
		z-index: -1;
		background: var(--color-open-tint);
		opacity: 0;
		pointer-events: none;
	}

	.open .tint {
		opacity: 1;
	}

	.panel {
		display: grid;
		grid-template-rows: 0fr;
	}

	.open .panel {
		grid-template-rows: 1fr;
	}

	.panel-inner {
		min-height: 0;
		overflow: hidden;
	}

	.panel-content {
		padding: var(--game-list-gap);
		border-top: var(--hairline) solid var(--color-divider);
		opacity: 0;
		transform: translateY(var(--panel-content-offset));
	}

	.open .panel-content {
		opacity: 1;
		transform: none;
	}

	.panel-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--panel-column-min)), 1fr));
		gap: var(--panel-section-gap);
	}

	.panel-highlights {
		margin-top: var(--panel-section-gap);
	}

	.notice {
		margin: var(--game-list-gap) 0 0;
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.stats-notice {
		margin: 0;
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.facts {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--panel-column-min)), 1fr));
		gap: var(--game-list-gap);
		margin: 0;
	}

	.fact dt {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.fact dd {
		margin: 0;
		font-size: var(--body-size);
	}

	.watch-title {
		margin: var(--panel-section-gap) 0 var(--game-list-gap);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.watch {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--panel-column-min)), 1fr));
		gap: var(--game-list-gap);
	}

	.watch-player {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.watch-name {
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
		text-transform: uppercase;
	}

	.stats-column {
		display: grid;
		align-content: start;
	}

	.game-center {
		display: flex;
		align-items: center;
		justify-self: end;
		width: fit-content;
		gap: var(--game-center-gap);
		min-height: var(--hit-target-size);
		margin-left: auto;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--game-center-size);
		letter-spacing: var(--game-center-letter-spacing);
		text-transform: uppercase;
		text-decoration: none;
		color: var(--color-accent-light);
	}

	.game-center:hover {
		color: var(--color-ink);
	}

	.game-center svg {
		width: var(--nav-icon-size);
		height: var(--nav-icon-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.open .chevron {
		rotate: var(--chevron-open-rotation);
	}

	.chevron {
		width: var(--chevron-size);
		height: var(--chevron-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
