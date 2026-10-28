<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import AllStarPlate from '#lib/components/AllStarPlate.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import NavRow from '#lib/components/NavRow.svelte';
	import SeasonSelect from '#lib/components/SeasonSelect.svelte';
	import SeasonTag from '#lib/components/SeasonTag.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import type { LiveTick } from '#lib/all-star/live-tick.svelte.ts';
	import type { AllStarHeaderView, StatCellView } from '#lib/all-star/types.ts';
	import { parseMs, play } from '#lib/hero/motion.ts';
	import { formatNumber } from '#lib/format/locale.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { CountUp } from '#lib/count/count-up.svelte.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		header: AllStarHeaderView | null; // null: only the nav row and the title, or the bones while loading
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		tick: LiveTick;
		onLive: (gameId: string) => void;
		seasonSelect?: SeasonControl | null; // null: no selector
		seasonTag?: string | null; // shown when there is no header (an unavailable past season)
	};

	let {
		header,
		loading = false,
		allGamesHref,
		standingsHref,
		layout,
		tick,
		onLive,
		seasonSelect = null,
		seasonTag = null
	}: Props = $props();

	const mobile = $derived(layout === 'mobile');

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

	// Counts the number, not the grouped text, so a thousands separator never splits it.
	function statText(stat: StatCellView): string {
		if (stat.countTo === null || countUp.progress >= 1) return stat.value;
		return formatNumber(Math.round(stat.countTo * countUp.progress));
	}

	// The section tabs' scroll rule: smooth, or at once under reduced motion.
	function scrollTo(id: string) {
		document
			.getElementById(id)
			?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
	}
</script>

{#snippet plate(view: AllStarHeaderView)}
	<AllStarPlate plate={view.plate} {layout} {tick} {onLive} />
{/snippet}

<header class="all-star-header" class:mobile aria-busy={loading && !header ? 'true' : undefined}>
	<div class="nav" class:sticky={mobile}>
		<div class="nav-inner">
			<NavRow page="all-star" gamesHref={allGamesHref} {standingsHref} {layout} />
			{#if seasonSelect && !mobile}
				<div class="season-row"><SeasonSelect {...seasonSelect} /></div>
			{/if}
		</div>
	</div>
	<div class="grid-bg" aria-hidden="true"></div>
	<div class="content">
		{#if header}
			<div class="hero">
				<div class="copy">
					<div class="tag-line">
						<StatusTag text={header.tag} accent />
						{#if header.seasonTag}<SeasonTag text={header.seasonTag} />{/if}
						{#if header.meta}<span class="meta">{header.meta}</span>{/if}
					</div>
					<Kicker text={header.kicker} />
					<div class="headline">
						<h1>{header.title}</h1>
						{#if mobile && header.plate.kind === 'mvp'}{@render plate(header)}{/if}
					</div>
					{#if header.score}<p class="score">{header.score}</p>{/if}
					{#if header.stats.length > 0}
						<dl class="stats">
							{#each header.stats as stat (stat.key)}
								<div class="stat" class:accent={stat.accent}>
									<dt>{stat.label}</dt>
									<dd>{statText(stat)}</dd>
								</div>
							{/each}
						</dl>
					{/if}
					{#if header.rows.length > 0}
						<dl class="rows">
							{#each header.rows as row (row.key)}
								<div class="info-row">
									<dt>{row.label}</dt>
									<dd>{row.value}</dd>
								</div>
							{/each}
						</dl>
					{/if}
					{#if header.buttons.length > 0}
						<div class="buttons">
							{#each header.buttons as button (button.key)}
								<button
									type="button"
									class="button"
									class:primary={button.primary}
									onclick={() => scrollTo(button.key)}
								>
									{button.label}
								</button>
							{/each}
						</div>
					{/if}
				</div>
				{#if !(mobile && header.plate.kind === 'mvp')}
					<div class="plate-column">{@render plate(header)}</div>
				{/if}
			</div>
		{:else}
			<h1>{m.allstar_title()}</h1>
			{#if loading}
				<div class="bones" aria-hidden="true" use:play={shimmer}>
					<span class="bone tag-bone"></span>
					<span class="bone state-bone"></span>
				</div>
			{:else if seasonTag}
				<div class="season-line"><SeasonTag text={seasonTag} /></div>
			{/if}
		{/if}
		{#if seasonSelect && mobile}
			<div class="season-row"><SeasonSelect {...seasonSelect} full /></div>
		{/if}
	</div>
</header>

<style>
	.all-star-header {
		position: relative;
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	.nav {
		position: relative;
		z-index: var(--tabs-z-index);
	}

	.nav.sticky {
		position: sticky;
		top: 0;
		min-height: var(--allstar-header-height);
		background: var(--allstar-header-bg);
		backdrop-filter: blur(var(--tabs-blur));
	}

	.nav-inner {
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--game-list-gap) var(--side-padding) 0;
	}

	.mobile .nav-inner {
		padding-inline: var(--allstar-side-padding-mobile);
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

	.content {
		position: relative;
		display: grid;
		gap: var(--panel-section-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--panel-section-gap) var(--side-padding);
	}

	.mobile .content {
		padding-inline: var(--allstar-side-padding-mobile);
		padding-top: var(--header-first-line-offset-mobile);
	}

	.hero {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		align-items: center;
		gap: var(--hero-gap);
	}

	.copy {
		display: grid;
		justify-items: start;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.tag-line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.meta {
		font-size: var(--caption-size);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.headline {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: var(--game-list-gap);
		width: 100%;
	}

	h1 {
		margin: 0;
		min-width: 0;
		font-size: var(--allstar-hero-title-size);
		line-height: var(--allstar-hero-title-leading);
		text-transform: uppercase;
	}

	.mobile h1 {
		font-size: var(--allstar-hero-title-size-mobile);
	}

	.score {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--allstar-score-size);
		font-variant-numeric: tabular-nums;
		color: var(--color-accent-light);
	}

	.mobile .score {
		font-size: var(--allstar-score-size-mobile);
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: var(--game-list-gap);
		width: 100%;
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
	}

	.stat dd {
		font-family: var(--font-heading);
		font-size: var(--allstar-hero-stat-size);
		font-variant-numeric: tabular-nums;
	}

	.stat.accent dd {
		color: var(--color-accent-light);
	}

	.rows {
		display: grid;
		gap: var(--day-strip-gap);
		width: 100%;
		margin: 0;
	}

	.info-row {
		display: grid;
		grid-template-columns: var(--allstar-box-sticky-column) 1fr;
		gap: var(--game-list-gap);
		padding: var(--day-strip-gap) 0;
		border-top: var(--hairline) solid var(--color-row-rule);
	}

	.info-row dd {
		font-size: var(--body-size);
	}

	.buttons {
		display: flex;
		flex-wrap: wrap;
		gap: var(--game-list-gap);
		width: 100%;
	}

	.mobile .buttons {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	.button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: var(--hit-target-size);
		padding-inline: calc(var(--hit-target-size) / 2);
		border: var(--hairline) solid var(--allstar-button-border);
		border-radius: var(--radius);
		background: transparent;
		font-family: var(--font-body);
		font-weight: var(--font-weight-medium);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-ink);
		cursor: pointer;
	}

	.mobile .button {
		min-height: var(--allstar-button-height-mobile);
	}

	.button.primary {
		border-color: var(--color-accent);
		background: var(--color-accent);
		color: var(--color-bg);
	}

	.plate-column {
		display: grid;
		justify-items: center;
		min-width: 0;
	}

	.bones {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.bone {
		display: block;
		background: var(--color-surface);
		border-radius: var(--radius);
	}

	.tag-bone {
		width: var(--skeleton-short-width);
		height: var(--body-size);
	}

	.state-bone {
		width: var(--skeleton-button-width);
		height: var(--body-size-small);
	}

	.season-line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.season-row {
		display: flex;
		justify-content: flex-end;
	}
</style>
