<script lang="ts">
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { TeamMarkTeam } from '#lib/team/mark.ts';

	type Props = {
		team: TeamMarkTeam | null; // null: a slot still to be determined
		size: 'large' | 'small';
		winner?: boolean; // the box gets the accent border
	};

	let { team, size, winner = false }: Props = $props();
</script>

<!-- An All-Star team is a guest: its code in an outlined box, never a link (ADR 0025, 0026). -->
<span class="sigla {size}" class:winner>
	{#if team}<TeamMark {team} part="label" />{:else}—{/if}
</span>

<style>
	.sigla {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex: none;
		min-width: 0;
		overflow: hidden;
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--body-size);
		white-space: nowrap;
	}

	.large {
		width: var(--allstar-sigla-size);
		height: var(--allstar-sigla-size);
	}

	.small {
		width: var(--allstar-sigla-width-small);
		height: var(--allstar-sigla-height-small);
		font-size: var(--caption-size);
	}

	.winner {
		border-color: var(--color-accent);
	}
</style>
