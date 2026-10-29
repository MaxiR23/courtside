<script lang="ts">
	// SEE: docs/design-cup.md ("Header")
	import type { ResolvedPathname } from '$app/types';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import SeasonTag from '#lib/components/SeasonTag.svelte';
	import Tag from '#lib/components/Tag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { CupHeaderView, StageView } from '#lib/cup/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { SeasonControl } from '#lib/season/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';
	import Kicker from '#lib/components/Kicker.svelte';

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

	const mobile = $derived(layout === 'mobile');

	const datesLine = (stage: StageView): string =>
		stage.note ? `${stage.dates} · ${stage.note}` : stage.dates;
</script>

{#snippet decor(team: NonNullable<CupHeaderView['team']>)}
	<div
		class="decor"
		class:mobile
		aria-hidden="true"
		style:--side-accent={team.accent ?? 'var(--identity-neutral-accent)'}
	>
		<div class="glow"></div>
		<span class="outline">{team.outline}</span>
		{#if team.team.logo}
			<span class="logo"
				><TeamMark team={team.team} part="tile" size="fill" logo={team.team.logo} /></span
			>
		{/if}
	</div>
{/snippet}

{#snippet firstLine()}
	{#if header}
		<div class="title-block">
			<div class="title-text">
				{#if header.team && mobile}{@render decor(header.team)}{/if}
				<div class="tag-row" class:mobile>
					{#if header.tag}<SeasonTag text={header.tag} />{:else}<Tag
							text={header.season}
							variant="accent"
							label={false}
							size="var(--body-size)"
							padding="var(--cup-year-tag-padding)"
						/>{/if}
					<span class="state-line">{header.stateLine}</span>
				</div>
				<h1 class:mobile>{m.cup_title()}</h1>
				{#if header.team}
					<div class="team-row">
						{#if header.team.strip}
							<span class="bar" class:mobile aria-hidden="true"
								><span class="half" style:background-color={header.team.strip.primary}></span><span
									class="half"
									style:background-color={header.team.strip.secondary}
								></span></span
							>
						{/if}
						<Kicker contents
							><span class="team-label" class:mobile>{header.team.label}</span></Kicker
						>
						<span class="team-name" class:mobile
							>{#if header.team.team.city}{header.team.team.city + ' '}{/if}<TeamMark
								team={header.team.team}
								part="name"
								{teamHref}
							/></span
						>
					</div>
				{/if}
			</div>
		</div>
	{:else}
		<h1 class:mobile>{m.cup_title()}</h1>
	{/if}
{/snippet}

{#snippet decorColumn()}
	{#if header?.team}
		<div
			class="decor-column"
			style:--cup-decor-reach={seasonSelect
				? 'calc(var(--past-select-height) + var(--game-list-gap) + var(--header-first-line-offset))'
				: 'var(--header-first-line-offset)'}
		>
			{@render decor(header.team)}
		</div>
	{/if}
{/snippet}

{#snippet timeline()}
	{#if header}
		<ol class="cup-timeline" class:mobile>
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

<PageHeader
	nav={{ page: 'cup', gamesHref: allGamesHref, standingsHref }}
	{layout}
	{seasonSelect}
	busy={loading && !header}
	grid={mobile ? 'var(--cup-header-grid-size-mobile)' : 'var(--cup-header-grid-size)'}
	gap="var(--cup-header-gap)"
	clip
	first={firstLine}
	body={header ? undefined : bodyRows}
	aside={header?.team && !mobile ? decorColumn : undefined}
	wide={header ? timeline : undefined}
/>

<style>
	.decor-column {
		display: flex;
		flex-direction: column;
		isolation: isolate;
		clip-path: inset(
			calc(-1 * var(--cup-decor-reach)) calc(-1 * var(--cup-header-clip-reach))
				calc(-1 * var(--cup-header-clip-reach))
		);
	}

	.decor {
		position: relative;
		z-index: -1;
		width: var(--cup-header-logo-size);
		height: var(--cup-header-logo-size);
		margin-inline-end: var(--cup-header-logo-right);
		align-self: flex-end;
		pointer-events: none;
	}

	.decor.mobile {
		right: var(--cup-header-logo-right-mobile);
		margin-inline-end: 0;
		width: var(--cup-header-logo-size-mobile);
		height: var(--cup-header-logo-size-mobile);
	}

	.glow {
		position: absolute;
		left: 50%;
		top: 50%;
		transform: translate(-50%, -50%);
		width: var(--cup-header-glow-size);
		height: var(--cup-header-glow-size);
		background: radial-gradient(
			circle,
			var(--side-accent),
			transparent var(--identity-glow-falloff)
		);
		opacity: var(--cup-header-glow-alpha);
	}

	.decor.mobile .glow {
		width: var(--cup-header-glow-size-mobile);
		height: var(--cup-header-glow-size-mobile);
	}

	.outline {
		position: absolute;
		left: 50%;
		top: 50%;
		transform: translate(-50%, -50%);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-bold);
		font-size: var(--cup-header-outline-size);
		line-height: var(--identity-word-leading);
		color: transparent;
		-webkit-text-stroke: var(--hairline) var(--side-accent);
		opacity: var(--cup-header-outline-alpha);
	}

	.decor.mobile .outline {
		font-size: var(--cup-header-outline-size-mobile);
	}

	.logo {
		position: absolute;
		inset: 0;
		filter: var(--cup-header-logo-shadow);
	}

	.decor.mobile .logo {
		position: relative;
		display: block;
		height: 100%;
	}

	.title-block {
		position: relative;
		isolation: isolate;
		display: flex;
		flex-direction: column;
		clip-path: inset(
			calc(-1 * var(--cup-header-gap)) calc(-1 * var(--cup-header-clip-reach))
				calc(-1 * var(--cup-header-clip-reach))
		);
	}

	.title-text {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: var(--cup-header-title-gap);
	}

	.title-text > :not(.decor) {
		max-width: var(--cup-header-title-max-width);
	}

	.tag-row.mobile {
		order: -1;
	}

	.tag-row,
	.season-line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
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

	h1.mobile {
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

	.bar.mobile {
		width: var(--cup-champion-bar-width-mobile);
		height: var(--cup-champion-bar-height-mobile);
	}

	.team-label.mobile {
		font-size: var(--cup-champion-label-size-mobile);
		/* The Kicker contents wrapper passes down spacing computed at 11px; resolve it against this size. */
		letter-spacing: var(--label-letter-spacing);
	}

	.team-name {
		font-family: var(--font-heading);
		font-size: var(--cup-champion-name-size);
		text-transform: uppercase;
	}

	.team-name.mobile {
		font-size: var(--cup-champion-name-size-mobile);
		flex-basis: 100%;
	}

	.cup-timeline {
		position: relative;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--cup-timeline-min)), 1fr));
		column-gap: var(--cup-timeline-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.cup-timeline.mobile {
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

	.cup-timeline.mobile .name {
		font-size: var(--cup-timeline-name-size-mobile);
	}

	.dates {
		font-size: var(--cup-timeline-dates-size);
		color: var(--color-muted);
	}

	.cup-timeline.mobile .dates {
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

	.cup-timeline.mobile .status {
		font-size: var(--cup-timeline-status-size-mobile);
	}

	.bones {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}
</style>
