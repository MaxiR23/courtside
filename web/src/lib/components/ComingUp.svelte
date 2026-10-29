<script lang="ts">
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import PageContainer from '#lib/components/PageContainer.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import type { ComingUpItemView, ComingUpTarget } from '#lib/home/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = { items: ComingUpItemView[]; layout: RowLayout };

	let { items, layout }: Props = $props();

	const headingId = $props.id();

	// Coming up resolves the seasonal routes itself, as the nav does (ADR 0030, ADR 0076).
	const hrefs: Record<ComingUpTarget, ResolvedPathname> = {
		cup: resolve('/cup'),
		allStar: resolve('/all-star'),
		playoffs: resolve('/playoffs')
	};

	const labels: Record<ComingUpTarget, () => string> = {
		cup: m.home_coming_up_cta_cup,
		allStar: m.home_coming_up_cta_all_star,
		playoffs: m.home_coming_up_cta_playoffs
	};
</script>

{#snippet card()}
	<BlueprintFrame>
		<div class="panel">
			<h2 class="heading" id={headingId}><Kicker text={m.home_coming_up_title()} /></h2>
			<ol class="items">
				{#each items as item (item.key)}
					<li class="item">
						<span class="date">{item.date}</span>
						<span class="title">{item.title}</span>
						<span class="sub">{item.sub}</span>
						<span class="status">
							<StatusTag text={item.statusLabel} accent={item.status === 'now'} />
						</span>
						{#if item.target}
							<a class="cta" href={hrefs[item.target]}>{labels[item.target]()}</a>
						{/if}
					</li>
				{/each}
			</ol>
		</div>
	</BlueprintFrame>
{/snippet}

{#if layout === 'mobile'}
	<PageContainer>
		<section class="coming-up mobile" aria-labelledby={headingId}>
			{@render card()}
		</section>
	</PageContainer>
{:else}
	<aside class="coming-up" aria-labelledby={headingId}>
		{@render card()}
	</aside>
{/if}

<style>
	.panel {
		display: flex;
		flex-direction: column;
		gap: var(--game-list-gap);
		padding: var(--identity-left-gap);
	}

	.heading {
		margin: 0;
		font-weight: var(--font-weight-regular);
	}

	.items {
		display: flex;
		flex-direction: column;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.item {
		display: grid;
		grid-template-columns: 1fr auto;
		align-items: center;
		column-gap: var(--game-list-gap);
		padding: var(--game-list-gap) 0;
		border-top: var(--hairline) solid var(--color-divider);
	}

	.item:first-child {
		border-top: none;
	}

	.date {
		grid-column: 1;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-muted);
		font-variant-numeric: tabular-nums;
	}

	.title {
		grid-column: 1;
		font-family: var(--font-heading);
		text-transform: uppercase;
	}

	.sub {
		grid-column: 1;
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.status {
		grid-column: 2;
		grid-row: 1;
		justify-self: end;
	}

	.cta {
		grid-column: 1 / -1;
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-accent-light);
		text-decoration: none;
	}

	.cta:hover {
		color: var(--color-accent-hover);
	}
</style>
