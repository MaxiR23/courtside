import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	if (import.meta.env.DEV) {
		const { default: Preview } = await import('./Preview.svelte');
		return { Preview };
	}
	error(404, 'Not found');
};
