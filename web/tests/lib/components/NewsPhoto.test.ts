// web/tests/lib/components/NewsPhoto.test.ts
//
// Tests for the NewsPhoto component.
//
// Tested:
// - The alt text is the headline, the image is lazy and keeps its size attributes
// - No photo draws no image
// - A load error removes the image and calls onFail once
//
// What is covered:
// - Both states (photo, no photo) and the error event
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NewsPhoto.test.ts
//
// SEE: web/src/lib/components/NewsPhoto.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import NewsPhoto from '../../../src/lib/components/NewsPhoto.svelte';

const photo = { url: 'https://images.example.com/a.jpg', width: 1280, height: 720 };

describe('NewsPhoto', () => {
	it('draws a lazy image whose alt is the headline', () => {
		render(NewsPhoto, { props: { photo, alt: 'A headline' } });
		const img = screen.getByRole('img', { name: 'A headline' });
		expect(img.getAttribute('loading')).toBe('lazy');
		expect(img.getAttribute('src')).toBe(photo.url);
		expect(img.getAttribute('width')).toBe('1280');
		expect(img.getAttribute('height')).toBe('720');
	});

	it('draws nothing without a photo', () => {
		const { container } = render(NewsPhoto, { props: { photo: null, alt: 'A headline' } });
		expect(container.querySelector('img')).toBeNull();
		expect(container.textContent).toBe('');
	});

	it('removes the image when it fails to load', async () => {
		const { container } = render(NewsPhoto, { props: { photo, alt: 'A headline' } });
		await fireEvent.error(screen.getByRole('img'));
		expect(container.querySelector('img')).toBeNull();
	});

	it('calls onFail once when the image fails to load', async () => {
		const onFail = vi.fn();
		render(NewsPhoto, { props: { photo, alt: 'A headline', onFail } });
		await fireEvent.error(screen.getByRole('img'));
		expect(onFail).toHaveBeenCalledTimes(1);
	});
});
