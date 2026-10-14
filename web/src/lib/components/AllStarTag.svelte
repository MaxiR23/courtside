<script lang="ts">
	// "All-Star", and the round line after it; solid: the Championship's accent tag. "All-Star 2027" on a player has no context.
	type Props = { text: string; context?: string | null; solid?: boolean };

	let { text, context = null, solid = false }: Props = $props();
</script>

<!-- The All-Star mark (ADR 0038): the stage tag with its round, or the player tag. Same shape as the Cup and
	playoffs tags, with its own styles so no section imports another (ADR 0034). Plain text: no link, no hover. -->
<span class="allstar-mark">
	<span class="allstar-tag" class:solid>{text}</span>
	{#if context}<span class="context">{context}</span>{/if}
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

	.allstar-tag {
		display: inline-block;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		border: var(--hairline) solid var(--color-accent);
		padding: var(--tag-padding);
		border-radius: var(--radius);
		color: var(--color-accent-light);
	}

	.solid {
		background: var(--color-accent);
		border-color: var(--color-accent);
		color: var(--color-bg);
	}

	.context {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}
</style>
