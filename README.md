# Linear MCP Server

A simple MCP (Model Context Protocol) server for Linear issue management.

## Features

- **list_organizations()** - List all configured Linear organizations
- **create_issue(title, team_key, description, priority, state_name, assignee_email, organization)** - Create a new issue
- **get_issue(identifier, organization)** - Get issue by identifier (e.g., "SRE-152")
- **search_issues(query, team_key, state_name, assignee_email, limit, organization)** - Search issues with filters
- **list_teams(organization)** - List all teams with their workflow states
- **update_issue_status(identifier, state_name, organization)** - Change issue status
- **update_issue(identifier, title, description, priority, assignee_email, organization)** - Update issue fields
- **add_comment(identifier, body, organization)** - Add a comment to an issue

All tools support an optional `organization` parameter. If you have only one organization configured or want to use the default, you can omit this parameter.

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

### Single Organization

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

### Multiple Organizations

To work with multiple Linear organizations, use organization-specific environment variables:

```json
{
  "mcpServers": {
    "linear": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Goldcap/linear-mcp.git", "linear-mcp"],
      "env": {
        "LINEAR_API_KEY_APPSUMO": "lin_api_appsumo_key_here",
        "LINEAR_API_KEY_TECHNO87": "lin_api_techno87_key_here"
      }
    }
  }
}
```

The organization name is extracted from the environment variable name (e.g., `LINEAR_API_KEY_APPSUMO` → organization name: "appsumo").

You can also mix both formats:

```json
{
  "mcpServers": {
    "linear": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Goldcap/linear-mcp.git", "linear-mcp"],
      "env": {
        "LINEAR_API_KEY": "lin_api_default_key_here",
        "LINEAR_API_KEY_COMPANY_A": "lin_api_company_a_key_here",
        "LINEAR_API_KEY_COMPANY_B": "lin_api_company_b_key_here"
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

### Single Organization

Once configured, Claude Code can:

```
# Create a new issue
create_issue(title="Fix DNS cleanup", team_key="SRE", description="Need to clean up old DNS records")

# Get an issue
get_issue("SRE-152")

# Search for issues
search_issues(query="DNS cleanup", team_key="SRE")

# Update issue status
update_issue_status("SRE-152", "Done")

# Add a comment
add_comment("SRE-152", "Completed the DNS cleanup!")
```

### Multiple Organizations

When you have multiple organizations configured, you can specify which one to use:

```
# List configured organizations
list_organizations()

# Create an issue in Appsumo organization
create_issue(title="Bug in checkout", team_key="ENG", organization="Appsumo")

# Get an issue from Appsumo organization
get_issue("PROD-123", organization="Appsumo")

# Search issues in Techno87 organization
search_issues(query="bug fix", organization="Techno87")

# Update issue in specific organization
update_issue_status("PROD-123", "Done", organization="Appsumo")

# Add comment to issue in specific organization
add_comment("PROD-123", "Fixed the issue!", organization="Techno87")
```

You can also use natural language to reference organizations:

```
"Add a Linear ticket to Appsumo"
"Read a Linear ticket from Techno87"
"Create an issue in Techno87 for the API bug"
"Update the status of SRE-152 in Appsumo to Done"
```

The organization name matching is case-insensitive and flexible:
- "Appsumo", "appsumo", "APPSUMO" all work
- Spaces and hyphens are ignored for matching

## Development

```bash
git clone https://github.com/Goldcap/linear-mcp.git
cd linear-mcp
pip install -e .
LINEAR_API_KEY=lin_api_xxx linear-mcp
```

## License

MIT
