<script lang="ts">
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { MiniScore } from '#lib/game/types.ts';
	import { miniScoreFade, scoreRowOpen } from '#lib/game/motion.ts';
	import { crossfade } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { ScrolledPastWatch } from '#lib/scroll/scrolled-past.svelte.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		tabs: readonly { id: string; label: string }[];
		miniScore?: MiniScore | null;
		mini?: string | null; // a pre-formatted text, such as "OKC 57–25", when there is no score
		reveal: { element: HTMLElement | null; layout: RowLayout }; // the mini score or text shows once this element's bottom has left the top of the viewport; hidden while it is null
	};

	let { tabs, miniScore = null, mini = null, reveal }: Props = $props();

	const watch = new ScrolledPastWatch();
	$effect(() => {
		const target = reveal.element;
		if (target) return watch.observe(target);
	});
	const revealed = $derived(watch.passed);
	const stacked = $derived(reveal.layout === 'mobile' && (miniScore !== null || mini !== null));

	function scrollToSection(event: MouseEvent, id: string) {
		event.preventDefault();
		const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
		document
			.getElementById(id)
			?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
	}
</script>

{#if tabs.length > 0 || miniScore || mini}
	<nav
		class="section-tabs"
		class:open={revealed}
		class:stacked
		aria-label={m.game_tabs_label()}
		use:crossfade={scoreRowOpen(stacked && revealed)}
	>
		<ul class="tabs">
			{#each tabs as tab (tab.id)}
				<li>
					<a href={`#${tab.id}`} onclick={(event) => scrollToSection(event, tab.id)}>{tab.label}</a>
				</li>
			{/each}
		</ul>
		{#if miniScore}
			<span
				class="mini-score"
				aria-hidden={revealed ? undefined : 'true'}
				use:crossfade={miniScoreFade(revealed)}
			>
				<TeamMark part="label" team={miniScore.awayTeam} />
				{miniScore.away} – {miniScore.home}
				<TeamMark part="label" team={miniScore.homeTeam} />
			</span>
		{:else if mini}
			<span
				class="mini-score"
				aria-hidden={revealed ? undefined : 'true'}
				use:crossfade={miniScoreFade(revealed)}>{mini}</span
			>
		{/if}
	</nav>
{/if}

<style>
	.section-tabs {
		position: sticky;
		top: 0;
		z-index: var(--tabs-z-index);
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
		padding-inline: var(--side-padding);
		background: var(--tabs-bg);
		backdrop-filter: blur(var(--tabs-blur));
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	.tabs {
		display: flex;
		gap: var(--panel-section-gap);
		margin: 0;
		padding: 0;
		list-style: none;
		overflow-x: auto;
		white-space: nowrap;
	}

	a {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		padding-block: var(--tab-padding-block);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--tab-size);
		letter-spacing: var(--tab-letter-spacing);
		text-transform: uppercase;
		text-decoration: none;
		color: var(--color-muted);
	}

	a:hover {
		color: var(--color-ink);
	}

	.mini-score {
		flex-shrink: 0;
		font-size: var(--mini-score-size);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		opacity: 0;
		pointer-events: none;
	}

	.open .mini-score {
		opacity: 1;
	}

	.stacked .mini-score {
		position: absolute;
		inset-inline: 0;
		top: 0;
		height: var(--mini-score-row-height-mobile);
		line-height: var(--mini-score-row-height-mobile);
		text-align: center;
	}

	.stacked.open {
		padding-top: var(--mini-score-row-height-mobile);
		margin-bottom: calc(-1 * var(--mini-score-row-height-mobile));
	}
</style>
