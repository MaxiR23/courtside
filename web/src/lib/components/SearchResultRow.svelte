<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
	import type { SearchPlayerRow, SearchTeamRow } from '#lib/search/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		row: { kind: 'team'; team: SearchTeamRow } | { kind: 'player'; player: SearchPlayerRow };
		href: ResolvedPathname;
		layout: RowLayout;
		active: boolean;
		id: string;
		onHover: () => void;
		onOpen: () => void;
	};

	let { row, href, layout, active, id, onHover, onOpen }: Props = $props();
</script>

<a
	class="row"
	class:active
	{href}
	{id}
	aria-current={active ? 'true' : undefined}
	onmouseenter={onHover}
	onclick={onOpen}
>
	{#if row.kind === 'team'}
		<span class="tile" class:plain={!row.team.strip}>
			<TeamMonogram code={row.team.code} size="search" />
			{#if row.team.strip}
				<span class="strip" aria-hidden="true">
					<span class="half" style:background-color={row.team.strip.primary}></span>
					<span class="half" style:background-color={row.team.strip.secondary}></span>
				</span>
			{/if}
		</span>
		<span class="text">
			<span class="title">
				<span class="city">{row.team.city}</span>
				<span class="name">{row.team.name}</span>
			</span>
			<span class="meta">{row.team.meta}</span>
		</span>
		<span class="record">{row.team.record}</span>
	{:else}
		<PlayerAvatar name={row.player.name} photo={row.player.photo} size="search" />
		{@const line = layout === 'mobile' ? row.player.lineShort : row.player.line}
		<span class="text">
			<span class="title">
				<span class="name">{layout === 'mobile' ? row.player.shortName : row.player.name}</span>
				{#if row.player.injury}<StatusTag injury={row.player.injury} />{/if}
			</span>
			{#if line}<span class="meta">{line}</span>{/if}
		</span>
		<span class="team">
			<span
				class="bar"
				class:plain={row.player.teamColor === null}
				style:background-color={row.player.teamColor}
				aria-hidden="true"
			></span>
			<span class="code">{row.player.teamCode}</span>
		</span>
	{/if}
</a>

<style>
	.row {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		padding: var(--search-row-inset);
		margin-inline: var(--search-row-inset);
		color: inherit;
		text-decoration: none;
	}

	.row.active {
		background: var(--search-active-row);
		border-radius: var(--search-radius);
	}

	.tile {
		display: grid;
		flex: none;
		width: var(--search-tile-size);
		border-radius: var(--search-tile-radius);
		overflow: hidden;
	}

	.plain {
		background: var(--color-surface);
	}

	.strip {
		display: flex;
		height: var(--search-strip-height);
	}

	.half {
		flex: 1;
	}

	.text {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-width: 0;
	}

	.title {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--search-row-inset);
	}

	.city {
		color: var(--color-muted);
	}

	.city,
	.name {
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
	}

	.meta {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.record {
		font-size: var(--player-name-size);
		font-variant-numeric: tabular-nums;
		color: var(--color-muted);
	}

	.team {
		display: inline-flex;
		flex: none;
		align-items: center;
		gap: var(--search-row-inset);
	}

	.bar {
		align-self: stretch;
		width: var(--search-team-bar-width);
	}

	.bar.plain {
		background: var(--color-surface);
	}

	.code {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
	}

	.row:focus-visible {
		outline: var(--focus-ring-width) solid var(--color-accent);
		outline-offset: var(--focus-ring-offset);
	}
</style>
