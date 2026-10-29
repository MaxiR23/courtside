<script lang="ts">
	import Kicker from '#lib/components/Kicker.svelte';
	import StakesFlag from '#lib/components/StakesFlag.svelte';
	import TournamentTag from '#lib/components/TournamentTag.svelte';
	import type { PostseasonMarkView } from '#lib/playoffs/types.ts';

	type Props = { mark: PostseasonMarkView };

	let { mark }: Props = $props();
</script>

<!-- The playoffs mark of a game (ADR 0035): the stage tag, the context line and the stakes flag, as one
	piece so each core component renders it behind one condition. -->
<span class="postseason-mark">
	<TournamentTag text={mark.tag} finals={mark.finals} />
	{#if mark.context}<Kicker tone="muted" contents
			><span class="context">{mark.context}</span></Kicker
		>{/if}
	{#if mark.stakes}<StakesFlag text={mark.stakes} />{/if}
</span>

<style>
	.postseason-mark {
		display: inline-flex;
		align-items: center;
		max-width: 100%;
		min-width: 0;
		gap: var(--playoffs-mark-gap);
		vertical-align: middle;
	}

	.context {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
