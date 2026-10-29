<script lang="ts">
	import Kicker from '#lib/components/Kicker.svelte';
	import Tag from '#lib/components/Tag.svelte';

	// "All-Star", and the round line after it; solid: the Championship's accent tag. "All-Star 2027" on a player has no context.
	type Props = { text: string; context?: string | null; solid?: boolean };

	let { text, context = null, solid = false }: Props = $props();
</script>

<!-- The All-Star mark (ADR 0038): the stage tag with its round, or the player tag. The section keeps its own
	wrapper styles so no section imports another (ADR 0034); the tag box is the shared Tag. Plain text: no
	link, no hover. -->
<span class="allstar-mark">
	<Tag {text} variant={solid ? 'solid' : 'accent'} truncate />
	{#if context}<Kicker tone="muted" contents><span class="context">{context}</span></Kicker>{/if}
</span>

<style>
	.allstar-mark {
		display: inline-flex;
		align-items: center;
		max-width: 100%;
		min-width: 0;
		gap: var(--allstar-mark-gap);
		vertical-align: middle;
	}

	.context {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
