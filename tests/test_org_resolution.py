"""Organization resolution must never silently pick a workspace.

Regression tests for the case where several Linear organizations are configured and
the caller does not name one. The old behaviour returned the first key in sorted
order, which meant a write intended for one tenant landed in another's workspace --
successfully, and with nothing in the response to show it.
"""
import pytest

from linear_mcp.server import KEY_PREFIX, get_api_key, resolve_organization


@pytest.fixture(autouse=True)
def _clear_linear_env(monkeypatch):
    """Start every test from a known-empty configuration."""
    import os

    for var in [k for k in os.environ if k.startswith(KEY_PREFIX)]:
        monkeypatch.delenv(var, raising=False)
    # keyring lookups must not leak a real credential into the tests
    monkeypatch.setattr("linear_mcp.server.resolve_secret",
                        lambda var: __import__("os").environ.get(var) or None)


def _configure(monkeypatch, **orgs):
    for name, key in orgs.items():
        var = KEY_PREFIX if name == "default" else f"{KEY_PREFIX}_{name.upper()}"
        monkeypatch.setenv(var, key)


# --- the regression -------------------------------------------------------------

def test_multiple_orgs_without_organization_raises(monkeypatch):
    _configure(monkeypatch, appsumo="k-appsumo", koard="k-koard", techno87="k-t87")
    with pytest.raises(ValueError) as exc:
        resolve_organization()
    msg = str(exc.value)
    assert "no `organization` was given" in msg
    # the error must name the choices so the caller can fix the call
    assert "appsumo" in msg and "koard" in msg and "techno87" in msg


def test_multiple_orgs_does_not_fall_back_to_first_alphabetically(monkeypatch):
    """`appsumo` sorts first -- the old code returned it for every unnamed call."""
    _configure(monkeypatch, appsumo="k-appsumo", koard="k-koard")
    with pytest.raises(ValueError):
        get_api_key()


def test_explicit_organization_wins(monkeypatch):
    _configure(monkeypatch, appsumo="k-appsumo", koard="k-koard", techno87="k-t87")
    assert resolve_organization("koard") == "koard"
    assert get_api_key("koard") == "k-koard"
    assert get_api_key("appsumo") == "k-appsumo"


def test_explicit_organization_is_case_and_dash_insensitive(monkeypatch):
    _configure(monkeypatch, koard="k-koard")
    assert get_api_key("KOARD") == "k-koard"
    assert get_api_key("Ko-ard") == "k-koard"


# --- backwards compatibility ----------------------------------------------------

def test_single_org_without_organization_still_works(monkeypatch):
    _configure(monkeypatch, koard="k-koard")
    assert resolve_organization() == "koard"
    assert get_api_key() == "k-koard"


def test_bare_default_key_still_wins(monkeypatch):
    _configure(monkeypatch, default="k-default", koard="k-koard")
    assert resolve_organization() == "default"
    assert get_api_key() == "k-default"


# --- ambiguity ------------------------------------------------------------------

def test_unique_partial_match_resolves(monkeypatch):
    _configure(monkeypatch, appsumo_production="k-prod")
    assert resolve_organization("appsumo") == "appsumo_production"


def test_ambiguous_partial_match_raises(monkeypatch):
    """Two orgs share a prefix -- picking one silently is how tenants get crossed."""
    _configure(monkeypatch, acme_prod="k-prod", acme_staging="k-staging")
    with pytest.raises(ValueError) as exc:
        resolve_organization("acme")
    assert "ambiguous" in str(exc.value)


# --- unresolvable ---------------------------------------------------------------

def test_unknown_organization_raises(monkeypatch):
    _configure(monkeypatch, koard="k-koard")
    with pytest.raises(ValueError) as exc:
        resolve_organization("nope")
    assert "not found" in str(exc.value)


def test_no_configuration_raises(monkeypatch):
    with pytest.raises(ValueError) as exc:
        resolve_organization()
    assert "No Linear API keys configured" in str(exc.value)
