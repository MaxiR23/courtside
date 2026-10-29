<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { ResolvedPathname } from '$app/types';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import SeasonTag from '#lib/components/SeasonTag.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import TrophyDrawing from '#lib/components/TrophyDrawing.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { ChampionHeroView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import Kicker from '#lib/components/Kicker.svelte';

	type Props = {
		hero: ChampionHeroView;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		linkSeries: boolean; // the series section is on the page: the strip links to it
		season: string; // "2026-27"
		tag: string | null; // "Season 2025-26" on a past season
		stateLine: string;
		seasonSelect?: SeasonControl | null; // null: no selector
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		after: Snippet; // the rows after the band: the stage strip
	};

	let {
		hero,
		layout,
		teamHref,
		linkSeries,
		season,
		tag,
		stateLine,
		seasonSelect = null,
		allGamesHref,
		standingsHref,
		after
	}: Props = $props();

	const mobile = $derived(layout === 'mobile');

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
			<Kicker tone="muted" contents><span class="n" aria-hidden="true">{game.label}</span></Kicker>
			<span class="score" aria-hidden="true">{game.score}</span>
			<span class="hidden">{game.spoken}</span>
		</span>
	{/each}
{/snippet}

{#snippet labelRow()}
	<div class="label-row" class:mobile>
		<span class="line title-line">
			<span class="trophy" aria-hidden="true"><TrophyDrawing title={hero.label} /></span>
			<span class="label">{hero.label}</span>
		</span>
		<span class="line state-group">
			{#if tag}<SeasonTag text={tag} />{:else}<StatusTag text={season} accent />{/if}
			<span class="state-line">{stateLine}</span>
		</span>
	</div>
{/snippet}

{#snippet art()}
	<div
		class="art"
		class:mobile
		style:--side-accent={hero.accent ?? 'var(--identity-neutral-accent)'}
	>
		<div class="glow" aria-hidden="true"></div>
		<div class="logo" aria-hidden="true">
			<TeamMark team={hero.team} part="tile" size="fill" logo={hero.team.logo} />
		</div>
	</div>
{/snippet}

{#snippet copy()}
	{#if mobile}{@render art()}{/if}
	<div class="copy">
		<h1 class:mobile>
			{#if hero.city}{hero.city}<br />{/if}<TeamMark team={hero.team} part="name" {teamHref} />
		</h1>
		<p class="subline" class:mobile>{hero.subline}</p>
	</div>
{/snippet}

{#snippet strip()}
	{#if linkSeries}
		<a
			class="strip"
			class:mobile
			href="#series"
			onclick={(event) => {
				event.preventDefault();
				scrollTo('series');
			}}
		>
			{@render columns()}
		</a>
	{:else}
		<div class="strip" class:mobile role="group" aria-label={m.playoffs_hero_strip()}>
			{@render columns()}
		</div>
	{/if}
{/snippet}

<PageHeader
	nav={{ page: 'playoffs', gamesHref: allGamesHref, standingsHref }}
	{layout}
	{seasonSelect}
	grid={mobile ? 'var(--playoffs-hero-grid-size-mobile)' : 'var(--hero-grid-size)'}
	band="var(--playoffs-hero-padding-bottom)"
	leadFlex="1 1 var(--playoffs-hero-column-min)"
	sideFlex="1 1 var(--playoffs-hero-column-min)"
	columnsMin="calc(var(--playoffs-hero-column-min) * 2)"
	first={labelRow}
	body={copy}
	aside={mobile ? undefined : art}
	wide={hero.games.length > 0 ? strip : undefined}
	{after}
/>

<style>
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

	.label-row.mobile {
		flex-direction: column;
		align-items: flex-start;
	}

	.label-row.mobile .line {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		white-space: nowrap;
	}

	.state-line {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.trophy {
		flex: none;
		width: var(--playoffs-trophy-width);
		height: var(--playoffs-trophy-height);
	}

	.label-row.mobile .trophy {
		width: var(--playoffs-trophy-width-mobile);
		height: var(--playoffs-trophy-height-mobile);
	}

	.label {
		font-size: var(--playoffs-hero-label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.label-row.mobile .label {
		font-size: var(--label-size);
	}

	h1 {
		margin: 0;
		font-size: var(--playoffs-hero-title-size);
		line-height: var(--playoffs-hero-title-leading);
		text-transform: uppercase;
	}

	h1.mobile {
		font-size: var(--playoffs-hero-title-size-mobile);
	}

	.subline {
		margin: 0;
		font-size: var(--playoffs-hero-subline-size);
		color: var(--color-muted);
	}

	.subline.mobile {
		font-size: var(--playoffs-hero-subline-size-mobile);
	}

	.art {
		position: relative;
		display: grid;
		justify-items: end;
		margin-block: auto;
		min-width: 0;
	}

	.art.mobile {
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

	.art.mobile .glow {
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

	.art.mobile .logo {
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

	.score {
		font-family: var(--font-heading);
		font-size: var(--playoffs-hero-strip-score-size);
		font-variant-numeric: tabular-nums;
		color: var(--color-ink);
	}

	.strip.mobile .score {
		font-size: var(--playoffs-hero-strip-score-size-mobile);
	}

	.loss .score {
		color: var(--color-muted);
	}
</style>
