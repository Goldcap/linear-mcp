#!/usr/bin/env python3
"""Linear MCP Server - Simple Linear issue management via GraphQL API."""

import os
import json
from typing import Optional

import httpx
from fastmcp import FastMCP

LINEAR_API_URL = "https://api.linear.app/graphql"

mcp = FastMCP("linear-mcp")


def get_available_organizations() -> dict[str, str]:
    """
    Get all configured Linear organizations and their API keys.

    Supports two configuration formats:
    1. Single key: LINEAR_API_KEY (default organization)
    2. Multiple keys: LINEAR_API_KEY_ORGNAME (e.g., LINEAR_API_KEY_APPSUMO)

    Returns:
        Dictionary mapping organization names (lowercase) to API keys
    """
    orgs = {}

    # Check for default single API key
    default_key = os.environ.get("LINEAR_API_KEY")
    if default_key:
        orgs["default"] = default_key

    # Check for organization-specific keys
    for key, value in os.environ.items():
        if key.startswith("LINEAR_API_KEY_") and value:
            org_name = key.replace("LINEAR_API_KEY_", "").lower()
            orgs[org_name] = value

    return orgs


def get_api_key(organization: Optional[str] = None) -> str:
    """
    Get Linear API key for a specific organization.

    Args:
        organization: Organization name (case-insensitive). If None, uses default.

    Returns:
        API key for the specified organization

    Raises:
        ValueError: If no API keys configured or organization not found
    """
    orgs = get_available_organizations()

    if not orgs:
        raise ValueError(
            "No Linear API keys configured. Set LINEAR_API_KEY or LINEAR_API_KEY_ORGNAME environment variables"
        )

    # If no organization specified, use default or first available
    if not organization:
        if "default" in orgs:
            return orgs["default"]
        # Return first available organization
        return next(iter(orgs.values()))

    # Normalize organization name for matching
    org_normalized = organization.lower().replace(" ", "").replace("-", "")

    # Try exact match first
    if org_normalized in orgs:
        return orgs[org_normalized]

    # Try partial match (e.g., "appsumo" matches "appsumo-production")
    for org_key, api_key in orgs.items():
        org_key_normalized = org_key.replace(" ", "").replace("-", "")
        if org_normalized in org_key_normalized or org_key_normalized in org_normalized:
            return api_key

    # No match found
    available = [name for name in orgs.keys() if name != "default"]
    if available:
        raise ValueError(
            f"Organization '{organization}' not found. Available organizations: {', '.join(available)}"
        )
    else:
        raise ValueError(
            f"Organization '{organization}' not found. Only default organization is configured."
        )


def graphql_request(query: str, variables: Optional[dict] = None, organization: Optional[str] = None) -> dict:
    """
    Execute a GraphQL request against Linear API.

    Args:
        query: GraphQL query string
        variables: Optional query variables
        organization: Organization name to use (uses default if not specified)

    Returns:
        GraphQL response data
    """
    api_key = get_api_key(organization)
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = httpx.post(LINEAR_API_URL, headers=headers, json=payload, timeout=30.0)
    response.raise_for_status()
    result = response.json()

    if "errors" in result:
        raise Exception(f"GraphQL errors: {json.dumps(result['errors'], indent=2)}")

    return result.get("data", {})


def _get_issue_internal(identifier: str, organization: Optional[str] = None) -> dict:
    """
    Internal helper to get issue - can be called by other functions.

    Args:
        identifier: Issue identifier (e.g., 'SRE-152')
        organization: Organization name to use

    Returns:
        Issue details dictionary
    """
    query = """
    query GetIssue($term: String!) {
      searchIssues(term: $term, first: 1) {
        nodes {
          id
          identifier
          title
          description
          priority
          priorityLabel
          url
          createdAt
          updatedAt
          state {
            id
            name
            type
          }
          assignee {
            id
            name
            email
          }
          team {
            id
            name
            key
          }
          labels {
            nodes {
              id
              name
              color
            }
          }
          project {
            id
            name
          }
          comments {
            nodes {
              id
              body
              createdAt
              user {
                name
              }
            }
          }
        }
      }
    }
    """
    variables = {"term": identifier}
    data = graphql_request(query, variables, organization=organization)

    issues = data.get("searchIssues", {}).get("nodes", [])
    if not issues:
        return {"error": f"Issue {identifier} not found"}

    # Verify we got the exact identifier (search might return similar results)
    for issue in issues:
        if issue.get("identifier") == identifier:
            return issue

    # Return first result if no exact match
    return issues[0]


@mcp.tool()
def get_issue(identifier: str, organization: Optional[str] = None) -> dict:
    """
    Get a Linear issue by its identifier (e.g., 'SRE-152').

    Args:
        identifier: The issue identifier like 'SRE-152' or 'ENG-123'
        organization: Organization name (e.g., 'Appsumo', 'Techno87'). Optional if only one org configured.

    Returns:
        Issue details including title, description, status, assignee, labels, and comments
    """
    return _get_issue_internal(identifier, organization=organization)


@mcp.tool()
def search_issues(
    query: Optional[str] = None,
    team_key: Optional[str] = None,
    state_name: Optional[str] = None,
    assignee_email: Optional[str] = None,
    limit: int = 20,
    organization: Optional[str] = None,
) -> dict:
    """
    Search for Linear issues with optional filters.

    Args:
        query: Text search query (searches title and description)
        team_key: Filter by team key (e.g., 'SRE', 'ENG')
        state_name: Filter by state name (e.g., 'Todo', 'In Progress', 'Done')
        assignee_email: Filter by assignee email
        limit: Maximum number of results (default 20, max 50)
        organization: Organization name (e.g., 'Appsumo', 'Techno87'). Optional if only one org configured.

    Returns:
        List of matching issues with basic details
    """
    # Build filter
    filters = []
    if team_key:
        filters.append(f'team: {{ key: {{ eq: "{team_key}" }} }}')
    if state_name:
        filters.append(f'state: {{ name: {{ eqIgnoreCase: "{state_name}" }} }}')
    if assignee_email:
        filters.append(f'assignee: {{ email: {{ eq: "{assignee_email}" }} }}')

    filter_str = ", ".join(filters)
    filter_clause = f"filter: {{ {filter_str} }}" if filters else ""

    # Use search query if provided
    if query:
        gql_query = f"""
        query SearchIssues($term: String!, $limit: Int!) {{
          searchIssues(term: $term, first: $limit) {{
            nodes {{
              id
              identifier
              title
              priority
              priorityLabel
              url
              state {{
                name
                type
              }}
              assignee {{
                name
              }}
              team {{
                key
                name
              }}
            }}
          }}
        }}
        """
        variables = {"term": query, "limit": min(limit, 50)}
        data = graphql_request(gql_query, variables, organization=organization)
        return {"issues": data.get("searchIssues", {}).get("nodes", [])}
    else:
        # No search query, just filter
        gql_query = f"""
        query ListIssues($limit: Int!) {{
          issues(first: $limit, {filter_clause}) {{
            nodes {{
              id
              identifier
              title
              priority
              priorityLabel
              url
              state {{
                name
                type
              }}
              assignee {{
                name
              }}
              team {{
                key
                name
              }}
            }}
          }}
        }}
        """
        variables = {"limit": min(limit, 50)}
        data = graphql_request(gql_query, variables, organization=organization)
        return {"issues": data.get("issues", {}).get("nodes", [])}


@mcp.tool()
def list_teams(organization: Optional[str] = None) -> dict:
    """
    List all teams with their workflow states.

    Args:
        organization: Organization name (e.g., 'Appsumo', 'Techno87'). Optional if only one org configured.

    Returns:
        List of teams with their IDs, keys, names, and available workflow states
    """
    query = """
    query ListTeams {
      teams {
        nodes {
          id
          name
          key
          states {
            nodes {
              id
              name
              type
              position
            }
          }
        }
      }
    }
    """
    data = graphql_request(query, organization=organization)
    return {"teams": data.get("teams", {}).get("nodes", [])}


@mcp.tool()
def update_issue_status(identifier: str, state_name: str, organization: Optional[str] = None) -> dict:
    """
    Update an issue's workflow status.

    Args:
        identifier: The issue identifier (e.g., 'SRE-152')
        state_name: The target state name (e.g., 'In Progress', 'Done', 'Todo')
        organization: Organization name (e.g., 'Appsumo', 'Techno87'). Optional if only one org configured.

    Returns:
        Updated issue details
    """
    # First, get the issue to find its ID and team
    issue = _get_issue_internal(identifier, organization=organization)
    if "error" in issue:
        return issue

    issue_id = issue["id"]
    team_id = issue["team"]["id"]

    # Get the team's workflow states to find the target state ID
    states_query = """
    query GetTeamStates($teamId: String!) {
      team(id: $teamId) {
        states {
          nodes {
            id
            name
            type
          }
        }
      }
    }
    """
    states_data = graphql_request(states_query, {"teamId": team_id}, organization=organization)
    states = states_data.get("team", {}).get("states", {}).get("nodes", [])

    # Find matching state (case-insensitive)
    target_state = None
    for state in states:
        if state["name"].lower() == state_name.lower():
            target_state = state
            break

    if not target_state:
        available = [s["name"] for s in states]
        return {"error": f"State '{state_name}' not found. Available states: {available}"}

    # Update the issue
    mutation = """
    mutation UpdateIssue($issueId: String!, $stateId: String!) {
      issueUpdate(id: $issueId, input: { stateId: $stateId }) {
        success
        issue {
          id
          identifier
          title
          state {
            name
            type
          }
        }
      }
    }
    """
    result = graphql_request(mutation, {"issueId": issue_id, "stateId": target_state["id"]}, organization=organization)
    return result.get("issueUpdate", {})


@mcp.tool()
def add_comment(identifier: str, body: str, organization: Optional[str] = None) -> dict:
    """
    Add a comment to an issue.

    Args:
        identifier: The issue identifier (e.g., 'SRE-152')
        body: The comment text (supports markdown)
        organization: Organization name (e.g., 'Appsumo', 'Techno87'). Optional if only one org configured.

    Returns:
        Created comment details
    """
    # Get the issue ID
    issue = _get_issue_internal(identifier, organization=organization)
    if "error" in issue:
        return issue

    issue_id = issue["id"]

    mutation = """
    mutation CreateComment($issueId: String!, $body: String!) {
      commentCreate(input: { issueId: $issueId, body: $body }) {
        success
        comment {
          id
          body
          createdAt
          user {
            name
          }
        }
      }
    }
    """
    result = graphql_request(mutation, {"issueId": issue_id, "body": body}, organization=organization)
    return result.get("commentCreate", {})


@mcp.tool()
def update_issue(
    identifier: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[int] = None,
    assignee_email: Optional[str] = None,
    organization: Optional[str] = None,
) -> dict:
    """
    Update issue fields (title, description, priority, assignee).

    Args:
        identifier: The issue identifier (e.g., 'SRE-152')
        title: New title (optional)
        description: New description (optional, supports markdown)
        priority: New priority 0-4 where 0=none, 1=urgent, 2=high, 3=medium, 4=low (optional)
        assignee_email: Email of user to assign (optional)
        organization: Organization name (e.g., 'Appsumo', 'Techno87'). Optional if only one org configured.

    Returns:
        Updated issue details
    """
    # Get the issue ID
    issue = _get_issue_internal(identifier, organization=organization)
    if "error" in issue:
        return issue

    issue_id = issue["id"]

    # Build input object
    input_fields = []
    variables = {"issueId": issue_id}

    if title is not None:
        input_fields.append("title: $title")
        variables["title"] = title
    if description is not None:
        input_fields.append("description: $description")
        variables["description"] = description
    if priority is not None:
        input_fields.append("priority: $priority")
        variables["priority"] = priority

    # Handle assignee lookup
    if assignee_email is not None:
        # Look up user by email
        user_query = """
        query FindUser($email: String!) {
          users(filter: { email: { eq: $email } }) {
            nodes {
              id
              name
              email
            }
          }
        }
        """
        user_data = graphql_request(user_query, {"email": assignee_email}, organization=organization)
        users = user_data.get("users", {}).get("nodes", [])
        if not users:
            return {"error": f"User with email '{assignee_email}' not found"}
        input_fields.append("assigneeId: $assigneeId")
        variables["assigneeId"] = users[0]["id"]

    if not input_fields:
        return {"error": "No fields to update. Provide at least one of: title, description, priority, assignee_email"}

    # Build variable declarations
    var_decls = ["$issueId: String!"]
    if "title" in variables:
        var_decls.append("$title: String!")
    if "description" in variables:
        var_decls.append("$description: String!")
    if "priority" in variables:
        var_decls.append("$priority: Int!")
    if "assigneeId" in variables:
        var_decls.append("$assigneeId: String")

    mutation = f"""
    mutation UpdateIssue({", ".join(var_decls)}) {{
      issueUpdate(id: $issueId, input: {{ {", ".join(input_fields)} }}) {{
        success
        issue {{
          id
          identifier
          title
          description
          priority
          priorityLabel
          state {{
            name
          }}
          assignee {{
            name
            email
          }}
        }}
      }}
    }}
    """
    result = graphql_request(mutation, variables, organization=organization)
    return result.get("issueUpdate", {})


@mcp.tool()
def create_issue(
    title: str,
    team_key: str,
    description: Optional[str] = None,
    priority: Optional[int] = None,
    state_name: Optional[str] = None,
    assignee_email: Optional[str] = None,
    project_name: Optional[str] = None,
    organization: Optional[str] = None,
) -> dict:
    """
    Create a new Linear issue.

    Args:
        title: Issue title
        team_key: Team key (e.g., 'SRE', 'ENG')
        description: Issue description (optional, supports markdown)
        priority: Priority 0-4 where 0=none, 1=urgent, 2=high, 3=medium, 4=low (optional)
        state_name: Initial state name (e.g., 'Todo', 'Backlog'). Optional, uses team default if not specified.
        assignee_email: Email of user to assign (optional)
        project_name: Project name to add issue to (optional, case-insensitive match)
        organization: Organization name (e.g., 'Appsumo', 'Techno87'). Optional if only one org configured.

    Returns:
        Created issue details
    """
    # Get the team to find its ID
    teams_query = """
    query GetTeams {
      teams {
        nodes {
          id
          key
          states {
            nodes {
              id
              name
            }
          }
        }
      }
    }
    """
    teams_data = graphql_request(teams_query, organization=organization)
    teams = teams_data.get("teams", {}).get("nodes", [])

    # Find the team
    target_team = None
    for team in teams:
        if team["key"].lower() == team_key.lower():
            target_team = team
            break

    if not target_team:
        available = [t["key"] for t in teams]
        return {"error": f"Team '{team_key}' not found. Available teams: {available}"}

    team_id = target_team["id"]

    # Build input object
    input_fields = ["title: $title", "teamId: $teamId"]
    variables = {"title": title, "teamId": team_id}

    if description is not None:
        input_fields.append("description: $description")
        variables["description"] = description

    if priority is not None:
        input_fields.append("priority: $priority")
        variables["priority"] = priority

    # Handle state lookup
    if state_name is not None:
        states = target_team.get("states", {}).get("nodes", [])
        target_state = None
        for state in states:
            if state["name"].lower() == state_name.lower():
                target_state = state
                break

        if not target_state:
            available = [s["name"] for s in states]
            return {"error": f"State '{state_name}' not found. Available states: {available}"}

        input_fields.append("stateId: $stateId")
        variables["stateId"] = target_state["id"]

    # Handle assignee lookup
    if assignee_email is not None:
        user_query = """
        query FindUser($email: String!) {
          users(filter: { email: { eq: $email } }) {
            nodes {
              id
              name
              email
            }
          }
        }
        """
        user_data = graphql_request(user_query, {"email": assignee_email}, organization=organization)
        users = user_data.get("users", {}).get("nodes", [])
        if not users:
            return {"error": f"User with email '{assignee_email}' not found"}
        input_fields.append("assigneeId: $assigneeId")
        variables["assigneeId"] = users[0]["id"]

    # Handle project lookup
    if project_name is not None:
        projects_query = """
        query ListProjects {
          projects(first: 50) {
            nodes {
              id
              name
            }
          }
        }
        """
        projects_data = graphql_request(projects_query, organization=organization)
        projects = projects_data.get("projects", {}).get("nodes", [])
        target_project = None
        for project in projects:
            if project["name"].lower() == project_name.lower():
                target_project = project
                break
        if not target_project:
            available = [p["name"] for p in projects]
            return {"error": f"Project '{project_name}' not found. Available projects: {available}"}
        input_fields.append("projectId: $projectId")
        variables["projectId"] = target_project["id"]

    # Build variable declarations
    var_decls = ["$title: String!", "$teamId: String!"]
    if "description" in variables:
        var_decls.append("$description: String")
    if "priority" in variables:
        var_decls.append("$priority: Int")
    if "stateId" in variables:
        var_decls.append("$stateId: String")
    if "assigneeId" in variables:
        var_decls.append("$assigneeId: String")
    if "projectId" in variables:
        var_decls.append("$projectId: String")

    mutation = f"""
    mutation CreateIssue({", ".join(var_decls)}) {{
      issueCreate(input: {{ {", ".join(input_fields)} }}) {{
        success
        issue {{
          id
          identifier
          title
          description
          priority
          priorityLabel
          url
          state {{
            name
            type
          }}
          assignee {{
            name
            email
          }}
          team {{
            key
            name
          }}
        }}
      }}
    }}
    """
    result = graphql_request(mutation, variables, organization=organization)
    return result.get("issueCreate", {})


@mcp.tool()
def create_project(
    name: str,
    team_key: str,
    description: Optional[str] = None,
    organization: Optional[str] = None,
) -> dict:
    """
    Create a new Linear project.

    Args:
        name: Project name
        team_key: Team key (e.g., 'SRE', 'ENG') to associate the project with
        description: Project description (optional, supports markdown)
        organization: Organization name (e.g., 'Appsumo', 'Techno87'). Optional if only one org configured.

    Returns:
        Created project details
    """
    # Get team ID
    teams_query = """
    query GetTeams {
      teams {
        nodes {
          id
          key
          name
        }
      }
    }
    """
    teams_data = graphql_request(teams_query, organization=organization)
    teams = teams_data.get("teams", {}).get("nodes", [])

    target_team = None
    for team in teams:
        if team["key"].lower() == team_key.lower():
            target_team = team
            break

    if not target_team:
        available = [t["key"] for t in teams]
        return {"error": f"Team '{team_key}' not found. Available teams: {available}"}

    # Build mutation
    input_fields = ["name: $name", "teamIds: [$teamId]"]
    variables = {"name": name, "teamId": target_team["id"]}
    var_decls = ["$name: String!", "$teamId: String!"]

    if description is not None:
        input_fields.append("description: $description")
        variables["description"] = description
        var_decls.append("$description: String")

    mutation = f"""
    mutation CreateProject({", ".join(var_decls)}) {{
      projectCreate(input: {{ {", ".join(input_fields)} }}) {{
        success
        project {{
          id
          name
          description
          url
          state
          teams {{
            nodes {{
              key
              name
            }}
          }}
        }}
      }}
    }}
    """
    result = graphql_request(mutation, variables, organization=organization)
    return result.get("projectCreate", {})


@mcp.tool()
def list_projects(
    team_key: Optional[str] = None,
    organization: Optional[str] = None,
) -> dict:
    """
    List Linear projects, optionally filtered by team.

    Args:
        team_key: Filter by team key (e.g., 'SRE', 'ENG'). Optional.
        organization: Organization name (e.g., 'Appsumo', 'Techno87'). Optional if only one org configured.

    Returns:
        List of projects with details
    """
    query = """
    query ListProjects {
      projects(first: 50) {
        nodes {
          id
          name
          description
          url
          state
          teams {
            nodes {
              key
              name
            }
          }
        }
      }
    }
    """
    data = graphql_request(query, organization=organization)
    projects = data.get("projects", {}).get("nodes", [])

    # Filter by team if specified
    if team_key:
        projects = [
            p for p in projects
            if any(t["key"].lower() == team_key.lower() for t in p.get("teams", {}).get("nodes", []))
        ]

    return {"projects": projects}


@mcp.tool()
def list_organizations() -> dict:
    """
    List all configured Linear organizations.

    Returns:
        List of organization names that can be used in other tool calls
    """
    orgs = get_available_organizations()
    org_names = [name for name in orgs.keys() if name != "default"]

    return {
        "organizations": org_names,
        "has_default": "default" in orgs,
        "count": len(org_names),
    }


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
