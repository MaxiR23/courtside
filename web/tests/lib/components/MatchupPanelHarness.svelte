<script lang="ts">
	// Test harness: owns the open card so the panel's focus return can be exercised.
	import type { ResolvedPathname } from '$app/types';
	import MatchupPanel from '../../../src/lib/components/MatchupPanel.svelte';
	import type { MatchupPanelState, OpenCard } from '../../../src/lib/cup/types';

	type Props = {
		state: MatchupPanelState;
		gameHref: (id: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
	};

	let { state: page, gameHref, playerHref }: Props = $props();
	let card = $state<OpenCard | null>(null);
</script>

<MatchupPanel
	state={page}
	layout="desktop"
	{gameHref}
	{playerHref}
	{card}
	onCard={(next) => (card = next)}
	onClose={() => {}}
/>
