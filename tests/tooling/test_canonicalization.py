from tools.canonicalize_manifest import canonicalize, manifest_digest


def test_object_key_order_is_canonical() -> None:
    value = {"b": 1, "a": 2}
    assert canonicalize(value) == b'{"a":2,"b":1}'
    assert manifest_digest(value) == (
        "sha256:d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772"
    )
