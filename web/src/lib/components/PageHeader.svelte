<script lang="ts">
	import type { ComponentProps, Snippet } from 'svelte';
	import NavRow from '#lib/components/NavRow.svelte';
	import SeasonSelect from '#lib/components/SeasonSelect.svelte';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';

	type Props = {
		nav: Omit<ComponentProps<typeof NavRow>, 'layout'>; // NavRow's props: page, hrefs, home extras
		layout: RowLayout;
		seasonSelect?: SeasonControl | null; // desktop: on the first line at the right edge; mobile: full width last
		first?: Snippet; // the first line (the home has none: its copy stays centered)
		body?: Snippet; // under the first line, in the lead column
		aside?: Snippet; // the right column, below the select
		wide?: Snippet; // full-width rows under the columns
		after?: Snippet; // with band: the rows after the band
		backdrop?: Snippet; // absolute layers between the grid and the content (the home watermark)
		busy?: boolean; // aria-busy while the first feed loads
		grid?: string | null; // token reference of the grid cell; null: no grid
		band?: string | null; // token reference of the band's bottom padding; set: grid and divider wrap first..wide
		divider?: boolean; // the hairline under the header
		sidePadding?: string; // token reference; default --side-padding
		gap?: string; // token reference of the row gap; default --panel-section-gap
		mainGap?: string; // token reference of the gap between the lead and side columns; default the row gap
		leadFlex?: string; // flex shorthand (token reference) of the lead column; default 1 1 auto
		sideFlex?: string; // flex shorthand (token reference) of the side column; default 0 1 auto
		columnsMin?: string; // calc of tokens: the lead and side bases added, the gap excluded; with a side column it keeps the desktop select on the first line when the columns wrap
		stickyNav?: { height: string; background: string } | null; // raised nav; sticky with this background on mobile
		clip?: boolean; // clip what overflows the sides (a glow), without a scroll container: the sticky nav keeps working
	};

	let {
		nav,
		layout,
		seasonSelect = null,
		first,
		body,
		aside,
		wide,
		after,
		backdrop,
		busy = false,
		grid = 'var(--hero-grid-size)',
		band = null,
		divider = true,
		sidePadding,
		gap,
		mainGap,
		leadFlex,
		sideFlex,
		columnsMin,
		stickyNav = null,
		clip = false
	}: Props = $props();

	const mobile = $derived(layout === 'mobile');
	const home = $derived(nav.page === 'home');
	const desktopSelect = $derived(seasonSelect != null && !mobile);
	const hasSide = $derived(desktopSelect || aside != null);
	// Out of the side column, so the select stays on the first line when the side column wraps under the lead.
	const floatSelect = $derived(
		desktopSelect && columnsMin != null && (aside != null || sideFlex != null)
	);
</script>

{#snippet mobileSelect()}
	{#if seasonSelect && mobile}<div class="season-row">
			<SeasonSelect {...seasonSelect} full />
		</div>{/if}
{/snippet}

<header
	class="page-header"
	class:mobile
	class:home
	class:divider
	class:clip
	aria-busy={busy ? 'true' : undefined}
	style:--page-header-grid-size={grid ?? undefined}
	style:--page-header-side-padding={sidePadding}
	style:--page-header-gap={gap}
	style:--page-header-main-gap={mainGap}
	style:--page-header-lead-flex={leadFlex}
	style:--page-header-side-flex={sideFlex}
	style:--page-header-columns-min={columnsMin}
	style:--page-header-band-padding={band ?? undefined}
	style:--page-header-nav-height={stickyNav?.height}
	style:--page-header-nav-bg={stickyNav?.background}
>
	{#if grid && !band}<div class="grid-bg" aria-hidden="true"></div>{/if}
	{@render backdrop?.()}
	<div class="nav-bar" class:raised={stickyNav != null}>
		<div class="nav-inner"><NavRow {...nav} {layout} /></div>
	</div>
	<div class="main-box" class:band={band != null}>
		{#if grid && band}<div class="grid-bg" aria-hidden="true"></div>{/if}
		<div class="main-inner">
			<div class="main" class:float-select={floatSelect}>
				<div class="lead">
					{#if first}<div class="first-line">{@render first()}</div>{/if}
					{@render body?.()}
				</div>
				{#if hasSide}
					<div class="side">
						{#if desktopSelect && seasonSelect && !floatSelect}<div class="season-select">
								<SeasonSelect {...seasonSelect} />
							</div>{/if}
						{#if aside}<div class="aside">{@render aside()}</div>{/if}
					</div>
				{/if}
				{#if floatSelect && seasonSelect}<div class="season-select floating">
						<SeasonSelect {...seasonSelect} />
					</div>{/if}
			</div>
			{@render wide?.()}
			{#if band == null}{@render mobileSelect()}{/if}
		</div>
	</div>
	{#if band != null}
		<div class="after-inner">{@render after?.()}{@render mobileSelect()}</div>
	{/if}
</header>

<style>
	.page-header {
		position: relative;
	}

	.clip {
		overflow-x: clip;
	}

	.divider {
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	.grid-bg {
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(var(--color-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(90deg, var(--color-grid-line) var(--hairline), transparent var(--hairline));
		background-size: var(--page-header-grid-size) var(--page-header-grid-size);
		pointer-events: none;
	}

	.nav-bar,
	.main-box {
		position: relative;
	}

	.nav-bar.raised {
		z-index: var(--tabs-z-index);
	}

	.mobile .nav-bar.raised {
		position: sticky;
		top: 0;
		min-height: var(--page-header-nav-height);
		background: var(--page-header-nav-bg);
		backdrop-filter: blur(var(--tabs-blur));
	}

	.nav-inner,
	.main-inner,
	.after-inner {
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding-inline: var(--page-header-side-padding, var(--side-padding));
	}

	.nav-inner {
		padding-top: var(--identity-hero-pad-top);
	}

	.main-inner {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--page-header-gap, var(--panel-section-gap));
		padding-top: var(--header-first-line-offset);
		padding-bottom: var(--panel-section-gap);
	}

	.band {
		overflow: hidden;
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	.band .main-inner {
		padding-bottom: var(--page-header-band-padding);
	}

	.after-inner {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--page-header-gap, var(--panel-section-gap));
		padding-top: var(--game-list-gap);
		padding-bottom: var(--panel-section-gap);
	}

	.mobile .main-inner {
		padding-top: var(--header-first-line-offset-mobile);
	}

	.home .main-inner {
		padding-top: 0;
		padding-bottom: var(--identity-hero-pad-bottom);
	}

	.main {
		position: relative;
		display: flex;
		flex-wrap: wrap;
		align-items: stretch;
		gap: var(--page-header-main-gap, var(--page-header-gap, var(--panel-section-gap)));
	}

	.lead {
		flex: var(--page-header-lead-flex, 1 1 auto);
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		align-content: start;
		gap: var(--page-header-gap, var(--panel-section-gap));
		min-width: 0;
	}

	.side {
		flex: var(--page-header-side-flex, 0 1 auto);
		display: flex;
		flex-direction: column;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.mobile .lead,
	.mobile .side {
		flex: 1 1 100%;
	}

	.season-select {
		align-self: flex-end;
	}

	/* The select leaves the side column: beside the lead the column starts under it, wrapped under the lead it starts at its top. The percentage is the row's width. */
	.float-select .side {
		padding-top: clamp(
			calc(var(--past-select-height) * 0),
			calc(
				(
						100% - var(--page-header-columns-min) -
							var(--page-header-main-gap, var(--page-header-gap, var(--panel-section-gap)))
					) *
					999
			),
			calc(var(--past-select-height) + var(--game-list-gap))
		);
	}

	.floating {
		position: absolute;
		top: 0;
		right: 0;
	}

	.aside {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
</style>
