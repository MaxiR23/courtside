<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import PlayerPhoto from '#lib/components/PlayerPhoto.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { formatNumber } from '#lib/format/locale.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { Leader } from '#lib/schedule/types.ts';

	type Props = {
		away: Leader;
		home: Leader;
		teamHref: (code: string) => ResolvedPathname;
		marks?: boolean; // the inline mark before each code; false leaves it out
	};

	let { away, home, teamHref, marks = true }: Props = $props();

	const NO_VALUE = '—';
	const stat = (value: number | null): string => (value === null ? NO_VALUE : formatNumber(value));

	const leaders = $derived(
		[
			{ side: 'away', leader: away },
			{ side: 'home', leader: home }
		].map(({ side, leader }) => ({
			side,
			...leader,
			line: m.panel_leader_line({
				points: stat(leader.points),
				rebounds: stat(leader.rebounds),
				assists: stat(leader.assists)
			})
		}))
	);
</script>

<div class="leaders">
	{#each leaders as leader (leader.side)}
		<div class="leader">
			<PlayerPhoto player={leader} />
			<span class="info">
				<span class="leader-code"
					>{#if marks}<TeamMark
							part="tile"
							team={leader.team}
							size="inline"
							logo={leader.team.logo}
						/>{/if}<TeamMark part="label" team={leader.team} {teamHref} /></span
				>
				<span class="leader-name">{leader.firstName} {leader.lastName}</span>
				<span class="leader-line">{leader.line}</span>
			</span>
		</div>
	{/each}
</div>

<style>
	.leaders {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
	}

	.leader {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.info {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.leader-code {
		display: inline-flex;
		align-items: center;
		gap: var(--identity-inline-mark-gap);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-accent-light);
	}

	.leader-name {
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
		text-transform: uppercase;
	}

	.leader-line {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}
</style>
