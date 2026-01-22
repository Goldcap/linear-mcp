#!/usr/bin/env python3
"""Linear MCP Server - Simple Linear issue management via GraphQL API."""

import os
import json
from typing import Optional

import httpx
from fastmcp import FastMCP

LINEAR_API_URL = "https://api.linear.app/graphql"

mcp = FastMCP("linear-mcp")


def get_api_key() -> str:
    """Get Linear API key from environment."""
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        raise ValueError("LINEAR_API_KEY environment variable not set")
    return key


def graphql_request(query: str, variables: Optional[dict] = None) -> dict:
    """Execute a GraphQL request against Linear API."""
    api_key = get_api_key()
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


@mcp.tool()
def get_issue(identifier: str) -> dict:
    """
    Get a Linear issue by its identifier (e.g., 'SRE-152').

    Args:
        identifier: The issue identifier like 'SRE-152' or 'ENG-123'

    Returns:
        Issue details including title, description, status, assignee, labels, and comments
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
    data = graphql_request(query, variables)

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
def search_issues(
    query: Optional[str] = None,
    team_key: Optional[str] = None,
    state_name: Optional[str] = None,
    assignee_email: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """
    Search for Linear issues with optional filters.

    Args:
        query: Text search query (searches title and description)
        team_key: Filter by team key (e.g., 'SRE', 'ENG')
        state_name: Filter by state name (e.g., 'Todo', 'In Progress', 'Done')
        assignee_email: Filter by assignee email
        limit: Maximum number of results (default 20, max 50)

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
        data = graphql_request(gql_query, variables)
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
        data = graphql_request(gql_query, variables)
        return {"issues": data.get("issues", {}).get("nodes", [])}


@mcp.tool()
def list_teams() -> dict:
    """
    List all teams with their workflow states.

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
    data = graphql_request(query)
    return {"teams": data.get("teams", {}).get("nodes", [])}


@mcp.tool()
def update_issue_status(identifier: str, state_name: str) -> dict:
    """
    Update an issue's workflow status.

    Args:
        identifier: The issue identifier (e.g., 'SRE-152')
        state_name: The target state name (e.g., 'In Progress', 'Done', 'Todo')

    Returns:
        Updated issue details
    """
    # First, get the issue to find its ID and team
    issue = get_issue(identifier)
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
    states_data = graphql_request(states_query, {"teamId": team_id})
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
    result = graphql_request(mutation, {"issueId": issue_id, "stateId": target_state["id"]})
    return result.get("issueUpdate", {})


@mcp.tool()
def add_comment(identifier: str, body: str) -> dict:
    """
    Add a comment to an issue.

    Args:
        identifier: The issue identifier (e.g., 'SRE-152')
        body: The comment text (supports markdown)

    Returns:
        Created comment details
    """
    # Get the issue ID
    issue = get_issue(identifier)
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
    result = graphql_request(mutation, {"issueId": issue_id, "body": body})
    return result.get("commentCreate", {})


@mcp.tool()
def update_issue(
    identifier: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[int] = None,
    assignee_email: Optional[str] = None,
) -> dict:
    """
    Update issue fields (title, description, priority, assignee).

    Args:
        identifier: The issue identifier (e.g., 'SRE-152')
        title: New title (optional)
        description: New description (optional, supports markdown)
        priority: New priority 0-4 where 0=none, 1=urgent, 2=high, 3=medium, 4=low (optional)
        assignee_email: Email of user to assign (optional)

    Returns:
        Updated issue details
    """
    # Get the issue ID
    issue = get_issue(identifier)
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
        user_data = graphql_request(user_query, {"email": assignee_email})
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
    result = graphql_request(mutation, variables)
    return result.get("issueUpdate", {})


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
