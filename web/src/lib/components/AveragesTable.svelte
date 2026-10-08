<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import StatTable from '#lib/components/StatTable.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { AveragesSection } from '#lib/player/types.ts';

	type Props = {
		averages: AveragesSection;
		gameHref: (id: string) => ResolvedPathname;
	};

	let { averages, gameHref }: Props = $props();
</script>

<StatTable table={averages} labelHeader={m.player_column_season()} {gameHref} />
