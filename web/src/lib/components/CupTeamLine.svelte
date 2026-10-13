<script lang="ts">
	import { resolve } from '$app/paths';
	import type { CupTeamLineView } from '#lib/cup/types.ts';

	type Props = { line: CupTeamLineView };

	let { line }: Props = $props();
</script>

<!-- The Cup line resolves its own route, as the nav's Cup link (ADR 0030, ADR 0031). -->
<a class="cup-line" href={resolve('/cup')}
	><span class="group">{line.group}</span> · {line.record}</a
>

<style>
	.cup-line {
		font-size: var(--body-size-small);
		color: var(--color-muted);
		font-variant-numeric: tabular-nums;
		text-decoration: none;
	}

	.group {
		color: var(--color-accent-light);
	}
</style>
