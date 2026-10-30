// web/tests/section-tabs-mini-waits-for-its-block.test.ts
//
// Cross-cutting test: the tab bar's mini score or text shows only once the page's watched header
// block has left the top of the viewport. SectionTabs has no prop or branch that shows it earlier,
// and every page that renders it passes the element to watch.
//
// Tested:
// - The files to scan are found, and the scan cannot pass by matching nothing
// - The matcher flags an optional or nullable reveal, an extra prop, a reveal default, a fade or an
//   aria-hidden that does not follow `revealed`, and a render site without an element to watch
// - The matcher passes the real forms (the multi-line game page tag, an indexed element)
// - SectionTabs passes its six rules, and every render site passes the element to watch
//
// What is covered:
// - Happy path (the real source passes), edge cases (multi-line tags) and the error case (each
//   forbidden form is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/section-tabs-mini-waits-for-its-block.test.ts
//
// SEE: web/src/lib/components/SectionTabs.svelte
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const webDir = join(import.meta.dirname, '..');
const componentsDir = join(webDir, 'src/lib/components');
const routesDir = join(webDir, 'src/routes');
const sectionTabsPath = join(componentsDir, 'SectionTabs.svelte');

function svelteUnder(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return svelteUnder(path);
		return entry.name.endsWith('.svelte') ? [path] : [];
	});
}

function propsBlock(source: string): string {
	return /type Props = \{([\s\S]*?)\n\t\};/.exec(source)?.[1] ?? '';
}

function declaredProps(source: string): string[] {
	return [...propsBlock(source).matchAll(/^\t\t(\w+)\??:/gm)].map((match) => match[1]);
}

function revealLine(source: string): string {
	return (
		propsBlock(source)
			.split('\n')
			.find((line) => /^\t\treveal\??:/.test(line)) ?? ''
	);
}

// Each rule returns the problems it finds in a SectionTabs source.
function componentProblems(source: string): string[] {
	const problems: string[] = [];
	const props = declaredProps(source).join(',');
	if (props !== 'tabs,miniScore,mini,reveal') problems.push(`props are ${props}`);

	const line = revealLine(source);
	const outside = line.replace(/\{[^}]*\}/, '').replace(/\/\/.*$/, '');
	if (!/^\t\treveal:\s*\{/.test(line) || /\|\s*(null|undefined)/.test(outside)) {
		problems.push('reveal is not required and non-nullable');
	}

	if (/\$props\(\)/.test(source)) {
		const destructuring = /let\s*\{([^}]*)\}\s*:\s*Props\s*=\s*\$props\(\)/.exec(source)?.[1] ?? '';
		if (/\breveal\s*=/.test(destructuring)) problems.push('reveal has a default');
	}

	if (!/const revealed = \$derived\(watch\.passed\);/.test(source)) {
		problems.push('revealed is not $derived(watch.passed)');
	}
	if (/reveal\s*[!=]==?\s*null|reveal\s*[!=]=\s*undefined|!reveal\b|reveal\?\./.test(source)) {
		problems.push('a branch on reveal being absent');
	}

	for (const match of source.matchAll(/miniScoreFade\(([^)]*)\)/g)) {
		if (match[1].trim() !== 'revealed') problems.push(`miniScoreFade(${match[1]})`);
	}
	for (const match of source.matchAll(/aria-hidden=(\{[^}]*\})/g)) {
		if (match[1] !== "{revealed ? undefined : 'true'}") problems.push(`aria-hidden=${match[1]}`);
	}

	const hidden = /(?:^|\n)\t\.mini-score\s*\{([^}]*)\}/.exec(source)?.[1] ?? '';
	if (!/opacity:\s*0;/.test(hidden)) problems.push('.mini-score does not start at opacity 0');
	const shown = [...source.matchAll(/([^{}]+)\{[^}]*opacity:\s*1;[^}]*\}/g)].map((match) =>
		match[1].trim()
	);
	if (shown.some((selector) => selector !== '.open .mini-score')) {
		problems.push(`opacity 1 set by ${shown.join(', ')}`);
	}
	return problems;
}

const WATCHED = /reveal=\{\{\s*element:\s*(?!\s)(?!null\b|undefined\b)[^,}]+,\s*layout\b/;

function renderSites(source: string): string[] {
	return [...source.matchAll(/<SectionTabs\b[\s\S]*?\/>/g)].map((match) => match[0]);
}

function sitesWithoutElement(source: string): string[] {
	return renderSites(source).filter((tag) => !WATCHED.test(tag));
}

const sources = [...svelteUnder(componentsDir), ...svelteUnder(routesDir)];
const sectionTabs = readFileSync(sectionTabsPath, 'utf8');

const props = (...lines: string[]) =>
	`type Props = {\n${lines.map((line) => `\t\t${line}`).join('\n')}\n\t};`;
const baseProps = [
	'tabs: readonly { id: string; label: string }[];',
	'miniScore?: MiniScore | null;',
	'mini?: string | null;'
];

describe('the scan', () => {
	it('finds SectionTabs.svelte and its props', () => {
		expect(declaredProps(sectionTabs)).toEqual(['tabs', 'miniScore', 'mini', 'reveal']);
	});

	it('finds the render sites', () => {
		const count = sources.reduce(
			(sum, file) => sum + renderSites(readFileSync(file, 'utf8')).length,
			0
		);
		expect(count).toBeGreaterThanOrEqual(4);
	});
});

describe('the matcher', () => {
	const withProps = (...lines: string[]) => props(...baseProps, ...lines);

	it('flags an optional reveal', () => {
		const code = withProps('reveal?: { element: HTMLElement | null; layout: RowLayout };');
		expect(componentProblems(code).length).toBeGreaterThan(0);
	});

	it('flags a nullable reveal', () => {
		const code = withProps('reveal: { element: HTMLElement | null; layout: RowLayout } | null;');
		expect(componentProblems(code)).toContain('reveal is not required and non-nullable');
	});

	it('flags an extra prop', () => {
		const code = withProps(
			'reveal: { element: HTMLElement | null; layout: RowLayout };',
			'alwaysShow?: boolean;'
		);
		expect(componentProblems(code)[0]).toMatch(/^props are/);
	});

	it('flags a reveal default', () => {
		const code = `${withProps('reveal: { element: null };')}\nlet { tabs, reveal = null }: Props = $props();`;
		expect(componentProblems(code)).toContain('reveal has a default');
	});

	it('flags a fade or an aria-hidden that does not follow revealed', () => {
		expect(componentProblems('miniScoreFade(true)')).toContain('miniScoreFade(true)');
		expect(componentProblems('miniScoreFade(reveal === null || revealed)')).toContain(
			'miniScoreFade(reveal === null || revealed)'
		);
		const aria = "aria-hidden={reveal !== null && !revealed ? 'true' : undefined}";
		expect(componentProblems(aria)).toContain(`aria-hidden=${aria.slice(12)}`);
		expect(componentProblems('const x = reveal !== null && watch.passed;')).toContain(
			'a branch on reveal being absent'
		);
	});

	it('flags a mini score shown by a selector other than .open', () => {
		const css =
			'\n\t.mini-score {\n\t\topacity: 0;\n\t}\n\t.reveal.open .mini-score {\n\t\topacity: 1;\n\t}';
		expect(componentProblems(css).some((problem) => problem.startsWith('opacity 1'))).toBe(true);
	});

	it('flags a render site without an element to watch', () => {
		expect(sitesWithoutElement('<SectionTabs tabs={t} mini={m} />')).toHaveLength(1);
		expect(
			sitesWithoutElement('<SectionTabs tabs={t} reveal={{ element: null, layout }} />')
		).toHaveLength(1);
		expect(sitesWithoutElement('<SectionTabs tabs={t} reveal={null} />')).toHaveLength(1);
	});

	it('passes the real render forms', () => {
		const multiLine = `<SectionTabs
	tabs={view.tabs}
	reveal={{ element: scoreboard, layout }}
/>`;
		expect(sitesWithoutElement(multiLine)).toEqual([]);
		const indexed =
			"<SectionTabs {tabs} reveal={{ element: tabTitles[i] ?? null, layout: 'desktop' }} />";
		expect(sitesWithoutElement(indexed)).toEqual([]);
	});
});

describe('the rule', () => {
	it('SectionTabs shows nothing before the watched block has passed', () => {
		expect(componentProblems(sectionTabs)).toEqual([]);
	});

	it('every SectionTabs render site passes the element to watch', () => {
		const offenders = sources.flatMap((file) =>
			sitesWithoutElement(readFileSync(file, 'utf8')).map(
				(tag) => `${relative(webDir, file)}: ${tag.replace(/\s+/g, ' ')}`
			)
		);
		expect(offenders).toEqual([]);
	});
});
