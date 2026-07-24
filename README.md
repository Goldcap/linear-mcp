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

### Keeping keys out of the config file

Every `LINEAR_API_KEY*` variable above can be supplied three ways. The first
one that yields a value wins:

| Order | Source | Config holds |
|---|---|---|
| 1 | The variable itself, e.g. `LINEAR_API_KEY_KOARD` | the key |
| 2 | A helper command, `LINEAR_API_KEY_KOARD_CMD` | a command |
| 3 | The OS keyring, service `linear-mcp`, username `LINEAR_API_KEY_KOARD` | nothing |

**Helper commands** are the recommended option. The command's stdout (stripped)
becomes the key, so the secret is never written to the config file *and* never
enters the process environment — it exists only in the server's memory. Only the
command shows up in `/proc/<pid>/environ`.

```json
{
  "mcpServers": {
    "linear": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Goldcap/linear-mcp.git", "linear-mcp"],
      "env": {
        "LINEAR_API_KEY_APPSUMO_CMD": "secret-tool lookup service linear-mcp account appsumo",
        "LINEAR_API_KEY_KOARD_CMD":   "secret-tool lookup service linear-mcp account koard"
      }
    }
  }
}
```

Store the keys once with libsecret (GNOME Keyring, KDE Wallet):

```bash
secret-tool store --label='Linear MCP (koard)' service linear-mcp account koard
```

Any command works — `pass show linear/koard`, `op read op://Private/Linear/credential`,
or, if you want an audit trail on every secret read:

```bash
aws ssm get-parameter --name /koard/linear/api-key --with-decryption \
  --query Parameter.Value --output text
```

**OS keyring** (option 3) needs the optional dependency:

```bash
uvx --from "git+https://github.com/Goldcap/linear-mcp.git[keyring]" linear-mcp
keyring set linear-mcp LINEAR_API_KEY_KOARD
```

Notes:

- Helper commands run through the shell, so pipes and redirection work. They are
  your own config, but treat the string as executed code.
- Resolution is cached per process — a rotated key needs a server restart.
- A helper that fails or prints nothing logs to stderr and that organization is
  skipped; other organizations still load.
- Plain environment variables keep working unchanged, which is usually what you
  want in CI.

## Getting a Linear API Key

1. Go to Linear Settings → API → Personal API keys
2. Create a new API key with appropriate scopes
3. Copy the key (starts with `lin_api_`)

Note that a personal API key is a long-lived shared credential however it is
stored. The options above reduce where it sits at rest; they do not make it
expire.

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
