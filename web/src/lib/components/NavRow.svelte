<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import NavSearchTrigger from '#lib/components/NavSearchTrigger.svelte';
	import { formatDate } from '#lib/format/locale.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type HomeExtras = {
		today: Date;
		spoilerFree: boolean;
		onSpoilerFreeToggle: () => void;
	};
	type Props = {
		page: 'home' | 'standings' | 'detail'; // home: "Games" current; standings: "Standings" current; detail: none
		gamesHref: ResolvedPathname; // Home: the schedule; every other page: Home
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		home?: HomeExtras; // Home only: the date and the spoiler-free toggle, after the links
	};

	let { page, gamesHref, standingsHref, layout, home }: Props = $props();

	const dateOptions: Intl.DateTimeFormatOptions = {
		weekday: 'short',
		month: 'short',
		day: 'numeric',
		year: 'numeric'
	};

	const iso = $derived(
		home
			? `${home.today.getFullYear()}-${String(home.today.getMonth() + 1).padStart(2, '0')}-${String(home.today.getDate()).padStart(2, '0')}`
			: ''
	);
</script>

<nav class="nav-row" class:mobile={layout === 'mobile'}>
	<span class="brand">
		<span class="brand-mark" aria-hidden="true"></span>
		<span class="brand-name">{m.site_name()}</span>
	</span>
	<div class="links">
		<a
			class="link"
			class:current={page === 'home'}
			aria-current={page === 'home' ? 'page' : undefined}
			href={gamesHref}
		>
			{page === 'home' ? m.nav_games() : m.hero_all_games()}
		</a>
		<a
			class="link"
			class:current={page === 'standings'}
			aria-current={page === 'standings' ? 'page' : undefined}
			href={standingsHref}
		>
			{m.nav_standings()}
		</a>
		{#if home}
			<time class="date" datetime={iso}>{formatDate(home.today, dateOptions)}</time>
			<button
				type="button"
				class="spoiler-free"
				aria-pressed={home.spoilerFree}
				onclick={home.onSpoilerFreeToggle}
			>
				{m.nav_spoiler_free()}
			</button>
		{/if}
	</div>
	<NavSearchTrigger {layout} />
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

	.links {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.mobile .links {
		flex-basis: 100%;
		order: 1;
	}

	.link {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		font-size: var(--nav-link-size);
		letter-spacing: var(--nav-link-letter-spacing);
		text-transform: uppercase;
		text-decoration: none;
		color: var(--color-muted);
	}

	.link:hover {
		color: var(--color-ink);
	}

	.link.current {
		color: var(--color-ink);
		text-decoration: underline;
		text-decoration-color: var(--color-accent);
		text-decoration-thickness: var(--hairline);
	}

	.spoiler-free {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		padding: 0;
		background: none;
		border: 0;
		font: inherit;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-ink);
		cursor: pointer;
	}

	.spoiler-free[aria-pressed='true'] {
		color: var(--color-accent-light);
	}
</style>
