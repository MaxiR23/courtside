<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import { m } from '#lib/paraglide/messages.js';

	type Props = { allGamesHref: ResolvedPathname };

	let { allGamesHref }: Props = $props();
</script>

<div class="nav-row">
	<span class="brand">
		<span class="brand-mark" aria-hidden="true"></span>
		<span class="brand-name">{m.site_name()}</span>
	</span>
	<a class="all-games" href={allGamesHref}>
		<svg viewBox="0 0 24 24" aria-hidden="true"
			><path d="m12 19-7-7 7-7" /><path d="M19 12H5" /></svg
		>
		{m.hero_all_games()}
	</a>
</div>

<style>
	.nav-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.brand {
		display: inline-flex;
		align-items: center;
		gap: var(--game-list-gap);
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

	.all-games {
		display: inline-flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-height: var(--hit-target-size);
		font-size: var(--nav-link-size);
		letter-spacing: var(--nav-link-letter-spacing);
		text-transform: uppercase;
		color: var(--color-ink);
		text-decoration: none;
	}

	.all-games svg {
		width: var(--nav-icon-size);
		height: var(--nav-icon-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
