"""Reverse-proxy engine: forwards a verified request to the resolved upstream."""
from __future__ import annotations

import requests
from flask import Response, request

# Hop-by-hop headers must not be forwarded (RFC 7230).
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-length", "host",
}


def forward(upstream_base: str, path: str, *, injected: dict, timeout: int) -> Response:
    url = upstream_base.rstrip("/") + path

    # Build outbound headers: drop hop-by-hop + any client-sent trusted headers
    # (those are stripped in the gateway before_request), then add injected ones.
    out_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and not k.lower().startswith("x-user")
        and not k.lower().startswith("x-roles") and not k.lower().startswith("x-tenant")
        and not k.lower().startswith("x-college")
        # RBAC context — permissions & scope are derived from the verified token
        # by the gateway alone; a client must never be able to assert its own.
        and not k.lower().startswith("x-permissions")
        and not k.lower().startswith("x-scope-level")
        and not k.lower().startswith("x-branch")
        # Access-gate context is set ONLY by the gateway from a verified grant —
        # never trust a client-supplied value.
        and not k.lower().startswith("x-product")
        and not k.lower().startswith("x-cohort")
        and not k.lower().startswith("x-drive")
    }
    out_headers.update(injected)

    upstream = requests.request(
        method=request.method,
        url=url,
        params=request.args,
        data=request.get_data(),
        headers=out_headers,
        cookies=request.cookies,
        stream=True,          # stream to support SSE / large bodies
        timeout=timeout,
        allow_redirects=False,
    )

    resp_headers = [
        (k, v) for k, v in upstream.raw.headers.items()
        if k.lower() not in HOP_BY_HOP
    ]

    return Response(
        upstream.iter_content(chunk_size=8192),
        status=upstream.status_code,
        headers=resp_headers,
        content_type=upstream.headers.get("Content-Type"),
    )
