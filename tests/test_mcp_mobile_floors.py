"""Tests for issue #522: ios and android_api in the MCP tools.

The command line takes --ios and --android-api, but the MCP server only
exposed glibc, musl and macos. An agent checking mobile targets could not ask
about the floor the app actually ships with, and diff_lockfiles took none of
the version floors at all.
"""

from test_mcp import call, init, run  # noqa: F401  (init/call/run are the harness)


def _tools() -> dict:
    replies = run(init(), {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    return {t["name"]: t for t in replies[-1]["result"]["tools"]}


def _call(tool: str, **arguments: object) -> dict:
    """Send one tool call and return its structured content."""
    replies = run(init(), call(tool, **arguments))
    return replies[-1]["result"]


def test_check_package_schema_lists_the_mobile_floors():
    schema = _tools()["check_package"]["inputSchema"]
    assert "ios" in schema["properties"]
    assert "android_api" in schema["properties"]


def test_diff_lockfiles_schema_lists_every_version_floor():
    schema = _tools()["diff_lockfiles"]["inputSchema"]
    for key in ("glibc", "musl", "macos", "ios", "android_api"):
        assert key in schema["properties"], key


def test_check_lockfile_and_check_dist_schema_list_the_mobile_floors():
    tools = _tools()
    for name in ("check_lockfile", "check_dist"):
        schema = tools[name]["inputSchema"]
        assert "ios" in schema["properties"], name
        assert "android_api" in schema["properties"], name


def test_list_targets_defaults_include_the_mobile_floors():
    from wheelgap import mcp

    result = mcp._list_targets({})
    assert result["defaults"]["ios"] == mcp.DEFAULT_IOS
    assert result["defaults"]["android_api"] == mcp.DEFAULT_ANDROID_API


def test_check_package_reports_the_assumed_mobile_floors(fake_pypi):
    result = _call(
        "check_package",
        name="fastlib",
        version="2.0.0",
        python="3.13",
        targets=["ios-arm64", "android-arm64-v8a"],
    )["structuredContent"]
    assumes = result["assumes"]
    assert assumes["ios"] == "13.0"
    assert assumes["android_api"] == "24"


def test_check_package_accepts_a_raised_ios_floor(fake_pypi):
    result = _call(
        "check_package",
        name="fastlib",
        version="2.0.0",
        python="3.13",
        targets=["ios-arm64"],
        ios="16.0",
    )["structuredContent"]
    assert result["assumes"]["ios"] == "16.0"


def test_check_package_rejects_a_non_numeric_ios_floor(fake_pypi):
    result = _call(
        "check_package",
        name="fastlib",
        version="2.0.0",
        python="3.13",
        targets=["ios-arm64"],
        ios="abc",
    )
    assert result.get("isError") is True


def test_android_api_maps_to_the_dashed_cli_flag():
    """The CLI flag is --android-api; the MCP key is android_api."""
    from wheelgap import mcp

    argv = [f"--{key}={value}" for key, value in mcp._versions({"android_api": "30"}).items()]
    assert argv == ["--android_api=30"]
