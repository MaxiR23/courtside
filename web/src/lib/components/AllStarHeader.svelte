<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import AllStarPlate from '#lib/components/AllStarPlate.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import PageHeader from '#lib/components/PageHeader.svelte';
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
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';

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

{#snippet firstLine()}
	{#if header}
		<div class="copy">
			<div class="tag-line">
				<StatusTag text={header.tag} accent />
				{#if header.seasonTag}<SeasonTag text={header.seasonTag} />{/if}
				{#if header.meta}<span class="meta">{header.meta}</span>{/if}
			</div>
			<Kicker text={header.kicker} />
			<div class="headline">
				<h1 class:mobile>{header.title}</h1>
				{#if mobile && header.plate.kind === 'mvp'}{@render plate(header)}{/if}
			</div>
			{#if header.score}<p class="score" class:mobile>{header.score}</p>{/if}
			{#if header.stats.length > 0}
				<dl class="stats" class:mobile>
					{#each header.stats as stat (stat.key)}
						<div class="stat" class:accent={stat.accent}>
							<Kicker as="dt" tone="muted" text={stat.label} />
							<dd>{statText(stat)}</dd>
						</div>
					{/each}
				</dl>
			{/if}
			{#if header.rows.length > 0}
				<dl class="rows">
					{#each header.rows as row (row.key)}
						<div class="info-row">
							<Kicker as="dt" tone="muted" text={row.label} />
							<dd>{row.value}</dd>
						</div>
					{/each}
				</dl>
			{/if}
			{#if header.buttons.length > 0}
				<div class="buttons" class:mobile>
					{#each header.buttons as button (button.key)}
						<button
							type="button"
							class="button"
							class:mobile
							class:primary={button.primary}
							onclick={() => scrollTo(button.key)}
						>
							<Kicker tone="inherit" text={button.label} />
						</button>
					{/each}
				</div>
			{/if}
		</div>
	{:else}
		<h1 class:mobile>{m.allstar_title()}</h1>
	{/if}
{/snippet}

{#snippet bodyRows()}
	{#if loading}
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			<SkeletonBone width="var(--skeleton-short-width)" height="var(--body-size)" />
			<SkeletonBone width="var(--skeleton-button-width)" height="var(--body-size-small)" />
		</div>
	{:else if seasonTag}
		<div class="season-line"><SeasonTag text={seasonTag} /></div>
	{/if}
{/snippet}

{#snippet plateColumn()}
	{#if header}
		<div class="plate-column">{@render plate(header)}</div>
	{/if}
{/snippet}

<PageHeader
	nav={{ page: 'all-star', gamesHref: allGamesHref, standingsHref }}
	{layout}
	{seasonSelect}
	busy={loading && !header}
	grid="var(--playoffs-hero-grid-size)"
	stickyNav={{ height: 'var(--allstar-header-height)', background: 'var(--allstar-header-bg)' }}
	sidePadding={mobile ? 'var(--allstar-side-padding-mobile)' : undefined}
	mainGap="var(--hero-gap)"
	leadFlex="1 1 var(--detail-column-min)"
	sideFlex="1 1 var(--detail-column-min)"
	columnsMin="calc(var(--detail-column-min) * 2)"
	first={firstLine}
	body={header ? undefined : bodyRows}
	aside={header && !(mobile && header.plate.kind === 'mvp') ? plateColumn : undefined}
/>

<style>
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

	h1.mobile {
		font-size: var(--allstar-hero-title-size-mobile);
	}

	.score {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--allstar-score-size);
		font-variant-numeric: tabular-nums;
		color: var(--color-accent-light);
	}

	.score.mobile {
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

	.stats.mobile {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	.stat {
		display: grid;
		gap: var(--day-strip-gap);
		min-width: 0;
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

	.buttons.mobile {
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
		color: var(--color-ink);
		cursor: pointer;
	}

	.button.mobile {
		min-height: var(--allstar-button-height-mobile);
	}

	.button.primary {
		border-color: var(--color-accent);
		background: var(--color-accent);
		color: var(--color-bg);
	}

	.plate-column {
		display: grid;
		margin-block: auto;
		justify-items: center;
		min-width: 0;
	}

	.bones {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.season-line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}
</style>
