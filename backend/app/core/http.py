from pydantic import SecretStr


def optional_bearer_auth_headers(api_key: SecretStr | None) -> dict[str, str] | None:
    """Return an Authorization header only when a non-blank API key is configured."""
    if api_key is None:
        return None
    value = api_key.get_secret_value().strip()
    return {"Authorization": f"Bearer {value}"} if value else None
