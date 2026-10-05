// web/tests/lib/components/MessageRow.test.ts
//
// Tests for the MessageRow component.
//
// Tested:
// - Shows its text inside a blueprint frame
//
// What is covered:
// - Its only state
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/MessageRow.test.ts
//
// SEE: web/src/lib/components/MessageRow.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import MessageRow from '../../../src/lib/components/MessageRow.svelte';

describe('MessageRow', () => {
	it('shows its text inside a blueprint frame', () => {
		render(MessageRow, { props: { text: 'Nothing here.' } });
		expect(screen.getByText('Nothing here.').closest('.blueprint-frame')).not.toBeNull();
	});
});
