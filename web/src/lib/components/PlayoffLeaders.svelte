<script lang="ts">
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { LeaderTabView } from '#lib/playoffs/types.ts';
	import Kicker from '#lib/components/Kicker.svelte';

	type Props = { tabs: LeaderTabView[] };

	let { tabs }: Props = $props();

	// Not kept between visits.
	let selected = $state(0);
	const current = $derived(tabs[selected] ?? tabs[0]);
	const NO_VALUE = '—';
</script>

<div class="playoff-leaders">
	<div class="chips" role="group" aria-label={m.playoffs_leaders()}>
		{#each tabs as tab, i (tab.key)}
			<button
				type="button"
				class="chip"
				class:active={i === selected}
				aria-pressed={i === selected}
				onclick={() => (selected = i)}
			>
				{tab.label}
			</button>
		{/each}
	</div>
	{#if current}
		<div class="first">
			<PlayerAvatar
				name={current.first?.name ?? NO_VALUE}
				photo={current.first?.photo ?? null}
				size="leader"
			/>
			<div class="who">
				<span class="name">{current.first?.name ?? NO_VALUE}</span>
				<Kicker tone="muted" contents
					><span class="team">{current.first?.team ?? NO_VALUE}</span></Kicker
				>
				<Kicker tone="muted" contents><span class="category">{current.label}</span></Kicker>
			</div>
			<span class="value">{current.first?.value ?? NO_VALUE}</span>
		</div>
		<ul class="rest">
			{#each current.rest as row (row.id)}
				<li class="row">
					<span class="rank">{row.rank}</span>
					<PlayerAvatar name={row.name} photo={row.photo} size="playoffs-avatar" />
					<span class="row-name">{row.name}</span>
					<span class="row-team">{row.team}</span>
					<span class="row-value">{row.value}</span>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.playoff-leaders {
		display: grid;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: var(--day-strip-gap);
	}

	.chip {
		min-width: var(--hit-target-size);
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: var(--hairline) solid var(--color-divider);
		background: none;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
		cursor: pointer;
	}

	.chip.active {
		border-color: var(--color-accent);
		background: var(--color-selected-day);
		color: var(--color-ink);
	}

	.first {
		display: flex;
		align-items: center;
		gap: var(--panel-section-gap);
		min-height: var(--team-leader-photo-width);
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	.who {
		display: grid;
		flex: 1;
		min-width: 0;
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--team-name-size);
	}

	.value {
		font-family: var(--font-heading);
		font-size: var(--playoffs-leader-value-size);
		font-variant-numeric: tabular-nums;
		color: var(--color-accent-light);
	}

	.rest {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.row {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		padding: var(--day-strip-gap);
		border-bottom: var(--hairline) solid var(--color-row-rule);
		font-variant-numeric: tabular-nums;
	}

	.rank {
		min-width: 2ch;
		color: var(--color-muted);
	}

	.row-name {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}

	.row-team {
		color: var(--color-muted);
	}

	.row-value {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}
</style>
