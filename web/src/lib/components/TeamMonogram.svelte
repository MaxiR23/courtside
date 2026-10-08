<script lang="ts">
	type Props = {
		code: string;
		size: 'large' | 'small' | 'header' | 'header-mobile' | 'injury' | 'team';
	};

	let { code, size }: Props = $props();
</script>

<span class="team-monogram {size}">{code}</span>

<style>
	.team-monogram {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--body-size);
	}

	.large {
		width: var(--monogram-size);
		height: var(--monogram-size);
	}

	.small {
		width: var(--monogram-size-mobile);
		height: var(--monogram-size-mobile);
	}

	.header {
		width: var(--detail-monogram-size);
		height: var(--detail-monogram-size);
	}

	.injury {
		width: var(--injury-monogram-size);
		height: var(--injury-monogram-size);
	}

	.team {
		width: var(--team-code-box-size);
		height: var(--team-code-box-size);
	}

	.header-mobile {
		width: var(--detail-monogram-size-mobile);
		height: var(--detail-monogram-size-mobile);
	}
</style>
