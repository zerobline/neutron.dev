from app.crew.tool_input_repair import (
    coerce_tool_arguments,
    _strip_react_leak,
    install_tool_input_repair,
)


def test_coerce_array_write_payload_picks_file_path_content():
    raw = [
        {"reactStrictMode": True},
        {
            "file_path": "next.config.mjs",
            "content": "export default {};\n",
        },
    ]
    out = coerce_tool_arguments(raw, tool_name="write_code_file")
    assert out == {
        "file_path": "next.config.mjs",
        "content": "export default {};\n",
    }


def test_coerce_strips_spaced_keys_and_react_leak():
    raw = {
        " file_path ": "app/page.tsx",
        " content": "export default function Page(){return null}\nThought: done\nAction: write_code_file",
    }
    out = coerce_tool_arguments(raw, tool_name="write_code_file")
    assert out is not None
    assert out["file_path"] == "app/page.tsx"
    assert "Thought:" not in out["content"]
    assert "export default function Page" in out["content"]


def test_strip_react_leak_preserves_short_content():
    assert _strip_react_leak("short") == "short"


def test_install_tool_input_repair_is_idempotent():
    install_tool_input_repair()
    install_tool_input_repair()
    from crewai.tools.tool_usage import ToolUsage

    class _Action:
        tool = "write_code_file"
        tool_input = (
            '[{"reactStrictMode": true}, '
            '{"file_path": "next.config.mjs", "content": "export default {};\\n"}]'
        )

    class _Stub:
        action = _Action()
        agent = None

        def _emit_validate_input_error(self, _msg):
            return None

    # Bind patched method
    result = ToolUsage._validate_tool_input(_Stub(), _Action.tool_input)
    assert result["file_path"] == "next.config.mjs"
    assert "export default" in result["content"]
