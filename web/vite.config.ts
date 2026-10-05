import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			adapter: adapter(),
			prerender: {
				handleHttpError: ({ path, status, message }) => {
					// The component preview route exists only in development and answers 404 in the build.
					if (path === '/preview' && status === 404) return;
					throw new Error(message);
				}
			}
		}),
		svelteTesting()
	],
	test: {
		environment: 'jsdom',
		include: ['tests/**/*.test.ts']
	}
});
