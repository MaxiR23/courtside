<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMonogram from '#lib/components/TeamMonogram.svelte';
	import type { InjuriesSection } from '#lib/game/types.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Props = { injuries: InjuriesSection };

	let { injuries }: Props = $props();

	const teams = $derived([injuries.away, injuries.home]);
</script>

<div class="injuries">
	{#each teams as team (team.code)}
		<BlueprintFrame>
			<div class="team">
				<div class="head">
					<TeamMonogram code={team.code} size="injury" />
					<h3>{team.name}</h3>
				</div>
				{#if team.injuries.length === 0}
					<p class="none">{m.game_injuries_none()}</p>
				{:else}
					<ul>
						{#each team.injuries as row, i (i)}
							<li>
								<div class="line">
									<span class="name">{row.name}</span>
									<StatusTag injury={row.status} />
								</div>
								{#if row.comment}<p class="comment">{row.comment}</p>{/if}
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		</BlueprintFrame>
	{/each}
</div>

<style>
	.injuries {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--injury-column-min)), 1fr));
		gap: var(--game-list-gap);
	}

	.team {
		display: grid;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
	}

	.head {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	h3 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--injury-name-size);
		text-transform: uppercase;
	}

	ul {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	li {
		display: grid;
		gap: var(--day-strip-gap);
		padding: var(--game-list-gap) 0;
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.line {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--injury-name-size);
	}

	.comment,
	.none {
		margin: 0;
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}
</style>
