// web/tests/prefer-languages.ts
//
// Test helper: sets the browser language preference (navigator.languages),
// the input the locale runtime reads. Test files that use it call
// vi.restoreAllMocks() in afterEach.
//
// SEE: web/vite.config.ts (locale strategy)
import { vi } from 'vitest';

export function preferLanguages(tags: string[]) {
	vi.spyOn(navigator, 'languages', 'get').mockReturnValue(tags);
}
