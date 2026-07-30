from __future__ import annotations


class UnknownProtocolEvent(RuntimeError):
    code = "unknown_protocol_event"


class MalformedProtocolMessage(RuntimeError):
    code = "malformed_protocol_message"


class TransportTimeout(RuntimeError):
    code = "transport_timeout"


class Disconnect(RuntimeError):
    code = "disconnect"


class TimerOrForfeit(RuntimeError):
    code = "timer_or_forfeit"
