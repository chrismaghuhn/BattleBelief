"""Stable, sanitized failure labels for the local Showdown oracle."""

from __future__ import annotations

from enum import StrEnum


class OracleFailureClass(StrEnum):
    """Closed failure taxonomy suitable for retained oracle evidence."""

    NODE_NOT_FOUND = "node_not_found"
    NODE_VERSION_NOT_APPROVED = "node_version_not_approved"
    SOURCE_MISSING = "source_missing"
    SOURCE_COMMIT_MISMATCH = "source_commit_mismatch"
    SOURCE_DIRTY = "source_dirty"
    LICENSE_MISMATCH = "license_mismatch"
    LOCKFILE_MISMATCH = "lockfile_mismatch"
    NPM_VERSION_MISMATCH = "npm_version_mismatch"
    BUILD_FAILED = "build_failed"
    BUILD_OUTPUT_MISSING = "build_output_missing"
    START_TIMEOUT = "start_timeout"
    WRITE_TIMEOUT = "write_timeout"
    RESPONSE_TIMEOUT = "response_timeout"
    FIXTURE_TIMEOUT = "fixture_timeout"
    MALFORMED_OUTPUT = "malformed_output"
    PROTOCOL_DESYNCHRONIZATION = "protocol_desynchronization"
    RULESET_REJECTED = "ruleset_rejected"
    PROCESS_CRASH = "process_crash"
    UNEXPECTED_EXIT_CODE = "unexpected_exit_code"
    SHUTDOWN_FAILED = "shutdown_failed"
    ORPHANED_CHILD_PROCESS = "orphaned_child_process"
    EXTERNAL_NETWORK_ATTEMPT = "external_network_attempt"
    INPUT_TOO_LARGE = "input_too_large"
    OUTPUT_TOO_LARGE = "output_too_large"


__all__ = ["OracleFailureClass"]
