<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { TeamInjuryRow } from '#lib/team/types.ts';

	type Props = { injuries: TeamInjuryRow[] };

	let { injuries }: Props = $props();
</script>

{#if injuries.length === 0}
	<p class="none">{m.game_injuries_none()}</p>
{:else}
	<ul class="injuries">
		{#each injuries as row, i (i)}
			<li>
				<BlueprintFrame>
					<div class="row">
						<div class="line">
							<div class="who">
								<span class="name">{row.name}</span>
								{#if row.line}<span class="detail">{row.line}</span>{/if}
							</div>
							<StatusTag injury={row.status} />
						</div>
						{#if row.comment}<p class="comment">{row.comment}</p>{/if}
					</div>
				</BlueprintFrame>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.injuries {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--injury-column-min)), 1fr));
		gap: var(--game-list-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.row {
		display: grid;
		gap: var(--day-strip-gap);
		padding: var(--game-list-gap);
	}

	.line {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.who {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--injury-name-size);
	}

	.detail,
	.comment,
	.none {
		margin: 0;
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}
</style>
