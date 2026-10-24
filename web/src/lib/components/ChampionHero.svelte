<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import SeasonSelect from '#lib/components/SeasonSelect.svelte';
	import SeasonTag from '#lib/components/SeasonTag.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import TrophyDrawing from '#lib/components/TrophyDrawing.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { ChampionHeroView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';

	type Props = {
		hero: ChampionHeroView;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		linkSeries: boolean; // the series section is on the page: the strip links to it
		season: string; // "2026-27"
		tag: string | null; // "Season 2025-26" on a past season
		stateLine: string;
		seasonSelect?: SeasonControl | null; // null: no selector
	};

	let {
		hero,
		layout,
		teamHref,
		linkSeries,
		season,
		tag,
		stateLine,
		seasonSelect = null
	}: Props = $props();

	const reduced =
		typeof window !== 'undefined' &&
		window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;

	// The SectionTabs scroll rule: smooth, or at once under reduced motion.
	function scrollTo(id: string) {
		document
			.getElementById(id)
			?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
	}
</script>

{#snippet columns()}
	{#each hero.games as game (game.key)}
		<span class="game" class:loss={!game.win}>
			<span class="n" aria-hidden="true">{game.label}</span>
			<span class="score" aria-hidden="true">{game.score}</span>
			<span class="hidden">{game.spoken}</span>
		</span>
	{/each}
{/snippet}

<section
	class="champion-hero"
	class:mobile={layout === 'mobile'}
	style:--side-accent={hero.accent ?? 'var(--identity-neutral-accent)'}
>
	<div class="grid-bg" aria-hidden="true"></div>
	<div class="inner">
		<div class="label-row">
			<span class="line title-line">
				<span class="trophy" aria-hidden="true"><TrophyDrawing title={hero.label} /></span>
				<span class="label">{hero.label}</span>
			</span>
			<span class="line state-group">
				{#if tag}<SeasonTag text={tag} />{:else}<StatusTag text={season} accent />{/if}
				<span class="state-line">{stateLine}</span>
			</span>
			{#if seasonSelect && layout === 'desktop'}
				<div class="season-select"><SeasonSelect {...seasonSelect} /></div>
			{/if}
		</div>
		<div class="main">
			<div class="copy">
				<h1>
					{#if hero.city}{hero.city}<br />{/if}<TeamMark team={hero.team} part="name" {teamHref} />
				</h1>
				<p class="subline">{hero.subline}</p>
			</div>
			<div class="art">
				<div class="glow" aria-hidden="true"></div>
				<div class="logo" aria-hidden="true">
					<TeamMark team={hero.team} part="tile" size="fill" logo={hero.team.logo} />
				</div>
			</div>
		</div>
		{#if hero.games.length > 0}
			{#if linkSeries}
				<a
					class="strip"
					href="#series"
					onclick={(event) => {
						event.preventDefault();
						scrollTo('series');
					}}
				>
					{@render columns()}
				</a>
			{:else}
				<div class="strip" role="group" aria-label={m.playoffs_hero_strip()}>
					{@render columns()}
				</div>
			{/if}
		{/if}
	</div>
</section>

<style>
	.champion-hero {
		position: relative;
		overflow: hidden;
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

	.mobile .grid-bg {
		background-size: var(--playoffs-hero-grid-size-mobile) var(--playoffs-hero-grid-size-mobile);
	}

	.inner {
		position: relative;
		display: grid;
		gap: var(--panel-section-gap);
		max-width: var(--playoffs-hero-max-width);
		margin: 0 auto;
		padding: var(--playoffs-hero-padding-top) var(--playoffs-hero-padding-side)
			var(--playoffs-hero-padding-bottom);
	}

	.main {
		display: grid;
		grid-template-columns: repeat(
			auto-fit,
			minmax(min(100%, var(--playoffs-hero-column-min)), 1fr)
		);
		align-items: center;
		gap: var(--panel-section-gap);
	}

	.mobile .main {
		grid-template-columns: minmax(0, 1fr);
	}

	.copy {
		display: grid;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.label-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.line {
		display: contents;
	}

	.mobile .label-row {
		flex-direction: column;
		align-items: flex-start;
	}

	.mobile .line {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		white-space: nowrap;
	}

	.state-line {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.season-select {
		margin-inline-start: auto;
	}

	.trophy {
		flex: none;
		width: var(--playoffs-trophy-width);
		height: var(--playoffs-trophy-height);
	}

	.mobile .trophy {
		width: var(--playoffs-trophy-width-mobile);
		height: var(--playoffs-trophy-height-mobile);
	}

	.label {
		font-size: var(--playoffs-hero-label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.mobile .label {
		font-size: var(--label-size);
	}

	h1 {
		margin: 0;
		font-size: var(--playoffs-hero-title-size);
		line-height: var(--playoffs-hero-title-leading);
		text-transform: uppercase;
	}

	.champion-hero.mobile h1 {
		font-size: var(--playoffs-hero-title-size-mobile);
	}

	.subline {
		margin: 0;
		font-size: var(--playoffs-hero-subline-size);
		color: var(--color-muted);
	}

	.mobile .subline {
		font-size: var(--playoffs-hero-subline-size-mobile);
	}

	.art {
		position: relative;
		display: grid;
		justify-items: end;
		min-width: 0;
	}

	.mobile .art {
		order: -1;
		justify-items: center;
	}

	.glow {
		position: absolute;
		top: 50%;
		right: 0;
		width: var(--playoffs-hero-glow-size);
		aspect-ratio: 1;
		transform: translateY(-50%);
		background: radial-gradient(
			circle,
			var(--side-accent),
			transparent var(--identity-glow-falloff)
		);
		opacity: var(--playoffs-hero-glow-alpha);
		pointer-events: none;
	}

	.mobile .glow {
		right: auto;
		left: 50%;
		transform: translate(-50%, -50%);
	}

	.logo {
		position: relative;
		width: min(100%, var(--playoffs-hero-logo-size));
		aspect-ratio: 1;
		filter: var(--playoffs-hero-logo-shadow);
	}

	.mobile .logo {
		width: min(100%, var(--playoffs-hero-logo-size-mobile));
	}

	.strip {
		display: grid;
		grid-auto-flow: column;
		grid-auto-columns: minmax(0, 1fr);
		border-top: var(--hairline) solid var(--playoffs-hero-strip-rule);
		color: inherit;
		text-decoration: none;
	}

	.game {
		display: grid;
		gap: var(--day-strip-gap);
		padding-top: var(--game-list-gap);
		min-width: 0;
		position: relative;
	}

	.hidden {
		position: absolute;
		width: var(--hairline);
		height: var(--hairline);
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}

	.n {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.score {
		font-family: var(--font-heading);
		font-size: var(--playoffs-hero-strip-score-size);
		font-variant-numeric: tabular-nums;
		color: var(--color-ink);
	}

	.mobile .score {
		font-size: var(--playoffs-hero-strip-score-size-mobile);
	}

	.loss .score {
		color: var(--color-muted);
	}
</style>
