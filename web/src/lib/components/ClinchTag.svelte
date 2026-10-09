<script lang="ts">
	import type { ClinchView } from '#lib/standings/types.ts';

	type Props = { clinch: ClinchView };

	let { clinch }: Props = $props();
</script>

<span class="clinch-tag {clinch.tone}">{clinch.code}</span>

<style>
	.clinch-tag {
		display: inline-block;
		font-size: var(--injury-tag-size);
		padding: var(--tag-padding);
		border: var(--hairline) solid;
		border-radius: var(--radius);
		white-space: nowrap;
	}

	.accent {
		border-color: var(--color-accent);
		color: var(--color-accent-light);
	}

	.ink {
		border-color: var(--color-divider);
		color: var(--color-ink);
	}

	.muted {
		border-color: var(--color-divider);
		color: var(--color-muted);
	}
</style>
