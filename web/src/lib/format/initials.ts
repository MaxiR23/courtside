// The initials rule of player photos and guest tiles: the first word's initial
// plus the last word's initial of a display name, uppercased.
// SEE: docs/adr/0026-one-guest-team-rule.md

export function initials(name: string): string {
	const words = name.split(/\s+/).filter(Boolean);
	const first = words[0]?.charAt(0) ?? '';
	const last = words.length > 1 ? (words[words.length - 1]?.charAt(0) ?? '') : '';
	return `${first}${last}`.toUpperCase();
}
