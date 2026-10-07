<script lang="ts">
	import type { InjuryTagStatus } from '#lib/game/types.ts';
	import type { HeroStatus } from '#lib/hero/types.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Props = { status: HeroStatus } | { injury: InjuryTagStatus };

	let props: Props = $props();

	const labels: Record<HeroStatus, () => string> = {
		tonight: m.status_tonight,
		live: m.status_live,
		final: m.status_final,
		delayed: m.status_delayed,
		postponed: m.status_postponed,
		canceled: m.status_canceled
	};

	const injuryLabels: Record<InjuryTagStatus, () => string> = {
		out: m.injury_status_out,
		doubtful: m.injury_status_doubtful,
		questionable: m.injury_status_questionable,
		probable: m.injury_status_probable,
		'day-to-day': m.injury_status_day_to_day
	};
</script>

{#if 'injury' in props}
	<span class="status-tag injury {props.injury}">{injuryLabels[props.injury]()}</span>
{:else}
	<span class="status-tag">{labels[props.status]()}</span>
{/if}

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

	.injury {
		font-size: var(--injury-tag-size);
		letter-spacing: var(--injury-tag-letter-spacing);
		white-space: nowrap;
	}

	.out {
		border-color: var(--color-accent);
		color: var(--color-accent-light);
	}

	.doubtful,
	.questionable {
		color: var(--color-ink);
	}

	.probable,
	.day-to-day {
		color: var(--color-muted);
	}
</style>
