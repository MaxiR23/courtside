<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import PageContainer from '#lib/components/PageContainer.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	const DAYS = Array.from({ length: 7 }, (_, i) => i); // the day strip's cells, as in DayStrip
	const CARDS = Array.from({ length: 3 }, (_, i) => i); // placeholder game cards
</script>

<PageContainer>
	<section class="schedule-skeleton" id="schedule" aria-busy="true">
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			<div class="strip">
				{#each DAYS as i (i)}
					<div class="day-bone">
						<span class="bone weekday-bone"></span>
						<span class="bone number-bone"></span>
						<span class="bone count-bone"></span>
					</div>
				{/each}
			</div>
			<ul class="cards">
				{#each CARDS as i (i)}
					<li>
						<BlueprintFrame>
							<div class="card-bone"><span class="bone"></span></div>
						</BlueprintFrame>
					</li>
				{/each}
			</ul>
		</div>
	</section>
</PageContainer>

<style>
	.schedule-skeleton {
		display: grid;
		gap: var(--game-list-gap);
		/* The container's top padding sits outside the anchor, so the scroll lands where it did. */
		scroll-margin-top: var(--side-padding);
	}

	.bones {
		display: grid;
		gap: var(--game-list-gap);
	}

	.strip {
		display: grid;
		grid-template-columns: repeat(7, minmax(0, 1fr));
		gap: var(--day-strip-gap);
	}

	.day-bone {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--day-strip-gap);
		padding: var(--day-strip-gap);
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
	}

	.cards {
		display: grid;
		gap: var(--game-list-gap);
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.card-bone {
		padding: var(--game-list-gap);
	}

	.bone {
		display: block;
		width: 100%;
		background: var(--color-surface);
		border-radius: var(--radius);
	}

	.weekday-bone,
	.count-bone {
		width: var(--skeleton-long-width);
		height: var(--label-size);
	}

	.number-bone {
		width: var(--skeleton-long-width);
		height: var(--day-number-size);
	}

	.card-bone .bone {
		height: var(--monogram-size);
	}
</style>
