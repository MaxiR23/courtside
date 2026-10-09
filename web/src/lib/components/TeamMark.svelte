<script lang="ts">
	// The one component that draws a game side or an opponent: as a tile, as its
	// label (the code, or the name of a guest without a code), or as its name.
	// It follows the link rule of ADR 0025: no link for a guest, and a link only
	// when a teamHref is given. Future features (full calendar, brackets) reuse it.
	// SEE: docs/adr/0026-one-guest-team-rule.md
	import type { ComponentProps } from 'svelte';
	import type { ResolvedPathname } from '$app/types';
	import NameLink from '#lib/components/NameLink.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { teamLabel, teamTile, type TeamMarkTeam } from '#lib/team/mark.ts';

	type Props = {
		team: TeamMarkTeam;
		part: 'tile' | 'label' | 'name';
		size?: ComponentProps<typeof TeamMonogram>['size']; // tile only
		versus?: 'home' | 'away'; // label only: "vs DEN" or "@ DEN", never a link
		teamHref?: (code: string) => ResolvedPathname; // absent: never a link
	};

	let { team, part, size = 'large', versus, teamHref }: Props = $props();

	const href = $derived(teamHref && !team.guest && team.code !== null ? teamHref(team.code) : null);
	const label = $derived(teamLabel(team));
	const versusText = $derived(
		versus === 'home'
			? m.game_last_game_home({ team: label })
			: versus === 'away'
				? m.game_last_game_away({ team: label })
				: null
	);
</script>

{#if part === 'tile'}
	<TeamMonogram code={teamTile(team)} {size} href={href ?? undefined} />
{:else if part === 'label'}
	{#if versusText !== null}{versusText}{:else}<NameLink {href} text={label} />{/if}
{:else}
	<NameLink {href} text={team.name ?? label} />
{/if}
