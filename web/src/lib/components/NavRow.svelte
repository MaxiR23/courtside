<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import { formatDate } from '#lib/format/locale.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Props = { today: Date; scheduleHref: ResolvedPathname };

	let { today, scheduleHref }: Props = $props();

	const dateOptions: Intl.DateTimeFormatOptions = {
		weekday: 'short',
		month: 'short',
		day: 'numeric',
		year: 'numeric'
	};

	const iso = $derived(
		`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
	);
</script>

<nav class="nav-row">
	<span class="brand">
		<span class="brand-mark" aria-hidden="true"></span>
		<span class="brand-name">{m.site_name()}</span>
	</span>
	<time class="date" datetime={iso}>{formatDate(today, dateOptions)}</time>
	<a class="games" href={scheduleHref}>{m.nav_games()}</a>
</nav>

<style>
	.nav-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.brand {
		display: inline-flex;
		align-items: center;
		gap: var(--game-list-gap);
		margin-inline-end: auto;
	}

	.brand-mark {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: var(--brand-mark-size);
		height: var(--brand-mark-size);
		border: var(--hairline) solid var(--color-accent);
	}

	.brand-mark::after {
		content: '';
		width: var(--brand-mark-inner-size);
		height: var(--brand-mark-inner-size);
		background: var(--color-accent);
	}

	.brand-name {
		font-family: var(--font-heading);
		font-size: var(--brand-size);
		letter-spacing: var(--brand-letter-spacing);
		text-transform: uppercase;
	}

	.date {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-muted);
	}

	.games {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-ink);
		text-decoration: none;
	}
</style>
