<script lang="ts">
	// A hairline control with one option pressed. The News page filter.
	type Props = {
		label: string; // the group's accessible name
		options: { value: string; label: string }[];
		value: string;
		onChange: (value: string) => void;
	};

	let { label, options, value, onChange }: Props = $props();
</script>

<div class="toggle" role="group" aria-label={label}>
	{#each options as option (option.value)}
		<button
			type="button"
			class="option"
			class:active={option.value === value}
			aria-pressed={option.value === value}
			onclick={() => onChange(option.value)}
		>
			{option.label}
		</button>
	{/each}
</div>

<style>
	.toggle {
		display: inline-flex;
		max-width: 100%;
		border: var(--hairline) solid var(--color-divider);
	}

	.option {
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: 0;
		background: none;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
		cursor: pointer;
	}

	.option + .option {
		border-left: var(--hairline) solid var(--color-divider);
	}

	.option.active {
		background: var(--toggle-active-fill);
		box-shadow: inset 0 0 0 var(--hairline) var(--color-accent);
		color: var(--color-ink);
	}
</style>
