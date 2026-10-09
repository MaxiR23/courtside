<script lang="ts">
	import ClinchTag from '#lib/components/ClinchTag.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { StandingsKeyEntry } from '#lib/standings/types.ts';

	type Props = { entries: StandingsKeyEntry[] };

	let { entries }: Props = $props();
</script>

<section class="standings-key">
	<Kicker text={m.standings_key()} />
	<ul class="entries">
		{#each entries as entry (entry.clinch.code)}
			<li class="entry">
				<ClinchTag clinch={entry.clinch} />
				<span class="label">{entry.label}</span>
			</li>
		{/each}
	</ul>
	<p class="note">{m.standings_key_note()}</p>
</section>

<style>
	.standings-key {
		display: grid;
		gap: var(--game-list-gap);
	}

	.entries {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--detail-column-min)), 1fr));
		gap: var(--day-strip-gap) var(--game-list-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.entry {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.label {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.note {
		margin: 0;
		font-size: var(--caption-size);
		color: var(--color-muted);
	}
</style>
