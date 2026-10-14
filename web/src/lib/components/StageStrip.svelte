<script lang="ts">
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Stage = {
		key: string;
		label: string;
		dates: string;
		status: 'complete' | 'in_progress' | 'next' | 'upcoming';
		statusLabel: string;
	};

	type Props = { stages: Stage[]; layout: RowLayout; columns?: 4 | 5 };

	let { stages, layout, columns = 4 }: Props = $props();
</script>

<ol class="stage-strip" class:mobile={layout === 'mobile'} class:five={columns === 5}>
	{#each stages as stage (stage.key)}
		<li
			class="stage"
			class:current={stage.status === 'in_progress'}
			class:done={stage.status === 'complete'}
		>
			<span class="label">{stage.label}</span>
			<span class="dates">{stage.dates}</span>
			<span class="status">{stage.statusLabel}</span>
		</li>
	{/each}
</ol>

<style>
	.stage-strip {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: var(--game-list-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.stage-strip.mobile {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	.stage-strip.five {
		grid-template-columns: repeat(var(--playoffs-stage-columns), minmax(0, 1fr));
	}

	.stage-strip.five.mobile {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	.stage-strip.five.mobile .stage:last-child {
		grid-column: 1 / -1;
	}

	.stage {
		display: grid;
		gap: var(--day-strip-gap);
		align-content: start;
		padding-top: var(--day-strip-gap);
		border-top: var(--hairline) solid var(--color-divider);
	}

	.stage.current {
		border-top: var(--cup-stage-rule-current) solid var(--color-accent);
	}

	.stage.done {
		border-top: var(--cup-stage-rule-done) solid var(--color-accent);
	}

	.label {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		text-transform: uppercase;
	}

	.dates {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.status {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.current .status {
		color: var(--color-accent-light);
	}
</style>
