<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import CalendarSheet from '#lib/components/CalendarSheet.svelte';
	import DateButton from '#lib/components/DateButton.svelte';
	import NavMenuSheet from '#lib/components/NavMenuSheet.svelte';
	import NavSearchTrigger from '#lib/components/NavSearchTrigger.svelte';
	import type { DateCalendar } from '#lib/calendar/types.ts';
	import { formatDate } from '#lib/format/locale.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type HomeExtras = {
		today: Date;
		spoilerFree: boolean;
		onSpoilerFreeToggle: () => void;
		calendar?: DateCalendar; // set: the date opens the calendar sheet
	};
	type Props = {
		page: 'home' | 'standings' | 'cup' | 'all-star' | 'playoffs' | 'detail'; // each current page marks its own link; detail: none
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

	// With no day selected (the games feed is not in) the sheet opens on the month of the date shown.
	const calendar = $derived(
		home?.calendar ? { ...home.calendar, selectedDay: home.calendar.selectedDay ?? iso } : undefined
	);
	type Tournament = {
		page: 'cup' | 'all-star' | 'playoffs';
		label: string;
		href: ResolvedPathname;
	};
	const tournaments: Tournament[] = $derived([
		// The Cup link resolves its own route so removing the Cup touches only this file (ADR 0030).
		{ page: 'cup', label: m.nav_cup(), href: resolve('/cup') },
		// The All-Star link resolves its own route so removing the All-Star touches only this file (ADR 0030).
		{ page: 'all-star', label: m.nav_all_star(), href: resolve('/all-star') },
		// The Playoffs link resolves its own route so removing the playoffs touches only this file (ADR 0030).
		{ page: 'playoffs', label: m.nav_playoffs(), href: resolve('/playoffs') }
	]);
	const tournamentCurrent = $derived(tournaments.some((t) => t.page === page));

	let tournamentsOpen = $state(false);
	let menuOpen = $state(false);
	let calendarOpen = $state(false);
	let tournamentsBox = $state<HTMLElement>();
	let tournamentsButton = $state<HTMLButtonElement>();
	let menuButton = $state<HTMLButtonElement>();

	// A navigation closes what the nav opened.
	afterNavigate(() => {
		tournamentsOpen = false;
		menuOpen = false;
		calendarOpen = false;
	});

	// A layout change drops what belongs to the other layout: the mobile sheets and the dropdown.
	$effect(() => {
		void layout;
		tournamentsOpen = false;
		menuOpen = false;
		calendarOpen = false;
	});

	function onWindowClick(event: MouseEvent) {
		if (tournamentsOpen && !tournamentsBox?.contains(event.target as Node)) tournamentsOpen = false;
	}

	function onWindowKeydown(event: KeyboardEvent) {
		if (tournamentsOpen && event.key === 'Escape') {
			event.preventDefault(); // the page's own Esc handlers (the bracket) leave it alone
			tournamentsOpen = false;
			tournamentsButton?.focus();
		}
	}

	function closeMenu() {
		menuOpen = false;
		menuButton?.focus();
	}

	function openCalendar() {
		menuOpen = false;
		calendarOpen = true;
	}

	function closeCalendar() {
		calendarOpen = false;
		menuButton?.focus();
	}

	const sheetLinks = $derived([
		{
			label: page === 'home' ? m.nav_games() : m.hero_all_games(),
			href: gamesHref,
			current: page === 'home'
		},
		{ label: m.nav_standings(), href: standingsHref, current: page === 'standings' },
		...tournaments.map((t) => ({ label: t.label, href: t.href, current: page === t.page }))
	]);
	const sheetHome = $derived(
		home
			? {
					dateText: formatDate(home.today, dateOptions),
					datetime: iso,
					onDate: calendar ? openCalendar : undefined,
					spoilerFree: home.spoilerFree,
					onSpoilerFreeToggle: home.onSpoilerFreeToggle
				}
			: undefined
	);
</script>

<svelte:window onclick={onWindowClick} onkeydowncapture={onWindowKeydown} />

<nav class="nav-row" class:mobile={layout === 'mobile'}>
	<span class="brand">
		<img class="brand-logo" src="/logo-mark.svg" alt="" aria-hidden="true" />
		<span class="brand-name">{m.site_name()}</span>
	</span>
	{#if layout === 'desktop'}
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
			<div class="tournaments" bind:this={tournamentsBox}>
				<button
					type="button"
					class="link tournaments-button"
					class:current={tournamentCurrent}
					aria-expanded={tournamentsOpen}
					bind:this={tournamentsButton}
					onclick={() => (tournamentsOpen = !tournamentsOpen)}
				>
					{m.nav_tournaments()}
					<svg viewBox="0 0 12 12" aria-hidden="true"><path d="m2 4 4 4 4-4" /></svg>
				</button>
				{#if tournamentsOpen}
					<ul class="dropdown">
						{#each tournaments as t (t.page)}
							<li>
								<a
									class="item"
									class:current={page === t.page}
									aria-current={page === t.page ? 'page' : undefined}
									href={t.href}
									onclick={() => (tournamentsOpen = false)}
								>
									{t.label}
								</a>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
			{#if home}
				{#if calendar}
					<DateButton
						text={formatDate(home.today, dateOptions)}
						datetime={iso}
						{calendar}
						{layout}
					/>
				{:else}
					<time class="date" datetime={iso}>{formatDate(home.today, dateOptions)}</time>
				{/if}
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
	{:else}
		<NavSearchTrigger {layout} />
		<button
			type="button"
			class="menu-button"
			aria-label={m.nav_menu_open()}
			aria-haspopup="dialog"
			aria-expanded={menuOpen}
			bind:this={menuButton}
			onclick={() => (menuOpen = true)}
		>
			<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
		</button>
	{/if}
</nav>
{#if menuOpen}
	<NavMenuSheet links={sheetLinks} home={sheetHome} onClose={closeMenu} />
{/if}
{#if calendarOpen && calendar}
	<CalendarSheet {calendar} {layout} onClose={closeCalendar} />
{/if}

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

	.brand-logo {
		flex: none;
		width: var(--brand-mark-size);
		height: var(--brand-mark-size);
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

	.link {
		display: inline-flex;
		align-items: center;
		gap: var(--day-strip-gap);
		min-height: var(--hit-target-size);
		padding: 0;
		background: none;
		border: 0;
		font: inherit;
		font-size: var(--nav-link-size);
		letter-spacing: var(--nav-link-letter-spacing);
		text-transform: uppercase;
		text-decoration: none;
		color: var(--color-muted);
		cursor: pointer;
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

	.tournaments {
		position: relative;
		display: inline-flex;
	}

	.dropdown {
		position: absolute;
		top: 100%;
		inset-inline-start: 0;
		z-index: var(--nav-menu-z-index);
		margin: 0;
		padding: 0;
		list-style: none;
		border: var(--hairline) solid var(--color-divider);
		background: var(--color-surface);
	}

	.item {
		display: flex;
		align-items: center;
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		font-size: var(--nav-link-size);
		letter-spacing: var(--nav-link-letter-spacing);
		text-transform: uppercase;
		text-decoration: none;
		white-space: nowrap;
		color: var(--color-muted);
	}

	.item:hover {
		color: var(--color-ink);
	}

	.item.current {
		color: var(--color-ink);
		text-decoration: underline;
		text-decoration-color: var(--color-accent);
		text-decoration-thickness: var(--hairline);
	}

	.tournaments-button svg {
		flex: none;
		width: var(--past-chevron-size);
		height: var(--past-chevron-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.menu-button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: var(--hit-target-size);
		height: var(--hit-target-size);
		padding: 0;
		background: none;
		border: 0;
		color: var(--color-ink);
		cursor: pointer;
	}

	.menu-button svg {
		flex: none;
		width: var(--nav-icon-size);
		height: var(--nav-icon-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
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
