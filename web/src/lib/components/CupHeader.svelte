<script lang="ts">
	// SEE: docs/design-cup.md ("Header")
	import type { ResolvedPathname } from '$app/types';
	import NavRow from '#lib/components/NavRow.svelte';
	import SeasonSelect from '#lib/components/SeasonSelect.svelte';
	import SeasonTag from '#lib/components/SeasonTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { CupHeaderView, StageView } from '#lib/cup/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		header: CupHeaderView | null; // null: only the nav row and the title, or the bones while loading
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
		allGamesHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		seasonSelect?: SeasonControl | null; // null: no selector
		seasonTag?: string | null; // "Season 2022-23": kept on the unavailable state of a past season
	};

	let {
		header,
		loading = false,
		allGamesHref,
		standingsHref,
		layout,
		teamHref,
		seasonSelect = null,
		seasonTag = null
	}: Props = $props();

	const datesLine = (stage: StageView): string =>
		stage.note ? `${stage.dates} · ${stage.note}` : stage.dates;
</script>

<header
	class="cup-header"
	class:mobile={layout === 'mobile'}
	aria-busy={loading && !header ? 'true' : undefined}
	style:--side-accent={header?.team
		? (header.team.accent ?? 'var(--identity-neutral-accent)')
		: undefined}
>
	<div class="grid-bg" aria-hidden="true"></div>
	{#if header?.team}
		<div class="decor" aria-hidden="true">
			<div class="glow"></div>
			<span class="outline">{header.team.outline}</span>
			{#if header.team.team.logo}
				<span class="logo"
					><TeamMark
						team={header.team.team}
						part="tile"
						size="fill"
						logo={header.team.team.logo}
					/></span
				>
			{/if}
		</div>
	{/if}
	<div class="content">
		<NavRow page="cup" gamesHref={allGamesHref} {standingsHref} {layout} />
		{#if seasonSelect && layout === 'desktop'}
			<div class="season-row"><SeasonSelect {...seasonSelect} /></div>
		{/if}

		{#if header}
			<div class="title-block">
				<div class="tag-row">
					<span class="year-tag">{header.season}</span>
					{#if header.tag}<SeasonTag text={header.tag} />{/if}
					<span class="state-line">{header.stateLine}</span>
				</div>
				<h1>{m.cup_title()}</h1>
				{#if header.team}
					<div class="team-row">
						{#if header.team.strip}
							<span class="bar" aria-hidden="true"
								><span class="half" style:background-color={header.team.strip.primary}></span><span
									class="half"
									style:background-color={header.team.strip.secondary}
								></span></span
							>
						{/if}
						<span class="team-label">{header.team.label}</span>
						<span class="team-name"
							><TeamMark team={header.team.team} part="name" {teamHref} /></span
						>
					</div>
				{/if}
			</div>
			<ol class="cup-timeline">
				{#each header.stages as stage (stage.key)}
					<li
						class="step"
						class:complete={stage.status === 'complete'}
						class:in-progress={stage.status === 'in_progress'}
					>
						<span class="name">{stage.label}</span>
						<span class="dates">{datesLine(stage)}</span>
						<span class="status">{stage.statusLabel}</span>
					</li>
				{/each}
			</ol>
		{:else}
			<h1>{m.cup_title()}</h1>
			{#if loading}
				<div class="bones" aria-hidden="true" use:play={shimmer}>
					<span class="bone tag-bone"></span>
					<span class="bone state-bone"></span>
				</div>
			{:else if seasonTag}
				<div class="season-line"><SeasonTag text={seasonTag} /></div>
			{/if}
		{/if}
		{#if seasonSelect && layout === 'mobile'}
			<div class="season-row"><SeasonSelect {...seasonSelect} full /></div>
		{/if}
	</div>
</header>

<style>
	.cup-header {
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
		background-size: var(--cup-header-grid-size) var(--cup-header-grid-size);
		pointer-events: none;
	}

	.mobile .grid-bg {
		background-size: var(--cup-header-grid-size-mobile) var(--cup-header-grid-size-mobile);
	}

	.decor {
		position: absolute;
		inset: 0;
		pointer-events: none;
	}

	.glow {
		position: absolute;
		right: var(--cup-header-glow-right);
		top: 50%;
		transform: translateY(-50%);
		width: var(--cup-header-glow-size);
		height: var(--cup-header-glow-size);
		background: radial-gradient(
			circle,
			var(--side-accent),
			transparent var(--identity-glow-falloff)
		);
		opacity: var(--cup-header-glow-alpha);
	}

	.mobile .glow {
		width: var(--cup-header-glow-size-mobile);
		height: var(--cup-header-glow-size-mobile);
	}

	.outline {
		position: absolute;
		right: var(--cup-header-outline-right);
		top: var(--cup-header-outline-top);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-bold);
		font-size: var(--cup-header-outline-size);
		line-height: var(--identity-word-leading);
		color: transparent;
		-webkit-text-stroke: var(--hairline) var(--side-accent);
		opacity: var(--cup-header-outline-alpha);
	}

	.mobile .outline {
		font-size: var(--cup-header-outline-size-mobile);
	}

	.logo {
		position: absolute;
		right: var(--cup-header-logo-right);
		top: var(--cup-header-logo-top);
		width: var(--cup-header-logo-size);
		height: var(--cup-header-logo-size);
		filter: var(--cup-header-logo-shadow);
	}

	.mobile .logo {
		right: var(--cup-header-logo-right-mobile);
		top: var(--cup-header-logo-top-mobile);
		width: var(--cup-header-logo-size-mobile);
		height: var(--cup-header-logo-size-mobile);
	}

	.content {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: var(--cup-header-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--game-list-gap) var(--side-padding) var(--panel-section-gap);
	}

	.title-block {
		position: relative;
		display: flex;
		flex-direction: column;
		justify-content: flex-end;
		gap: var(--cup-header-title-gap);
		max-width: var(--cup-header-title-max-width);
		min-height: var(--cup-header-title-min-height);
	}

	.mobile .title-block {
		min-height: var(--cup-header-title-min-height-mobile);
	}

	.mobile .tag-row {
		position: absolute;
		top: 0;
		left: 0;
	}

	.tag-row,
	.season-line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.year-tag {
		font-size: var(--body-size);
		padding: var(--cup-year-tag-padding);
		border: var(--hairline) solid var(--color-accent);
		color: var(--color-accent-light);
	}

	.state-line {
		font-size: var(--caption-size);
		letter-spacing: var(--cup-header-tracking);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	h1 {
		margin: 0;
		font-size: var(--cup-title-size);
		line-height: var(--cup-title-leading);
	}

	.mobile h1 {
		font-size: var(--cup-title-size-mobile);
	}

	.team-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.bar {
		display: flex;
		width: var(--cup-champion-bar-width);
		height: var(--cup-champion-bar-height);
	}

	.half {
		flex: 1;
	}

	.mobile .bar {
		width: var(--cup-champion-bar-width-mobile);
		height: var(--cup-champion-bar-height-mobile);
	}

	.team-label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.mobile .team-label {
		font-size: var(--cup-champion-label-size-mobile);
	}

	.team-name {
		font-family: var(--font-heading);
		font-size: var(--cup-champion-name-size);
		text-transform: uppercase;
	}

	.mobile .team-name {
		font-size: var(--cup-champion-name-size-mobile);
	}

	.cup-timeline {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--cup-timeline-min)), 1fr));
		column-gap: var(--cup-timeline-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.mobile .cup-timeline {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--cup-timeline-gap-mobile);
	}

	.step {
		display: grid;
		align-content: start;
		padding-top: var(--cup-timeline-step-padding);
		border-top: var(--hairline) solid var(--cup-timeline-rule-idle);
	}

	.step.complete {
		border-top: var(--cup-stage-rule-done) solid var(--color-accent);
	}

	.step.in-progress {
		border-top: var(--cup-stage-rule-current) solid var(--color-accent);
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--cup-timeline-name-size);
		letter-spacing: var(--cup-timeline-name-tracking);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.complete .name,
	.in-progress .name {
		color: var(--color-ink);
	}

	.mobile .name {
		font-size: var(--cup-timeline-name-size-mobile);
	}

	.dates {
		font-size: var(--cup-timeline-dates-size);
		color: var(--color-muted);
	}

	.mobile .dates {
		font-size: var(--cup-timeline-dates-size-mobile);
	}

	.status {
		font-size: var(--label-size);
		letter-spacing: var(--cup-header-tracking);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.in-progress .status {
		color: var(--color-accent-light);
	}

	.mobile .status {
		font-size: var(--cup-timeline-status-size-mobile);
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

	.season-row {
		display: flex;
		justify-content: flex-end;
	}
</style>
