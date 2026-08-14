# MCP servers

The kit registers **blueprint** by default. The rest are optional and listed here so a new
machine can be brought to parity in one place.

## blueprint — browser automation

Drives a real browser (Chrome / Firefox / Safari) with your real profile: navigate, snapshot the
accessibility tree, click, fill forms, read console + network, screenshot, save PDF. In this kit it
covers the "the recording is behind a login, grab its URL / open the player page" step of
`recording-brief`, and general visual verification.

```bash
claude mcp add blueprint -s user -- npx -y @railsblueprint/blueprint-mcp@latest
```

Windows PowerShell:

```powershell
claude mcp add blueprint -s user -- npx -y '@railsblueprint/blueprint-mcp@latest'
```

Verify: `claude mcp list` → `blueprint` should report **connected**. First run downloads the
package via npx (Node ≥ 18). If it stays disconnected, run
`npx -y @railsblueprint/blueprint-mcp@latest` once by hand and read the error.

### Claude Desktop (instead of Claude Code)

Add to `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "blueprint": {
      "command": "npx",
      "args": ["-y", "@railsblueprint/blueprint-mcp@latest"]
    }
  }
}
```

On Windows, if `npx` is not resolved from the desktop app, use
`"command": "cmd", "args": ["/c", "npx", "-y", "@railsblueprint/blueprint-mcp@latest"]`.

## Optional servers this kit's skills can use

| Server | Why | Command |
|---|---|---|
| `playwright` | scripted browser sessions / capturing your own screen recordings | `claude mcp add playwright -s user -- npx -y @playwright/mcp@latest` |
| `browsermcp` | alternative browser bridge (Chrome extension) | see browsermcp.io |

`servers.json` in this folder holds the same definitions in Claude-Desktop format, for copy-paste.
