// web/tests/sticky-bar-is-the-one-stuck-state.test.ts
//
// Cross-cutting test: the tab bar's mini score or text shows only while the bar is stuck to the top
// of the viewport, and that state has one owner. SectionTabs reads it from the shared sticky bar
// state, nothing else builds that state or draws the mini, and every page that renders SectionTabs
// passes only its layout, never an element to watch.
//
// Tested:
// - The files to scan are found, and the scan cannot pass by matching nothing
// - The matcher flags an optional or nullable layout, an extra prop, a reveal prop, a stuck state
//   derived from anything else (the page-level `stickyBar.stuck` included), an assignment to the
//   per-bar or page-level state, a fade or an aria-hidden that does not follow `revealed`, a render
//   site without a layout or with a reveal, and a second owner of the state or of the mini
// - The matcher passes the real forms (the multi-line page tag, the preview tag)
// - SectionTabs passes its rules, every render site passes, and the state has one owner
//
// What is covered:
// - Happy path (the real source passes), edge cases (multi-line tags) and the error case (each
//   forbidden form is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/sticky-bar-is-the-one-stuck-state.test.ts
//
// SEE: web/src/lib/components/SectionTabs.svelte
// SEE: web/src/lib/scroll/scrolled-past.svelte.ts
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const webDir = join(import.meta.dirname, '..');
const libDir = join(webDir, 'src/lib');
const componentsDir = join(libDir, 'components');
const routesDir = join(webDir, 'src/routes');
const sectionTabsPath = join(componentsDir, 'SectionTabs.svelte');
const modulePath = join(libDir, 'scroll/scrolled-past.svelte.ts');

function filesUnder(dir: string, extensions: string[]): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return filesUnder(path, extensions);
		return extensions.some((extension) => entry.name.endsWith(extension)) ? [path] : [];
	});
}

function propsBlock(source: string): string {
	return /type Props = \{([\s\S]*?)\n\t\};/.exec(source)?.[1] ?? '';
}

function declaredProps(source: string): string[] {
	return [...propsBlock(source).matchAll(/^\t\t(\w+)\??:/gm)].map((match) => match[1]);
}

// Each rule returns the problems it finds in a SectionTabs source.
function componentProblems(source: string): string[] {
	const problems: string[] = [];
	const props = declaredProps(source).join(',');
	if (props !== 'tabs,miniScore,mini,layout') problems.push(`props are ${props}`);

	if (!/^\t\tlayout:\s*RowLayout;/m.test(propsBlock(source))) {
		problems.push('layout is not required and non-nullable');
	}

	if (!/import \{ stickyBar \} from '#lib\/scroll\/scrolled-past\.svelte\.ts';/.test(source)) {
		problems.push('stickyBar is not imported from the shared module');
	}
	if (!/const revealed = \$derived\(stickyBar\.stuckOf\(bar\)\);/.test(source)) {
		problems.push('revealed is not $derived(stickyBar.stuckOf(bar))');
	}
	if (
		/new IntersectionObserver|new ScrolledPastWatch|new StickyBarState|addEventListener\('scroll'|querySelector/.test(
			source
		)
	) {
		problems.push('SectionTabs builds its own watch');
	}

	for (const match of source.matchAll(/miniScoreFade\(([^)]*)\)/g)) {
		if (match[1].trim() !== 'revealed') problems.push(`miniScoreFade(${match[1]})`);
	}
	for (const match of source.matchAll(/aria-hidden=(\{[^}]*\})/g)) {
		if (match[1] !== "{revealed ? undefined : 'true'}") problems.push(`aria-hidden=${match[1]}`);
	}
	if (/class:open=\{/.test(source) && !/class:open=\{revealed\}/.test(source)) {
		problems.push('open does not follow revealed');
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

function renderSites(source: string): string[] {
	return [...source.matchAll(/<SectionTabs\b[\s\S]*?\/>/g)].map((match) => match[0]);
}

function siteProblems(source: string): string[] {
	return renderSites(source).flatMap((tag) => {
		const found: string[] = [];
		if (!/\blayout=|\{layout\}/.test(tag)) found.push('no layout');
		if (/\breveal\b/.test(tag)) found.push('passes reveal');
		return found.map((problem) => `${problem}: ${tag.replace(/\s+/g, ' ')}`);
	});
}

// The rules on who owns the state, over a map of file -> source.
function ownerProblems(files: Record<string, string>): string[] {
	const problems: string[] = [];
	for (const [file, source] of Object.entries(files)) {
		const isModule = file === 'src/lib/scroll/scrolled-past.svelte.ts';
		const isTabs = file === 'src/lib/components/SectionTabs.svelte';
		if (!isModule && /new StickyBarState\(/.test(source))
			problems.push(`${file}: builds the state`);
		if (!isTabs && /stickyBar\.observe\(/.test(source)) problems.push(`${file}: registers a bar`);
		if (/stickyBar\.(stuck|bottom|stuckOf|bottomOf)\s*=[^=]/.test(source))
			problems.push(`${file}: assigns the state`);
		if (!isTabs && /miniScoreFade\(/.test(source)) problems.push(`${file}: fades the mini`);
		if (!isTabs && /class="mini-score"/.test(source)) problems.push(`${file}: draws the mini`);
	}
	return problems;
}

const sources = [...filesUnder(componentsDir, ['.svelte']), ...filesUnder(routesDir, ['.svelte'])];
const owned = Object.fromEntries(
	[...filesUnder(libDir, ['.svelte', '.ts']), ...filesUnder(routesDir, ['.svelte', '.ts'])].map(
		(file) => [relative(webDir, file), readFileSync(file, 'utf8')]
	)
);
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
		expect(declaredProps(sectionTabs)).toEqual(['tabs', 'miniScore', 'mini', 'layout']);
	});

	it('finds the render sites', () => {
		const count = sources.reduce(
			(sum, file) => sum + renderSites(readFileSync(file, 'utf8')).length,
			0
		);
		expect(count).toBeGreaterThanOrEqual(4);
	});

	it('finds the shared module and its one instance', () => {
		expect(readFileSync(modulePath, 'utf8')).toContain(
			'export const stickyBar = new StickyBarState();'
		);
		expect(Object.keys(owned)).toContain('src/lib/components/SectionTabs.svelte');
	});
});

describe('the matcher', () => {
	const withProps = (...lines: string[]) => props(...baseProps, ...lines);

	it('flags an optional or nullable layout', () => {
		expect(componentProblems(withProps('layout?: RowLayout;'))).toContain(
			'layout is not required and non-nullable'
		);
		expect(componentProblems(withProps('layout: RowLayout | null;'))).toContain(
			'layout is not required and non-nullable'
		);
	});

	it('flags an extra prop and a reveal prop', () => {
		const extra = withProps('layout: RowLayout;', 'alwaysShow?: boolean;');
		expect(componentProblems(extra)[0]).toMatch(/^props are/);
		const reveal = withProps('layout: RowLayout;', 'reveal?: { element: HTMLElement | null };');
		expect(componentProblems(reveal)[0]).toMatch(/^props are/);
	});

	it('flags a stuck state derived from anything else', () => {
		const problem = 'revealed is not $derived(stickyBar.stuckOf(bar))';
		expect(componentProblems('const revealed = $derived(watch.passed);')).toContain(problem);
		expect(
			componentProblems('const revealed = $derived(stickyBar.stuckOf(bar) || alwaysShow);')
		).toContain(problem);
		expect(componentProblems('const revealed = $derived(stickyBar.stuck);')).toContain(problem);
	});

	it('flags a component that builds its own watch', () => {
		expect(componentProblems('new IntersectionObserver(() => {})')).toContain(
			'SectionTabs builds its own watch'
		);
		expect(componentProblems("document.querySelector('.x')")).toContain(
			'SectionTabs builds its own watch'
		);
	});

	it('flags a fade or an aria-hidden that does not follow revealed', () => {
		expect(componentProblems('miniScoreFade(true)')).toContain('miniScoreFade(true)');
		const aria = "aria-hidden={revealed ? undefined : 'false'}";
		expect(componentProblems(aria)).toContain(`aria-hidden=${aria.slice(12)}`);
		expect(componentProblems('class:open={always}')).toContain('open does not follow revealed');
	});

	it('flags a mini score shown by a selector other than .open', () => {
		const css =
			'\n\t.mini-score {\n\t\topacity: 0;\n\t}\n\t.stuck .mini-score {\n\t\topacity: 1;\n\t}';
		expect(componentProblems(css).some((problem) => problem.startsWith('opacity 1'))).toBe(true);
	});

	it('flags a render site without a layout or with a reveal', () => {
		expect(siteProblems('<SectionTabs tabs={t} mini={m} />')).toHaveLength(1);
		const withReveal = siteProblems('<SectionTabs tabs={t} reveal={{ element: x, layout }} />');
		expect(withReveal.some((problem) => problem.startsWith('passes reveal'))).toBe(true);
	});

	it('flags a second owner of the state or of the mini', () => {
		const second = {
			'src/lib/a.ts': 'const s = new StickyBarState();',
			'src/lib/b.svelte': 'stickyBar.observe(a, b);',
			'src/lib/c.svelte': 'const f = miniScoreFade(true);',
			'src/lib/d.svelte': '<span class="mini-score"></span>',
			'src/lib/e.ts': 'stickyBar.stuck = true;',
			'src/lib/f.ts': 'stickyBar.stuckOf = () => true;'
		};
		expect(ownerProblems(second)).toHaveLength(6);
	});

	it('passes the real render forms', () => {
		const multiLine = `<SectionTabs
	tabs={view.tabs}
	{layout}
/>`;
		expect(siteProblems(multiLine)).toEqual([]);
		expect(siteProblems('<SectionTabs {tabs} {miniScore} layout="desktop" />')).toEqual([]);
	});
});

describe('the rule', () => {
	it('SectionTabs shows the mini only from the shared stuck state', () => {
		expect(componentProblems(sectionTabs)).toEqual([]);
	});

	it('every SectionTabs render site passes the layout and no element', () => {
		const offenders = sources.flatMap((file) =>
			siteProblems(readFileSync(file, 'utf8')).map(
				(problem) => `${relative(webDir, file)}: ${problem}`
			)
		);
		expect(offenders).toEqual([]);
	});

	it('only the shared module builds the state, only SectionTabs registers the bar and draws the mini', () => {
		expect(ownerProblems(owned)).toEqual([]);
	});
});
