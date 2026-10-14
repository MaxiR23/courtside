<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Button from '#lib/components/Button.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import TrophyDrawing from '#lib/components/TrophyDrawing.svelte';
	import { parseMs } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { CountUp } from '#lib/playoffs/count-up.svelte.ts';
	import type { ChampionHeroView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		hero: ChampionHeroView;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		showRelive: boolean; // the series section is on the page
	};

	let { hero, layout, teamHref, showRelive }: Props = $props();

	// The tokens live on :root. The server has no window.
	const style = typeof window === 'undefined' ? null : getComputedStyle(document.documentElement);
	const reduced =
		typeof window !== 'undefined' &&
		window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
	const countUp = new CountUp({
		durationMs: parseMs(style?.getPropertyValue('--playoffs-count-duration') ?? ''),
		timeoutMs: parseMs(style?.getPropertyValue('--playoffs-count-timeout') ?? ''),
		reduced
	});

	$effect(() => countUp.start());

	// The SectionTabs scroll rule: smooth, or at once under reduced motion.
	function scrollTo(id: string) {
		document
			.getElementById(id)
			?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
	}
</script>

<div class="champion-hero" class:mobile={layout === 'mobile'}>
	<div class="grid-bg" aria-hidden="true"></div>
	<div class="copy">
		<div class="headline">
			<div class="text">
				<StatusTag text={hero.tag} accent />
				<p class="result">{hero.result}</p>
				<h1>{hero.title}</h1>
			</div>
			{#if layout === 'mobile'}
				<div class="trophy-mobile"><TrophyDrawing title={hero.trophyTitle} /></div>
			{/if}
		</div>
		<div class="champion">
			<span class="tile">
				<TeamMark team={hero.team} part="tile" size="playoffs-champion" {teamHref} />
				{#if hero.strip}
					<span class="strip" aria-hidden="true">
						<span class="half" style:background-color={hero.strip.primary}></span>
						<span class="half" style:background-color={hero.strip.secondary}></span>
					</span>
				{/if}
			</span>
			<span class="champion-text">
				{#if hero.city}<span class="city">{hero.city}</span>{/if}
				<span class="champion-name"><TeamMark team={hero.team} part="name" {teamHref} /></span>
			</span>
		</div>
		<dl class="stats">
			{#each hero.stats as stat (stat.key)}
				<div class="stat" class:accent={stat.accent}>
					<dt>{stat.label}</dt>
					<dd>{countUp.text(stat.value)}</dd>
				</div>
			{/each}
		</dl>
		<div class="buttons">
			{#if showRelive}
				<Button variant="primary" label={m.playoffs_relive()} onclick={() => scrollTo('series')} />
			{/if}
			<Button
				variant="secondary"
				label={m.playoffs_full_bracket()}
				onclick={() => scrollTo('bracket')}
			/>
		</div>
	</div>
	{#if layout === 'desktop'}
		<div class="plate">
			<BlueprintFrame>
				<div class="plate-body">
					<span class="plate-label">{hero.plateLabel}</span>
					<div class="plate-drawing"><TrophyDrawing title={hero.trophyTitle} /></div>
				</div>
			</BlueprintFrame>
		</div>
	{/if}
</div>

<style>
	.champion-hero {
		position: relative;
		display: grid;
		grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
		align-items: center;
		gap: var(--hero-gap);
	}

	.champion-hero.mobile {
		grid-template-columns: minmax(0, 1fr);
	}

	.grid-bg {
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(var(--color-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(90deg, var(--color-grid-line) var(--hairline), transparent var(--hairline));
		background-size: var(--playoffs-hero-grid-size) var(--playoffs-hero-grid-size);
		pointer-events: none;
	}

	.copy {
		position: relative;
		display: grid;
		gap: var(--panel-section-gap);
		min-width: 0;
	}

	.headline {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.text {
		display: grid;
		gap: var(--day-strip-gap);
		justify-items: start;
		min-width: 0;
	}

	.result {
		margin: 0;
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	h1 {
		margin: 0;
		font-size: var(--playoffs-hero-title-size);
		line-height: var(--playoffs-hero-title-leading);
		text-transform: uppercase;
	}

	.trophy-mobile {
		flex: none;
		height: var(--playoffs-trophy-mobile-height);
		aspect-ratio: var(--playoffs-plate-ratio);
	}

	.champion {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.tile {
		display: grid;
		width: var(--playoffs-champion-mark);
	}

	.strip {
		display: flex;
		height: var(--standings-strip-height);
	}

	.half {
		flex: 1;
	}

	.champion-text {
		display: grid;
	}

	.city {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.champion-name {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: var(--game-list-gap);
		margin: 0;
		padding: var(--game-list-gap) 0;
		border-top: var(--hairline) solid var(--color-divider);
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	.mobile .stats {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	.stat {
		display: grid;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	dt {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	dd {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--team-record-value-size);
		font-variant-numeric: tabular-nums;
	}

	.stat.accent dd {
		color: var(--color-accent-light);
	}

	.buttons {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.plate {
		position: relative;
	}

	.plate-body {
		position: relative;
		aspect-ratio: var(--playoffs-plate-ratio);
		padding: var(--panel-section-gap);
		background: var(--color-frame-fill);
	}

	.plate-label {
		position: absolute;
		top: var(--game-list-gap);
		left: var(--game-list-gap);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.plate-drawing {
		width: 100%;
		height: 100%;
	}
</style>
