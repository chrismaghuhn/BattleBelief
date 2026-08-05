"""Tests for the hermetic Node preload used by every Lab oracle process."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from battlebelief_lab.oracle.showdown import network as network_module
from battlebelief_lab.oracle.showdown.network import (
    EXTERNAL_NETWORK_MARKER,
    guarded_node_environment,
    network_guard_digest,
)


def _node() -> str:
    executable = "node.exe" if os.name == "nt" else "node"
    resolved = shutil.which(executable)
    if resolved is None:
        pytest.skip("Node is unavailable for this optional integration test")
    return str(Path(resolved))


def _guarded_environment() -> dict[str, str]:
    environment = {"PATH": os.environ.get("PATH", "")}
    if os.name == "nt":
        environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return environment


def test_guarded_environment_replaces_caller_node_options_and_has_a_digest() -> None:
    with guarded_node_environment({**_guarded_environment(), "NODE_OPTIONS": "--inspect"}) as env:
        assert env["NODE_OPTIONS"].startswith("--require ")
        assert "--inspect" not in env["NODE_OPTIONS"]
        assert " " in env["NODE_OPTIONS"]
    assert network_guard_digest().startswith("sha256:")


def test_packaged_preload_blocks_a_public_target_before_connecting() -> None:
    script = "require('node:net').connect({host: '198.51.100.7', port: 9});"
    with guarded_node_environment(_guarded_environment()) as env:
        completed = subprocess.run(
            [_node(), "-e", script],
            env=dict(env),
            check=False,
            capture_output=True,
            timeout=10,
        )
    assert completed.returncode != 0
    assert EXTERNAL_NETWORK_MARKER.encode("ascii") in completed.stderr


def test_packaged_preload_allows_only_a_literal_loopback_listener() -> None:
    script = (
        "const server=require('node:net').createServer();"
        "server.listen({host:'127.0.0.1',port:0},()=>server.close());"
    )
    with guarded_node_environment(_guarded_environment()) as env:
        completed = subprocess.run(
            [_node(), "-e", script],
            env=dict(env),
            check=False,
            capture_output=True,
            timeout=10,
        )
    assert completed.returncode == 0
    assert EXTERNAL_NETWORK_MARKER.encode("ascii") not in completed.stderr


def test_packaged_preload_allows_a_numeric_port_with_a_literal_loopback_host() -> None:
    script = (
        "const net=require('node:net');"
        "const server=net.createServer(socket=>socket.end());"
        "server.listen({host:'127.0.0.1',port:0},()=>{"
        "const client=net.connect(server.address().port,'127.0.0.1');"
        "client.on('close',()=>server.close());"
        "});"
    )
    with guarded_node_environment(_guarded_environment()) as env:
        completed = subprocess.run(
            [_node(), "-e", script],
            env=dict(env),
            check=False,
            capture_output=True,
            timeout=10,
        )
    assert completed.returncode == 0
    assert EXTERNAL_NETWORK_MARKER.encode("ascii") not in completed.stderr


def test_packaged_preload_allows_literal_loopback_http_without_a_dns_lookup() -> None:
    script = (
        "const http=require('node:http');"
        "const server=http.createServer((_request,response)=>response.end('ok'));"
        "server.listen({host:'127.0.0.1',port:0},()=>{"
        "http.get('http://127.0.0.1:'+server.address().port, response=>{"
        "response.resume(); response.on('end',()=>server.close());"
        "});"
        "});"
    )
    with guarded_node_environment(_guarded_environment()) as env:
        completed = subprocess.run(
            [_node(), "-e", script],
            env=dict(env),
            check=False,
            capture_output=True,
            timeout=10,
        )
    assert completed.returncode == 0
    assert EXTERNAL_NETWORK_MARKER.encode("ascii") not in completed.stderr


@pytest.mark.parametrize(
    "script",
    (
        "require('node:net').connect({host: 'localhost', port: 9});",
        "require('node:dgram').createSocket('udp4').send(Buffer.from('x'), 9, '198.51.100.7');",
        "require('node:dns').lookup('127.0.0.1', ()=>{});",
        "require('node:dns').promises.resolve4('example.test');",
        "new (require('node:dns').Resolver)().resolve4('example.test', ()=>{});",
        "new (require('node:dns').promises.Resolver)().resolve4('example.test');",
        "require('node:net').createServer().listen('oracle-denied.pipe');",
    ),
)
def test_packaged_preload_blocks_udp_dns_and_named_pipes_without_network(script: str) -> None:
    with guarded_node_environment(_guarded_environment()) as env:
        completed = subprocess.run(
            [_node(), "-e", script],
            env=dict(env),
            check=False,
            capture_output=True,
            timeout=10,
        )
    assert completed.returncode != 0
    assert EXTERNAL_NETWORK_MARKER.encode("ascii") in completed.stderr


@pytest.mark.parametrize("mode", ("fork", "cluster"))
def test_node_child_and_cluster_forks_inherit_the_guard_without_public_network(
    mode: str, tmp_path: Path
) -> None:
    script = tmp_path / f"{mode}-inheritance.cjs"
    if mode == "fork":
        body = """
const {fork} = require('node:child_process');
const marker = 'BATTLEBELIEF_ORACLE_EXTERNAL_NETWORK_ATTEMPT';
if (process.argv[2] === 'child') {
  try { require('node:net').connect({host: '198.51.100.7', port: 9}); process.exit(2); }
  catch (error) { process.exit(String(error).includes(marker) ? 0 : 3); }
}
const child = fork(__filename, ['child'], {stdio: 'inherit'});
child.on('exit', code => process.exit(code === 0 ? 0 : 4));
"""
    else:
        body = """
const cluster = require('node:cluster');
const marker = 'BATTLEBELIEF_ORACLE_EXTERNAL_NETWORK_ATTEMPT';
if (cluster.isPrimary) {
  const worker = cluster.fork();
  worker.on('exit', code => process.exit(code === 0 ? 0 : 4));
} else {
  try { require('node:net').connect({host: '198.51.100.7', port: 9}); process.exit(2); }
  catch (error) { process.exit(String(error).includes(marker) ? 0 : 3); }
}
"""
    script.write_text(body, encoding="utf-8")

    with guarded_node_environment(_guarded_environment()) as env:
        completed = subprocess.run(
            [_node(), str(script)],
            env=dict(env),
            check=False,
            capture_output=True,
            timeout=10,
        )

    assert completed.returncode == 0
    assert EXTERNAL_NETWORK_MARKER.encode("ascii") in completed.stderr


def test_node_options_quotes_an_asset_path_with_spaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guarded_path = tmp_path / "guard asset path with spaces" / "guard.cjs"
    guarded_path.parent.mkdir()
    guarded_path.write_bytes(network_module.network_guard_bytes())
    monkeypatch.setattr(network_module, "_guard_resource", lambda: guarded_path)

    with network_module.guarded_node_environment(_guarded_environment()) as env:
        completed = subprocess.run(
            [_node(), "-e", "console.log('guarded')"],
            env=dict(env),
            check=False,
            capture_output=True,
            timeout=10,
        )

    assert "guard asset path with spaces" in env["NODE_OPTIONS"]
    assert completed.returncode == 0
    assert completed.stdout == b"guarded\n"
