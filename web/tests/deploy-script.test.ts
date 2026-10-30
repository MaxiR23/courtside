// web/tests/deploy-script.test.ts
//
// Cross-cutting test: scripts/deploy.sh, run with bash inside a throwaway git repository with a
// local bare origin and stub ssh, curl, vercel and pnpm first on PATH. Nothing reaches the network.
//
// Tested:
// - The build gets every feed URL of web/.env.example at the site's /api/feeds path
// - web/.env is left byte-identical and VIDEO_PLATFORM_NAME is not set by the script
// - The Vercel folder is replaced except .vercel and deployed to production
// - The api side moves the machine to the exact checked commit over SSH, checks its HEAD before
//   the rebuild and waits for the healthy service
// - The script refuses a missing key, a dirty tree, another branch, a main behind or ahead of
//   origin, an unlinked Vercel folder and an unknown mode, and no output holds a .env.deploy value
// - DEPLOY_SSH_HOST accepts only letters, digits, dots, hyphens and underscores, not a
//   leading -, and a refused value stops the run before any ssh call without being printed
// - The Vercel folder guards refuse /, the home folder, the repository, a folder containing it,
//   their symlinks and a relative path, before any delete
// - The api side fails when the remote update fails, when the machine is not on the checked
//   commit, when its commit cannot be read, when the rebuild fails and when the service is not
//   healthy in 180 s
// - In web and all modes DEPLOY_VERCEL_PROJECT_ID must be set and equal the projectId of the
//   linked folder's .vercel/project.json, read by plain text; api mode does not need it
// - A variable in the build's environment wins over web/.env (the loadEnv call SvelteKit makes)
//
// What is covered:
// - Happy paths (all, web and api modes, a host alias with digits and an underscore, a project.json
//   whose projectId matches, one line or pretty-printed)
// - Edge cases (empty value versus missing line, untracked file, api-only mode, the precedence control,
//   api mode without DEPLOY_VERCEL_PROJECT_ID, an empty projectId, the value under orgId)
// - Error cases (a host starting with -, holding a space or an =, every refusal above and a HEAD mismatch, a failed HEAD read, a failed rebuild and a failing health check,
//   a projectId that differs, a project.json without projectId)
//
// Run with: cd web && pnpm exec vitest run tests/deploy-script.test.ts
//
// SEE: scripts/deploy.sh, .env.deploy.example, deploy/vercel.json, docs/deploy.md, web/.env.example
// @vitest-environment node
import { spawnSync } from 'node:child_process';
import {
	chmodSync,
	copyFileSync,
	existsSync,
	mkdirSync,
	mkdtempSync,
	readdirSync,
	readFileSync,
	realpathSync,
	rmSync,
	statSync,
	symlinkSync,
	writeFileSync
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { loadEnv } from 'vite';

const root = join(import.meta.dirname, '..', '..');
const realExample = readFileSync(join(root, 'web', '.env.example'), 'utf8');
const realDoc = readFileSync(join(root, 'docs', 'deploy.md'), 'utf8');

const sshHost = 'courtside-test.example';
const siteUrl = 'https://www.example.com';
const projectId = 'prj_example_courtside';
const secretValues = [sshHost, siteUrl, projectId];

const stubs: Record<string, string> = {
	ssh: `#!/usr/bin/env bash
printf 'ssh\\t%s\\t%s\\n' "$PWD" "$*" >> "$STUB_LOG"
last="\${@: -1}"
case "$last" in
  *"ps --format"*) printf '%s\\n' "\${STUB_SSH_HEALTH:-healthy}" ;;
  *"rev-parse HEAD"*) [ -z "\${STUB_SSH_HEAD_FAIL:-}" ] || exit 1; printf '%s\\n' "\${STUB_SSH_HEAD:-$(git rev-parse HEAD)}" ;;
  *"git merge --ff-only"*) [ -z "\${STUB_SSH_UPDATE_FAIL:-}" ] || exit 1 ;;
  *"compose up"*) [ -z "\${STUB_SSH_REBUILD_FAIL:-}" ] || exit 1 ;;
esac
`,
	sleep: `#!/usr/bin/env bash
printf 'sleep\\t%s\\t%s\\n' "$PWD" "$*" >> "$STUB_LOG"
`,
	curl: `#!/usr/bin/env bash
printf 'curl\\t%s\\t%s\\n' "$PWD" "$*" >> "$STUB_LOG"
last="\${@: -1}"
case "$last" in
  */api/health) printf '%s' "\${STUB_HEALTH_CODE:-200}" ;;
  *) printf '200' ;;
esac
`,
	vercel: `#!/usr/bin/env bash
printf 'vercel\\t%s\\t%s\\n' "$PWD" "$*" >> "$STUB_LOG"
`,
	pnpm: `#!/usr/bin/env bash
printf 'pnpm\\t%s\\t%s\\n' "$PWD" "$*" >> "$STUB_LOG"
if [ "$*" = "run build" ]; then
  mkdir -p build/_app
  printf 'page\\n' > build/200.html
  env | grep -E '^([A-Z_]+_FEED_URL|VIDEO_PLATFORM_NAME)=' > build/_app/env.txt || true
fi
`
};

let tmp: string;
let repo: string;
let vercelDir: string;
let log: string;

function git(args: string[], cwd = repo): string {
	const result = spawnSync(
		'git',
		['-c', 'user.name=Test', '-c', 'user.email=test@example.com', ...args],
		{
			cwd,
			encoding: 'utf8',
			env: { ...process.env, GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: '/dev/null' }
		}
	);
	if (result.status !== 0) throw new Error(`git ${args.join(' ')}: ${result.stderr}`);
	return result.stdout.trim();
}

function feedNames(): string[] {
	return [...realExample.matchAll(/^([A-Z_]+_FEED_URL)=/gm)].map((m) => m[1]);
}

function documentedPaths(): Record<string, string> {
	const paths: Record<string, string> = {};
	for (const m of realDoc.matchAll(
		/([A-Z_]+_FEED_URL)=https:\/\/www\.example\.com\/api\/feeds\/([^`\s,]+?)(?=[`,\s]|$)/g
	)) {
		paths[m[1]] = m[2];
	}
	return paths;
}

function writeDeployEnv(lines: string[]): void {
	writeFileSync(join(repo, '.env.deploy'), lines.join('\n') + '\n');
}

function defaultDeployEnv(): string[] {
	return [
		`DEPLOY_SSH_HOST=${sshHost}`,
		`DEPLOY_SITE_URL=${siteUrl}`,
		`DEPLOY_VERCEL_DIR=${vercelDir}`,
		`DEPLOY_VERCEL_PROJECT_ID=${projectId}`
	];
}

function run(args: string[] = [], extra: Record<string, string> = {}) {
	const result = spawnSync('bash', ['scripts/deploy.sh', ...args], {
		cwd: repo,
		encoding: 'utf8',
		timeout: 25000,
		env: {
			PATH: `${join(tmp, 'bin')}:${process.env.PATH ?? ''}`,
			HOME: tmp,
			GIT_CONFIG_NOSYSTEM: '1',
			GIT_CONFIG_GLOBAL: '/dev/null',
			STUB_LOG: log,
			STUB_HEALTH_CODE: '200',
			...extra
		}
	});
	const output = `${result.stdout}${result.stderr}`;
	for (const value of secretValues) expect(output).not.toContain(value);
	expect(output).not.toContain(vercelDir);
	return { status: result.status, stdout: result.stdout, stderr: result.stderr };
}

function stubLog(): string[] {
	return existsSync(log)
		? readFileSync(log, 'utf8')
				.split('\n')
				.filter((line) => line !== '')
		: [];
}

function filesUnder(dir: string): string[] {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		return statSync(path).isDirectory() ? filesUnder(path) : [path];
	});
}

beforeEach(() => {
	tmp = realpathSync(mkdtempSync(join(tmpdir(), 'deploy-')));
	repo = join(tmp, 'repo');
	vercelDir = join(tmp, 'vercel');
	log = join(tmp, 'stub.log');

	mkdirSync(join(tmp, 'bin'));
	for (const [name, body] of Object.entries(stubs)) {
		writeFileSync(join(tmp, 'bin', name), body);
		chmodSync(join(tmp, 'bin', name), 0o755);
	}

	git(['init', '--bare', '-b', 'main', join(tmp, 'origin.git')], tmp);
	mkdirSync(join(repo, 'scripts'), { recursive: true });
	mkdirSync(join(repo, 'deploy'));
	mkdirSync(join(repo, 'web'));
	copyFileSync(join(root, 'scripts', 'deploy.sh'), join(repo, 'scripts', 'deploy.sh'));
	chmodSync(join(repo, 'scripts', 'deploy.sh'), 0o755);
	copyFileSync(join(root, 'deploy', 'vercel.json'), join(repo, 'deploy', 'vercel.json'));
	copyFileSync(join(root, '.gitignore'), join(repo, '.gitignore'));
	copyFileSync(join(root, 'web', '.gitignore'), join(repo, 'web', '.gitignore'));
	git(['init', '-b', 'main'], repo);
	git(['add', '-A'], repo);
	git(['commit', '-m', 'fixture'], repo);
	git(['remote', 'add', 'origin', join(tmp, 'origin.git')], repo);
	git(['push', 'origin', 'main'], repo);
	git(['fetch', 'origin'], repo);

	const webEnv = feedNames().map((name) => `${name}=http://127.0.0.1:8000/feeds/x.json`);
	writeFileSync(
		join(repo, 'web', '.env'),
		[...webEnv, 'VIDEO_PLATFORM_NAME=Example Video', ''].join('\n')
	);
	mkdirSync(join(vercelDir, '.vercel'), { recursive: true });
	writeFileSync(
		join(vercelDir, '.vercel', 'project.json'),
		`{"projectId":"${projectId}","orgId":"team_example"}`
	);
	writeFileSync(join(vercelDir, 'old.txt'), 'stale');
	writeDeployEnv(defaultDeployEnv());
});

afterEach(() => {
	rmSync(tmp, { recursive: true, force: true });
});

describe('scripts/deploy.sh', () => {
	it("builds web with every feed URL of web/.env.example at the site's /api/feeds path", () => {
		const result = run();
		expect(result.status).toBe(0);
		const lines = readFileSync(join(vercelDir, '_app', 'env.txt'), 'utf8')
			.split('\n')
			.filter(Boolean);
		const built = Object.fromEntries(
			lines
				.map((line) => [line.slice(0, line.indexOf('=')), line.slice(line.indexOf('=') + 1)])
				.filter(([name]) => name.endsWith('_FEED_URL'))
		);
		const names = feedNames();
		expect(names).toHaveLength(23);
		expect(Object.keys(built).sort()).toEqual([...names].sort());
		const paths = documentedPaths();
		expect(Object.keys(paths).sort()).toEqual([...names].sort());
		for (const name of names) {
			expect(built[name]).toBe(`${siteUrl}/api/feeds/${paths[name]}`);
		}
	});

	it('leaves no 127.0.0.1 in the build output and does not set VIDEO_PLATFORM_NAME', () => {
		expect(run().status).toBe(0);
		for (const file of filesUnder(vercelDir)) {
			expect(readFileSync(file, 'utf8')).not.toContain('127.0.0.1');
		}
		expect(readFileSync(join(vercelDir, '_app', 'env.txt'), 'utf8')).not.toContain(
			'VIDEO_PLATFORM_NAME'
		);
	});

	it('leaves web/.env byte-identical', () => {
		const before = readFileSync(join(repo, 'web', '.env'));
		expect(run().status).toBe(0);
		expect(readFileSync(join(repo, 'web', '.env')).equals(before)).toBe(true);
	});

	it('replaces the Vercel folder except .vercel, adds vercel.json and deploys to production there', () => {
		expect(run().status).toBe(0);
		expect(existsSync(join(vercelDir, 'old.txt'))).toBe(false);
		expect(existsSync(join(vercelDir, '.vercel', 'project.json'))).toBe(true);
		expect(existsSync(join(vercelDir, '200.html'))).toBe(true);
		expect(readFileSync(join(vercelDir, 'vercel.json'), 'utf8')).toBe(
			readFileSync(join(root, 'deploy', 'vercel.json'), 'utf8')
		);
		const lines = stubLog();
		expect(lines).toContain(`vercel\t${vercelDir}\tdeploy --prod`);
		const pnpm = lines.filter((line) => line.startsWith('pnpm\t'));
		expect(pnpm).toEqual([
			`pnpm\t${join(repo, 'web')}\tinstall --frozen-lockfile`,
			`pnpm\t${join(repo, 'web')}\trun build`
		]);
	});

	it('checks / and /api/health on the site at the end', () => {
		const result = run();
		expect(result.status).toBe(0);
		const curl = stubLog().filter((line) => line.startsWith('curl\t'));
		expect(curl).toHaveLength(2);
		expect(curl[0]).toMatch(new RegExp(`${siteUrl}/$`));
		expect(curl[1]).toMatch(new RegExp(`${siteUrl}/api/health$`));
	});

	it('api: updates the machine over SSH and waits until the api service is healthy', () => {
		const commit = git(['rev-parse', 'HEAD']);
		const result = run(['api']);
		expect(result.status).toBe(0);
		const lines = stubLog();
		const ssh = lines.filter((line) => line.startsWith('ssh\t'));
		expect(ssh).toHaveLength(4);
		expect(
			ssh[0].endsWith(
				`\t${sshHost} cd ~/courtside && git fetch --quiet origin && git merge --ff-only ${commit}`
			)
		).toBe(true);
		expect(ssh[1].endsWith(`\t${sshHost} cd ~/courtside && git rev-parse HEAD`)).toBe(true);
		expect(
			ssh[2].endsWith(`\t${sshHost} cd ~/courtside && sudo docker compose up -d --build`)
		).toBe(true);
		expect(ssh[3]).toContain('ps --format');
		expect(ssh.some((line) => line.includes('git pull'))).toBe(false);
		expect(lines.some((line) => /^(pnpm|vercel)\t/.test(line))).toBe(false);
	});

	it('api: fails after 36 health checks and 35 waits when the service never gets healthy', () => {
		const result = run(['api'], { STUB_SSH_HEALTH: 'starting' });
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('not healthy after 180 seconds');
		const lines = stubLog();
		const ssh = lines.filter((line) => line.startsWith('ssh\t'));
		expect(ssh.filter((line) => line.includes('ps --format'))).toHaveLength(36);
		expect(ssh.filter((line) => line.includes('git merge --ff-only'))).toHaveLength(1);
		expect(ssh).toHaveLength(39);
		expect(lines.filter((line) => line.endsWith('\t5') && line.startsWith('sleep\t'))).toHaveLength(
			35
		);
		expect(lines.filter((line) => line.startsWith('sleep\t'))).toHaveLength(35);
		expect(lines.some((line) => line.startsWith('curl\t'))).toBe(false);
	});

	it('api: fails when the remote update fails, without checking health', () => {
		const result = run(['api'], { STUB_SSH_UPDATE_FAIL: '1' });
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('api: the remote update failed');
		const lines = stubLog();
		expect(lines.filter((line) => line.startsWith('ssh\t'))).toHaveLength(1);
		expect(lines.some((line) => line.includes('rev-parse HEAD'))).toBe(false);
		expect(lines.some((line) => line.includes('compose up'))).toBe(false);
		expect(lines.some((line) => line.includes('ps --format'))).toBe(false);
		expect(lines.some((line) => /^(sleep|curl)\t/.test(line))).toBe(false);
	});

	it('api: stops before the rebuild when the machine is not on the checked commit', () => {
		const commit = git(['rev-parse', 'HEAD']);
		const other = 'f'.repeat(40);
		const result = run([], { STUB_SSH_HEAD: other });
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain(other);
		expect(result.stderr).toContain(commit);
		expect(result.stderr).toContain('not on the checked commit');
		const lines = stubLog();
		expect(lines.some((line) => line.includes('compose up'))).toBe(false);
		expect(lines.some((line) => line.includes('ps --format'))).toBe(false);
		expect(lines.some((line) => /^(pnpm|vercel|sleep|curl)\t/.test(line))).toBe(false);
	});

	it('api: stops before the rebuild when the machine commit cannot be read', () => {
		const result = run(['api'], { STUB_SSH_HEAD_FAIL: '1' });
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain("api: cannot read the machine's commit");
		expect(stubLog().some((line) => line.includes('compose up'))).toBe(false);
	});

	it('api: fails when the rebuild fails, without checking health', () => {
		const result = run(['api'], { STUB_SSH_REBUILD_FAIL: '1' });
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('api: the rebuild failed');
		const lines = stubLog();
		expect(lines.some((line) => line.includes('ps --format'))).toBe(false);
		expect(lines.some((line) => /^(sleep|curl)\t/.test(line))).toBe(false);
	});

	it.each(['DEPLOY_SSH_HOST', 'DEPLOY_SITE_URL', 'DEPLOY_VERCEL_DIR', 'DEPLOY_VERCEL_PROJECT_ID'])(
		'fails naming the missing key %s, without printing any value',
		(key) => {
			for (const empty of [false, true]) {
				const lines = defaultDeployEnv().filter((line) => !line.startsWith(`${key}=`));
				writeDeployEnv(empty ? [...lines, `${key}=`] : lines);
				const result = run();
				expect(result.status).not.toBe(0);
				expect(result.stderr).toContain(`set ${key} in .env.deploy`);
				expect(stubLog()).toEqual([]);
			}
		}
	);

	function writeProjectJson(content: string): void {
		writeFileSync(join(vercelDir, '.vercel', 'project.json'), content);
	}

	it('web: stops naming DEPLOY_VERCEL_PROJECT_ID when it is missing, before the build', () => {
		for (const empty of [false, true]) {
			const lines = defaultDeployEnv().filter(
				(line) => !line.startsWith('DEPLOY_VERCEL_PROJECT_ID=')
			);
			writeDeployEnv(empty ? [...lines, 'DEPLOY_VERCEL_PROJECT_ID='] : lines);
			const result = run(['web']);
			expect(result.status).not.toBe(0);
			expect(result.stderr).toContain('set DEPLOY_VERCEL_PROJECT_ID in .env.deploy');
			expect(stubLog()).toEqual([]);
			expect(existsSync(join(vercelDir, 'old.txt'))).toBe(true);
		}
	});

	it('api: runs without DEPLOY_VERCEL_PROJECT_ID', () => {
		writeDeployEnv(
			defaultDeployEnv().filter((line) => !line.startsWith('DEPLOY_VERCEL_PROJECT_ID='))
		);
		const result = run(['api']);
		expect(result.status).toBe(0);
		expect(stubLog().filter((line) => line.startsWith('ssh\t'))).toHaveLength(4);
	});

	it.each(['all', 'web'])(
		'%s: stops before the build when the linked projectId differs, naming both keys and printing neither value',
		(mode) => {
			writeProjectJson('{"projectId":"prj_example_other","orgId":"team_example"}');
			const result = run([mode]);
			expect(result.status).not.toBe(0);
			expect(result.stderr).toContain('DEPLOY_VERCEL_PROJECT_ID');
			expect(result.stderr).toContain('projectId');
			expect(`${result.stdout}${result.stderr}`).not.toContain('prj_example_other');
			expect(stubLog()).toEqual([]);
			expect(existsSync(join(vercelDir, 'old.txt'))).toBe(true);
		}
	);

	it.each(['all', 'web'])(
		'%s: stops before the build when .vercel/project.json has no projectId, naming the key',
		(mode) => {
			writeProjectJson('{"orgId":"team_example"}');
			const result = run([mode]);
			expect(result.status).not.toBe(0);
			expect(result.stderr).toContain('projectId');
			expect(stubLog()).toEqual([]);
			expect(existsSync(join(vercelDir, 'old.txt'))).toBe(true);
		}
	);

	it('stops when projectId is empty in .vercel/project.json', () => {
		writeProjectJson('{"projectId":"","orgId":"team_example"}');
		const result = run(['web']);
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('projectId not found in .vercel/project.json');
		expect(stubLog()).toEqual([]);
	});

	it('web: accepts a pretty-printed project.json whose projectId matches', () => {
		writeProjectJson(`{\n  "orgId": "team_example",\n  "projectId": "${projectId}"\n}\n`);
		const result = run(['web']);
		expect(result.status).toBe(0);
		expect(stubLog()).toContain(`vercel\t${vercelDir}\tdeploy --prod`);
	});

	it('does not take orgId as projectId', () => {
		writeProjectJson(`{"orgId":"${projectId}"}`);
		const result = run(['web']);
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('projectId not found in .vercel/project.json');
	});

	it('api: accepts a host alias of letters, digits, dots, hyphens and underscores and reaches ssh', () => {
		const host = 'courtside_vm-2.example';
		writeDeployEnv([
			`DEPLOY_SSH_HOST=${host}`,
			`DEPLOY_SITE_URL=${siteUrl}`,
			`DEPLOY_VERCEL_DIR=${vercelDir}`
		]);
		const result = run(['api']);
		expect(result.status).toBe(0);
		const sshLines = stubLog().filter((line) => line.startsWith('ssh\t'));
		expect(sshLines).toHaveLength(4);
		for (const line of sshLines) expect(line).toContain(`\t${host} `);
		expect(`${result.stdout}${result.stderr}`).not.toContain(host);
	});

	it.each([
		['starting with -', '-oProxyCommand=false'],
		['holding a space', 'courtside vm'],
		['holding an =', 'courtside=vm']
	])('refuses DEPLOY_SSH_HOST %s before any ssh call, without printing it', (_label, host) => {
		writeDeployEnv([
			`DEPLOY_SSH_HOST=${host}`,
			`DEPLOY_SITE_URL=${siteUrl}`,
			`DEPLOY_VERCEL_DIR=${vercelDir}`
		]);
		const result = run(['api']);
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('DEPLOY_SSH_HOST');
		expect(`${result.stdout}${result.stderr}`).not.toContain(host);
		expect(stubLog()).toEqual([]);
	});

	it('fails when .env.deploy does not exist', () => {
		rmSync(join(repo, '.env.deploy'));
		const result = run();
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('.env.deploy not found');
		expect(stubLog()).toEqual([]);
	});

	it('refuses a dirty tree, tracked or untracked', () => {
		writeFileSync(join(repo, 'deploy', 'vercel.json'), '{}\n');
		let result = run();
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('the working tree is not clean');
		expect(stubLog()).toEqual([]);

		git(['checkout', '--', 'deploy/vercel.json']);
		writeFileSync(join(repo, 'new-file.txt'), 'x');
		result = run();
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('the working tree is not clean');
		expect(stubLog()).toEqual([]);
	});

	it('refuses a branch other than main', () => {
		git(['switch', '-c', 'feature']);
		const result = run();
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('deploy runs only from main');
		expect(stubLog()).toEqual([]);
	});

	it('refuses when main is not equal to origin/main', () => {
		writeFileSync(join(repo, 'local.txt'), 'x');
		git(['add', 'local.txt']);
		git(['commit', '-m', 'local']);
		const result = run();
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('main is not equal to origin/main');
		expect(stubLog()).toEqual([]);
	});

	it('refuses a Vercel folder without .vercel and deletes nothing', () => {
		rmSync(join(vercelDir, '.vercel'), { recursive: true });
		const result = run();
		expect(result.status).not.toBe(0);
		expect(existsSync(join(vercelDir, 'old.txt'))).toBe(true);
	});

	describe('Vercel folder guards', () => {
		// Every case runs inside the mktemp sandbox. Each refusal comes before any delete, so
		// the sentinel files and the fixture repository must survive and no build or deploy runs.
		function link(dir: string, ignored = false): string {
			mkdirSync(join(dir, '.vercel'), { recursive: true });
			writeFileSync(join(dir, '.vercel', 'project.json'), '{}');
			// Inside the repository only ignored paths keep the tree clean.
			const sentinel = join(dir, ignored ? '.vercel' : '', 'sentinel.txt');
			writeFileSync(sentinel, 'keep');
			return sentinel;
		}

		// run() sets HOME to the fixture root; a case about another guard moves it elsewhere.
		const elsewhere = '/nonexistent-home-for-test';

		function expectRefused(
			value: string,
			message: string,
			sentinels: string[],
			extra: Record<string, string> = {}
		): void {
			writeDeployEnv([
				`DEPLOY_SSH_HOST=${sshHost}`,
				`DEPLOY_SITE_URL=${siteUrl}`,
				`DEPLOY_VERCEL_DIR=${value}`
			]);
			const result = run(['web'], extra);
			expect(result.status).not.toBe(0);
			expect(result.stderr).toContain(message);
			expect(stubLog().some((line) => /^(pnpm|vercel)\t/.test(line))).toBe(false);
			for (const sentinel of sentinels) expect(existsSync(sentinel)).toBe(true);
			expect(existsSync(join(repo, 'scripts', 'deploy.sh'))).toBe(true);
			expect(existsSync(join(vercelDir, 'old.txt'))).toBe(true);
		}

		it('refuses a folder that contains the repository', () => {
			const sentinel = link(tmp);
			expectRefused(tmp, 'must not contain the repository', [sentinel], { HOME: elsewhere });
		});

		it('refuses a symlink to a folder that contains the repository', () => {
			const sentinel = link(tmp);
			const alias = join(tmp, 'alias');
			symlinkSync(tmp, alias);
			expectRefused(alias, 'must not contain the repository', [sentinel], { HOME: elsewhere });
		});

		it('refuses the home folder', () => {
			const home = join(tmp, 'home');
			const sentinel = link(home);
			expectRefused(home, 'must not be the home folder', [sentinel], { HOME: home });
		});

		it('refuses a symlink to the home folder', () => {
			const home = join(tmp, 'home');
			const sentinel = link(home);
			const alias = join(tmp, 'home-alias');
			symlinkSync(home, alias);
			expectRefused(alias, 'must not be the home folder', [sentinel], { HOME: home });
		});

		it('refuses the repository itself', () => {
			expectRefused(repo, 'must be outside the repository', []);
		});

		it('refuses a symlink into the repository', () => {
			const sentinel = link(join(repo, 'web'), true);
			const alias = join(tmp, 'into-repo');
			symlinkSync(join(repo, 'web'), alias);
			expectRefused(alias, 'must be outside the repository', [sentinel]);
		});

		it('refuses a relative path', () => {
			const sentinel = link(join(tmp, 'relative'));
			expectRefused('../relative', 'must be an absolute path', [sentinel]);
		});

		it('refuses the root folder before any delete', () => {
			// "/" has no .vercel/project.json, so the run stops even without the guard; the
			// message proves the explicit arm fires first.
			expectRefused('/', 'must not be the root folder', []);
		});
	});

	it('fails when /api/health does not answer 200', () => {
		const result = run([], { STUB_HEALTH_CODE: '502' });
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('smoke: /api/health answered 502');
	});

	it('rejects an unknown mode with the usage line', () => {
		const result = run(['everything']);
		expect(result.status).not.toBe(0);
		expect(result.stderr).toContain('usage: scripts/deploy.sh [api|web|all]');
		expect(stubLog()).toEqual([]);
	});
});

describe('build-time env precedence', () => {
	let dir: string;

	beforeEach(() => {
		dir = mkdtempSync(join(tmpdir(), 'loadenv-'));
		writeFileSync(join(dir, '.env'), 'GAMES_FEED_URL=http://127.0.0.1:8000/feeds/games.json\n');
	});

	afterEach(() => {
		vi.unstubAllEnvs();
		rmSync(dir, { recursive: true, force: true });
	});

	it("a variable in the build's environment wins over web/.env", () => {
		expect(loadEnv('production', dir, '').GAMES_FEED_URL).toBe(
			'http://127.0.0.1:8000/feeds/games.json'
		);
		vi.stubEnv('GAMES_FEED_URL', 'https://www.example.com/api/feeds/games.json');
		expect(loadEnv('production', dir, '').GAMES_FEED_URL).toBe(
			'https://www.example.com/api/feeds/games.json'
		);
	});
});
