# Linear MCP Server

A simple MCP (Model Context Protocol) server for Linear issue management.

## Features

- **get_issue(identifier)** - Get issue by identifier (e.g., "SRE-152")
- **search_issues(query, team_key, state_name, assignee_email)** - Search issues with filters
- **list_teams()** - List all teams with their workflow states
- **update_issue_status(identifier, state_name)** - Change issue status
- **update_issue(identifier, title, description, priority, assignee_email)** - Update issue fields
- **add_comment(identifier, body)** - Add a comment to an issue

## Installation

### Using uvx (recommended)

```bash
uvx --from git+https://github.com/Goldcap/linear-mcp.git linear-mcp
```

### Using pip

```bash
pip install git+https://github.com/Goldcap/linear-mcp.git
```

## Configuration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "linear": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Goldcap/linear-mcp.git", "linear-mcp"],
      "env": {
        "LINEAR_API_KEY": "lin_api_your_key_here"
      }
    }
  }
}
```

Or if installed locally:

```json
{
  "mcpServers": {
    "linear": {
      "command": "linear-mcp",
      "env": {
        "LINEAR_API_KEY": "lin_api_your_key_here"
      }
    }
  }
}
```

## Getting a Linear API Key

1. Go to Linear Settings → API → Personal API keys
2. Create a new API key with appropriate scopes
3. Copy the key (starts with `lin_api_`)

## Usage Examples

Once configured, Claude Code can:

```
# Get an issue
get_issue("SRE-152")

# Search for issues
search_issues(query="DNS cleanup", team_key="SRE")

# Update issue status
update_issue_status("SRE-152", "Done")

# Add a comment
add_comment("SRE-152", "Completed the DNS cleanup!")
```

## Development

```bash
git clone https://github.com/Goldcap/linear-mcp.git
cd linear-mcp
pip install -e .
LINEAR_API_KEY=lin_api_xxx linear-mcp
```

## License

MIT
