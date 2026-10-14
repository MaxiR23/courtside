<script lang="ts">
	import type { LeagueMarkView } from '#lib/all-star/types.ts';

	type Props = { league: LeagueMarkView };

	let { league }: Props = $props();
</script>

<!-- The two colors of a league team, as the bar under a player photo or a monogram. -->
<span class="league-bar" aria-hidden="true">
	<span class="half" style:background-color={league.primary ?? 'var(--color-bar-neutral)'}></span>
	<span class="half" style:background-color={league.secondary ?? 'var(--color-bar-neutral)'}></span>
</span>

<style>
	.league-bar {
		display: flex;
		width: 100%;
		height: var(--allstar-league-bar);
	}

	.half {
		flex: 1;
	}
</style>
