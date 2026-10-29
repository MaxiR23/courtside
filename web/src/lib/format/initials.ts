// The initials rule of player photos and guest tiles, uppercased. Two forms:
// - a display name: the first word's initial plus the last word's initial;
// - a first and last name, where the feed carries them: the initial of each.
// SEE: docs/adr/0026-one-guest-team-rule.md

export function initials(name: string | { firstName: string; lastName: string }): string {
	if (typeof name !== 'string') {
		return `${name.firstName.trim().charAt(0)}${name.lastName.trim().charAt(0)}`.toUpperCase();
	}
	const words = name.split(/\s+/).filter(Boolean);
	const first = words[0]?.charAt(0) ?? '';
	const last = words.length > 1 ? (words[words.length - 1]?.charAt(0) ?? '') : '';
	return `${first}${last}`.toUpperCase();
}
