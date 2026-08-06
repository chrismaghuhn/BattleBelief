'use strict';

// This preload is intentionally CommonJS and uses only APIs present in Node 18,
// 20, and 22. NODE_OPTIONS propagates it to Node child and cluster processes.
// It is a hermeticity boundary, not a firewall: every denied operation emits
// the stable marker before throwing, so the owning Python process can fail closed.

const EXTERNAL_NETWORK_MARKER = 'BATTLEBELIEF_ORACLE_EXTERNAL_NETWORK_ATTEMPT';
const LOOPBACK_LISTEN_MARKER = 'BATTLEBELIEF_ORACLE_LOOPBACK_LISTEN';
let permittedInternalLookups = 0;

function denied() {
	try {
		process.stderr.write(EXTERNAL_NETWORK_MARKER + '\n');
	} catch {}
	throw new Error(EXTERNAL_NETWORK_MARKER);
}

function isLoopbackLiteral(value) {
	return value === '127.0.0.1' || value === '::1' || value === '[::1]';
}

function optionHost(value) {
	if (typeof value === 'string') return value;
	if (!value || typeof value !== 'object') return undefined;
	return value.host ?? value.hostname;
}

function connectionHost(args) {
	const first = args[0];
	return optionHost(first) ?? (typeof first === 'number' ? args[1] : undefined);
}

function requireLoopback(value) {
	if (!isLoopbackLiteral(value)) denied();
}

function literalLoopbackLookup(hostname, options, callback) {
	if (typeof options === 'function') callback = options;
	requireLoopback(hostname);
	if (typeof callback !== 'function') denied();
	callback(null, hostname, hostname === '::1' || hostname === '[::1]' ? 6 : 4);
}

function guardedConnectionArgs(args) {
	const first = args[0];
	if (first && typeof first === 'object' && !Array.isArray(first)) {
		const options = {...first};
		requireLoopback(optionHost(options));
		options.lookup = literalLoopbackLookup;
		return [options, ...args.slice(1)];
	}
	if (typeof first === 'number') {
		const host = args[1];
		requireLoopback(host);
		return [{port: first, host, lookup: literalLoopbackLookup}, ...args.slice(2)];
	}
	denied();
}

function patchConnect(module) {
	const connect = module.connect;
	let permittedSocketConnects = 0;
	module.connect = module.createConnection = function (...args) {
		const guardedArgs = guardedConnectionArgs(args);
		permittedSocketConnects++;
		try {
			return connect.apply(this, guardedArgs);
		} finally {
			permittedSocketConnects--;
		}
	};
	if (module.Socket && module.Socket.prototype) {
		const socketConnect = module.Socket.prototype.connect;
		module.Socket.prototype.connect = function (...args) {
			const guardedArgs = permittedSocketConnects ? args : guardedConnectionArgs(args);
			return socketConnect.apply(this, guardedArgs);
		};
	}
}

function patchListen(net) {
	const listen = net.Server.prototype.listen;
	net.Server.prototype.listen = function (...args) {
		const value = args[0];
		if (typeof value === 'string') denied();
		const host = optionHost(value) ?? args[1];
		requireLoopback(host);
		this.once('listening', () => {
			const address = this.address();
			if (!address || typeof address === 'string' || !isLoopbackLiteral(address.address)) denied();
			process.stderr.write(LOOPBACK_LISTEN_MARKER + '\n');
		});
		permittedInternalLookups++;
		try {
			return listen.apply(this, args);
		} finally {
			permittedInternalLookups--;
		}
	};
}

const net = require('node:net');
patchConnect(net);
patchListen(net);
patchConnect(require('node:tls'));

const dgram = require('node:dgram');
// A datagram socket can transmit without connect(), so every operation that
// can bind, transmit, or join a network group is denied. Socket construction
// and close remain usable only to let a caller clean up after the denial.
for (const method of [
	'bind', 'connect', 'send', 'addMembership', 'dropMembership',
	'addSourceSpecificMembership', 'dropSourceSpecificMembership',
	'setBroadcast', 'setMulticastInterface', 'setMulticastLoopback',
	'setMulticastTTL', 'setTTL',
]) {
	if (typeof dgram.Socket.prototype[method] === 'function') {
		dgram.Socket.prototype[method] = function () { denied(); };
	}
}

const dns = require('node:dns');
function patchResolverConstructor(container) {
	if (!container || typeof container.Resolver !== 'function') return;
	const Resolver = container.Resolver;
	for (const name of Object.getOwnPropertyNames(Resolver.prototype)) {
		if (name !== 'constructor' && typeof Resolver.prototype[name] === 'function') {
			Resolver.prototype[name] = function () { denied(); };
		}
	}
	function DeniedResolver() { denied(); }
	DeniedResolver.prototype = Resolver.prototype;
	Object.setPrototypeOf(DeniedResolver, Object.getPrototypeOf(Resolver));
	container.Resolver = DeniedResolver;
}

function patchDnsFunctions(container) {
	if (!container) return;
	for (const name of Object.getOwnPropertyNames(container)) {
		if (name !== 'Resolver' && typeof container[name] === 'function') {
			const original = container[name];
			container[name] = function (...args) {
				if (name === 'lookup' && permittedInternalLookups && isLoopbackLiteral(args[0])) {
					return original.apply(this, args);
				}
				denied();
			};
		}
	}
}
patchResolverConstructor(dns);
patchResolverConstructor(dns.promises);
patchDnsFunctions(dns);
patchDnsFunctions(dns.promises);

function patchHttp(module) {
	const request = module.request;
	module.request = function (...args) {
		const first = args[0];
		if (typeof first === 'string' || first instanceof URL) requireLoopback(new URL(first).hostname);
		else requireLoopback(optionHost(first));
		return request.apply(this, args);
	};
	module.get = function (...args) {
		const requestValue = module.request.apply(this, args);
		requestValue.end();
		return requestValue;
	};
}
patchHttp(require('node:http'));
patchHttp(require('node:https'));

if (typeof globalThis.fetch === 'function') {
	const fetch = globalThis.fetch;
	globalThis.fetch = function (input, init) {
		const target = input && typeof input === 'object' && 'url' in input ? input.url : input;
		requireLoopback(new URL(target).hostname);
		return fetch.call(this, input, init);
	};
}
