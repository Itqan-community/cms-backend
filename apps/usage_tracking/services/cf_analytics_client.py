"""Shared Cloudflare GraphQL Analytics constants and error type."""

from __future__ import annotations

CF_GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"


class CloudflareGraphQLError(RuntimeError):
    """Raised when the Cloudflare GraphQL API returns an ``errors`` payload."""
