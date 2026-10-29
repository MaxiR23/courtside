<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import AllStarLeagueBar from '#lib/components/AllStarLeagueBar.svelte';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { MvpView, ScorelineView } from '#lib/all-star/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		mvp: MvpView | null; // null: only the scoreline card shows
		scoreline: ScorelineView | null;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
		onChampionship: () => void; // selects the Championship and scrolls to the games
	};

	let { mvp, scoreline, layout, teamHref, playerHref, onChampionship }: Props = $props();
</script>

{#snippet rows(line: ScorelineView)}
	<span class="score-rows">
		{#each line.rows as row, i (i)}
			<span class="score-row" class:loser={row.loser}>
				<span class="score-name">
					{#if row.team}<TeamMark team={row.team} part="name" />{:else}{row.name}{/if}
				</span>
				<span class="score-value" class:winner={row.winner}>{row.score}</span>
			</span>
		{/each}
	</span>
{/snippet}

<div class="all-star-mvp" class:mobile={layout === 'mobile'}>
	{#if mvp}
		<BlueprintFrame marks="allstar">
			<div class="mvp-card">
				<div class="photo-column">
					{#if mvp.jersey}<span class="watermark" aria-hidden="true">{mvp.jersey}</span>{/if}
					<PlayerAvatar name={mvp.name} photo={mvp.photo} size="allstar-mvp" />
				</div>
				<div class="info">
					<Kicker text={m.allstar_mvp_label()} />
					<h2 class="name">{mvp.name}</h2>
					{#if mvp.league}
						<a class="league" href={teamHref(mvp.league.code)}>
							<span class="league-code">{mvp.league.code}</span>
							<AllStarLeagueBar league={mvp.league} />
						</a>
					{/if}
					<ul class="lines">
						{#each mvp.lines as line (line.key)}
							<li class="line">
								<Kicker tone="muted" contents
									><span class="round" class:championship={line.championship}>{line.round}</span
									></Kicker
								>
								<span class="result">{line.result}</span>
								<span class="stat">{line.stat}</span>
							</li>
						{/each}
					</ul>
					<p class="total">{mvp.total}</p>
					<a class="profile" href={playerHref(mvp.playerId)}>{m.allstar_mvp_profile()}</a>
				</div>
			</div>
		</BlueprintFrame>
	{/if}
	{#if scoreline}
		<BlueprintFrame marks="allstar">
			{#if layout === 'mobile'}
				<button type="button" class="scoreline block" onclick={onChampionship}>
					{@render rows(scoreline)}
					<span class="box-link">{m.allstar_mvp_box_link()}</span>
				</button>
			{:else}
				<div class="scoreline">
					{@render rows(scoreline)}
					<button type="button" class="box-link" onclick={onChampionship}>
						{m.allstar_mvp_box_link()}
					</button>
				</div>
			{/if}
		</BlueprintFrame>
	{/if}
</div>

<style>
	.all-star-mvp {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--panel-section-gap);
		align-items: stretch;
	}

	.mobile {
		grid-template-columns: minmax(0, 1fr);
		gap: var(--game-list-gap);
	}

	.mvp-card {
		display: grid;
		grid-template-columns: 1fr 1.15fr;
		min-height: var(--allstar-mvp-min-height);
		height: 100%;
	}

	.mobile .mvp-card {
		grid-template-columns: minmax(0, 1fr);
	}

	.photo-column {
		position: relative;
		min-height: 0;
		overflow: hidden;
		background: var(--color-frame-fill);
	}

	.mobile .photo-column {
		height: var(--allstar-mvp-photo-height-mobile);
	}

	.watermark {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		font-family: var(--font-heading);
		font-size: var(--hero-watermark-size);
		color: var(--allstar-watermark-ink);
		line-height: 1;
		pointer-events: none;
	}

	.info {
		display: grid;
		align-content: start;
		justify-items: start;
		gap: var(--game-list-gap);
		min-width: 0;
		padding: var(--panel-section-gap);
	}

	.name {
		margin: 0;
		font-size: var(--allstar-mvp-name-size);
		line-height: var(--allstar-hero-title-leading);
		text-transform: uppercase;
	}

	.league {
		display: grid;
		gap: var(--day-strip-gap);
		color: inherit;
		text-decoration: none;
	}

	.league:hover {
		color: var(--color-accent-hover);
	}

	.league-code {
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
	}

	.lines {
		display: grid;
		gap: var(--day-strip-gap);
		width: 100%;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.line {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0 var(--game-list-gap);
		align-items: baseline;
		padding-top: var(--day-strip-gap);
		border-top: var(--hairline) solid var(--color-row-rule);
	}

	.round.championship {
		color: var(--color-accent-light);
	}

	.result {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.stat {
		grid-column: 1 / -1;
		font-family: var(--font-heading);
		font-size: var(--allstar-mvp-line-size);
		font-variant-numeric: tabular-nums;
	}

	.total {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--allstar-mvp-total-size);
		font-variant-numeric: tabular-nums;
		color: var(--color-accent-light);
	}

	.profile,
	.box-link {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		padding: 0;
		border: 0;
		background: none;
		font: inherit;
		font-size: var(--body-size-small);
		color: var(--color-accent-light);
		cursor: pointer;
	}

	.profile:hover,
	.box-link:hover {
		color: var(--color-accent-hover);
	}

	.scoreline {
		display: grid;
		align-content: space-between;
		justify-items: start;
		gap: var(--panel-section-gap);
		box-sizing: border-box;
		height: 100%;
		padding: var(--panel-section-gap);
	}

	button.scoreline {
		width: 100%;
		border: 0;
		background: none;
		font: inherit;
		color: inherit;
		text-align: left;
		cursor: pointer;
	}

	.score-rows {
		display: grid;
		gap: var(--day-strip-gap);
		width: 100%;
	}

	.score-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.score-row.loser {
		color: var(--color-muted);
	}

	.score-name {
		min-width: 0;
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--allstar-team-name-size);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.score-value {
		font-family: var(--font-heading);
		font-size: var(--allstar-championship-score-size);
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}

	.score-value.winner {
		color: var(--color-accent-light);
	}
</style>
