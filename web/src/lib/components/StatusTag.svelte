<script lang="ts">
	import type { HeroStatus } from '#lib/hero/types.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Props = { status: HeroStatus };

	let { status }: Props = $props();

	const labels: Record<Props['status'], () => string> = {
		tonight: m.status_tonight,
		live: m.status_live,
		final: m.status_final,
		delayed: m.status_delayed,
		postponed: m.status_postponed,
		canceled: m.status_canceled
	};
</script>

<span class="status-tag">{labels[status]()}</span>

<style>
	.status-tag {
		display: inline-block;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		border: var(--hairline) solid var(--color-divider);
		padding: var(--tag-padding);
		border-radius: var(--radius);
	}
</style>
