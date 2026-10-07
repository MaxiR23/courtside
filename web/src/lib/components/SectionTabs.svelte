<script lang="ts">
	import type { MiniScore, SectionTab } from '#lib/game/types.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Props = { tabs: SectionTab[]; miniScore: MiniScore | null };

	let { tabs, miniScore }: Props = $props();

	function scrollToSection(event: MouseEvent, id: string) {
		event.preventDefault();
		const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
		document
			.getElementById(id)
			?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
	}
</script>

{#if tabs.length > 0 || miniScore}
	<nav class="section-tabs" aria-label={m.game_tabs_label()}>
		<ul class="tabs">
			{#each tabs as tab (tab.id)}
				<li>
					<a href={`#${tab.id}`} onclick={(event) => scrollToSection(event, tab.id)}>{tab.label}</a>
				</li>
			{/each}
		</ul>
		{#if miniScore}
			<span class="mini-score">
				{miniScore.awayCode}
				{miniScore.away} – {miniScore.home}
				{miniScore.homeCode}
			</span>
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
	}
</style>
