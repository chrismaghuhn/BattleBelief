'use strict';

// This extractor is deliberately small and has no inputs. It is executed from
// the verified Showdown checkout after its explicit TypeScript build.
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const {Dex} = require(path.join(process.cwd(), 'dist', 'sim', 'dex'));

const extractorSource = fs.readFileSync(__filename);
const digest = `sha256:${crypto.createHash('sha256').update(extractorSource).digest('hex')}`;
const format = Dex.formats.get('gen9ou');
const formatDex = Dex.forFormat(format);
const table = Dex.formats.getRuleTable(format);

function sortedStrings(values) {
	return [...values].map(String).sort();
}

function compareStrings(left, right) {
	if (left < right) return -1;
	if (left > right) return 1;
	return 0;
}

function sortedEntries(entries) {
	return [...entries]
		.map(([key, value]) => ({key: String(key), value: String(value)}))
		.sort((left, right) => compareStrings(left.key, right.key) || compareStrings(left.value, right.value));
}

function sortedComplexBans(values) {
	return [...values]
		.map(value => ({
			limit: Number(value[1]),
			rules: sortedStrings(value[0]),
			source: String(value[2]),
		}))
		.sort((left, right) => compareStrings(JSON.stringify(left), JSON.stringify(right)));
}

const snapshot = {
	schema_version: 1,
	extractor_id: 'battlebelief-showdown-ruleset-extractor-v1',
	extractor_digest: digest,
	format: {
		id: format.id,
		name: format.name,
		mod: format.mod,
		game_type: format.gameType,
		gen: formatDex.gen,
		rated: Boolean(format.rated),
		ruleset: sortedStrings(format.ruleset),
		base_ruleset: sortedStrings(format.baseRuleset),
		banlist: sortedStrings(format.banlist),
		restricted: sortedStrings(format.restricted),
		unbanlist: sortedStrings(format.unbanlist),
	},
	resolved_rule_table: {
		entries: sortedEntries(table.entries()),
		value_rules: sortedEntries(table.valueRules.entries()),
		complex_bans: sortedComplexBans(table.complexBans),
		complex_team_bans: sortedComplexBans(table.complexTeamBans),
		tag_rules: [...table.tagRules]
			.map(([prefix, tag]) => ({prefix: String(prefix), tag: String(tag)}))
			.sort((left, right) => compareStrings(left.prefix, right.prefix) || compareStrings(left.tag, right.tag)),
		team_constraints: {
			ev_limit: table.evLimit,
			max_level: table.maxLevel,
			max_move_count: table.maxMoveCount,
			max_team_size: table.maxTeamSize,
			min_level: table.minLevel,
			min_source_gen: table.minSourceGen,
			min_team_size: table.minTeamSize,
		},
	},
};

process.stdout.write(JSON.stringify(snapshot));
