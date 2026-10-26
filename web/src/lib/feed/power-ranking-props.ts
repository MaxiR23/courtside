import type { PowerRankingFeed } from '#lib/contract/power-ranking.ts';
import { formatNumber } from '#lib/format/locale.ts';
import { m } from '#lib/paraglide/messages.js';
import type { PowerRankingView } from '#lib/standings/types.ts';
import { teamMark } from '#lib/team/mark.ts';

/** docs/design-standings-search.md, Power ranking: the top 10 by default. */
export const TOP_ROWS = 10;

/**
 * The power ranking section: every text as the feed sends it, in the feed's order. Null unless the
 * feed is available and holds teams, so the section is hidden (ADR 0075).
 */
export function toPowerRankingView(feed: PowerRankingFeed): PowerRankingView | null {
	if (feed.state !== 'available' || feed.teams.length === 0) return null;
	return {
		teams: feed.teams.map((team) => ({
			code: team.team.code,
			rank: team.tied
				? m.power_ranking_rank_tied({ rank: formatNumber(team.rank) })
				: formatNumber(team.rank),
			tied: team.tied,
			team: teamMark({
				code: team.team.code,
				name: team.team.name,
				city: team.team.city,
				logo: team.team.logo
			}),
			record: team.record,
			rating: team.rating,
			ratingMuted: team.ratingNegative,
			offense: team.offense,
			defense: team.defense,
			projected: team.projected,
			playoffs: team.playoffs,
			playoffsMuted: team.playoffsLow,
			title: team.title,
			titleShare: team.titleShare
		})),
		showAllLabel: m.power_ranking_show_all({ count: formatNumber(feed.teams.length) }),
		showTopLabel: m.power_ranking_show_top({ count: formatNumber(TOP_ROWS) })
	};
}
