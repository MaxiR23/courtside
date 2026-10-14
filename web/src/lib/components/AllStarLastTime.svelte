<script lang="ts">
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import AllStarLeagueBar from '#lib/components/AllStarLeagueBar.svelte';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import type { LastTimeView } from '#lib/all-star/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		lastTime: LastTimeView;
		layout: RowLayout;
		playerHref: (id: string) => ResolvedPathname;
	};

	let { lastTime, layout, playerHref }: Props = $props();
</script>

<div class="last-time" class:mobile={layout === 'mobile'}>
	<div class="cards">
		<BlueprintFrame marks="allstar">
			<div class="champion-card">
				<Kicker text={lastTime.champion.kicker} />
				<p class="champion-name">{lastTime.champion.name}</p>
				<p class="meta">{lastTime.champion.meta}</p>
				<p class="score">{lastTime.champion.score}</p>
			</div>
		</BlueprintFrame>
		{#if lastTime.mvp}
			{@const mvp = lastTime.mvp}
			<BlueprintFrame marks="allstar">
				<a class="mvp-card" href={playerHref(mvp.playerId)}>
					<span class="photo">
						<PlayerAvatar name={mvp.name} photo={mvp.photo} size="allstar-mvp" />
					</span>
					<span class="info">
						<span class="name">{mvp.name}</span>
						{#if mvp.league}
							<span class="league">
								<span class="league-code">{mvp.league.code}</span>
								<AllStarLeagueBar league={mvp.league} />
							</span>
						{/if}
						<span class="summary">{mvp.summary}</span>
					</span>
				</a>
			</BlueprintFrame>
		{/if}
	</div>
	<a class="link" href={resolve('/all-star/previous')}>{lastTime.link}</a>
</div>

<style>
	.last-time {
		display: grid;
		gap: var(--game-list-gap);
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--panel-section-gap);
	}

	.mobile .cards {
		gap: var(--game-list-gap);
	}

	.champion-card {
		display: grid;
		align-content: start;
		justify-items: start;
		gap: var(--day-strip-gap);
		box-sizing: border-box;
		height: 100%;
		padding: var(--panel-section-gap);
	}

	.champion-name {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--allstar-recap-name-size);
		line-height: var(--allstar-hero-title-leading);
		text-transform: uppercase;
	}

	.meta {
		margin: 0;
		font-size: var(--caption-size);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.score {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--allstar-recap-score-size);
		font-variant-numeric: tabular-nums;
		color: var(--color-accent);
	}

	.mvp-card {
		display: grid;
		grid-template-columns: var(--allstar-sigla-size) 1fr;
		gap: var(--panel-section-gap);
		align-items: center;
		box-sizing: border-box;
		height: 100%;
		padding: var(--panel-section-gap);
		color: inherit;
		text-decoration: none;
	}

	.photo {
		display: block;
		width: var(--allstar-top5-photo-size);
		height: var(--allstar-top5-photo-size);
	}

	.info {
		display: grid;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--allstar-team-name-size);
	}

	.league {
		display: grid;
		justify-items: start;
		gap: var(--day-strip-gap);
		width: var(--allstar-box-monogram-size);
	}

	.league-code {
		font-family: var(--font-heading);
		font-size: var(--body-size);
	}

	.summary {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.link {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		font-size: var(--body-size);
		color: var(--color-accent-light);
	}

	.link:hover {
		color: var(--color-accent-hover);
	}
</style>
