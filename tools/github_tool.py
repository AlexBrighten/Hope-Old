"""
tools/github_tool.py — GitHub integration via PyGithub.

Provides repository management, file CRUD, issues, pull requests,
and code search for the Hope AI agent.
"""

import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from tools.approval import check_or_stage

HERE = Path(__file__).resolve().parent.parent
load_dotenv(HERE / ".env")

_SETUP_MSG = (
    "GitHub is not configured. To set up securely:\n"
    "1. Go to https://github.com/settings/tokens?type=beta (Fine-grained Personal Access Tokens).\n"
    "2. Select ONLY the specific repositories Hope should access (avoid 'All repositories').\n"
    "3. Set minimal permissions:\n"
    "   • Contents: Read and write\n"
    "   • Pull requests: Read and write\n"
    "   • Issues: Read and write\n"
    "4. Add  GITHUB_TOKEN=github_pat_your_token_here  to your .env file at:\n"
    f"   {HERE / '.env'}\n"
    "5. (Recommended) Set GITHUB_ALLOWED_REPOS=owner/repo in .env to enforce a repository allowlist."
)

ALLOWED_REPOS = [
    r.strip().lower()
    for r in os.environ.get("GITHUB_ALLOWED_REPOS", "").split(",")
    if r.strip()
]


def _check_repo_allowed(full_repo_name: str) -> tuple[bool, str]:
    """If GITHUB_ALLOWED_REPOS is set, ensure repo is in the whitelist."""
    if not ALLOWED_REPOS:
        return True, ""
    normalized = full_repo_name.lower().strip()
    for allowed in ALLOWED_REPOS:
        if normalized == allowed or normalized.endswith(f"/{allowed}"):
            return True, ""
    return False, (
        f"🛡️ Security Block: Repository '{full_repo_name}' is not in your GITHUB_ALLOWED_REPOS whitelist.\n"
        f"Allowed repositories: {', '.join(ALLOWED_REPOS)}\n"
        "To allow writes to this repository, update GITHUB_ALLOWED_REPOS in your .env file."
    )


def _get_github():
    """Return an authenticated Github client, or raise if unconfigured."""
    try:
        from github import Github
    except ImportError:
        raise RuntimeError(
            "PyGithub is not installed. Run:  pip install PyGithub"
        )
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError(_SETUP_MSG)
    return Github(token)


def _resolve_repo(g, repo_name: str):
    """Resolve 'repo' (auto-prepend user) or 'owner/repo' to a Repository."""
    if "/" not in repo_name:
        user = g.get_user().login
        repo_name = f"{user}/{repo_name}"
    return g.get_repo(repo_name)


# ── Repositories ────────────────────────────────────────────────────────


def github_list_repos(visibility: str = "all", limit: int = 10) -> str:
    """List the authenticated user's GitHub repositories.

    Args:
        visibility: Filter — 'all', 'public', or 'private'.
        limit: Max repos to return (default 10).

    Returns a formatted list with name, description, stars, and language.
    """
    try:
        g = _get_github()
        user = g.get_user()
        repos = user.get_repos(visibility=visibility, sort="updated")
        lines = []
        for i, r in enumerate(repos):
            if i >= limit:
                break
            desc = r.description or "(no description)"
            lines.append(
                f"• **{r.full_name}** — {desc}\n"
                f"  ⭐ {r.stargazers_count}  |  {r.language or 'N/A'}"
            )
        return "\n".join(lines) if lines else "No repositories found."
    except Exception as e:
        return f"Error listing repos: {e}"


def github_get_repo_info(repo_name: str) -> str:
    """Get detailed info about a GitHub repository.

    Args:
        repo_name: 'owner/repo' or just 'repo' (uses authenticated user).

    Returns default branch, open issues, stars, forks, description, last push.
    """
    try:
        g = _get_github()
        r = _resolve_repo(g, repo_name)
        return (
            f"**{r.full_name}**\n"
            f"Description: {r.description or '(none)'}\n"
            f"Default branch: {r.default_branch}\n"
            f"Stars: {r.stargazers_count}  |  Forks: {r.forks_count}\n"
            f"Open issues: {r.open_issues_count}\n"
            f"Language: {r.language or 'N/A'}\n"
            f"Last push: {r.pushed_at.isoformat() if r.pushed_at else 'N/A'}"
        )
    except Exception as e:
        return f"Error getting repo info: {e}"


# ── File Operations ────────────────────────────────────────────────────


def github_read_file(repo_name: str, file_path: str, branch: str = "") -> str:
    """Read a file from a GitHub repository.

    Args:
        repo_name: 'owner/repo' or just 'repo'.
        file_path: Path to the file inside the repo (e.g. 'src/main.py').
        branch: Branch/ref to read from. Defaults to the repo's default branch.

    Returns the decoded file contents.
    """
    try:
        g = _get_github()
        repo = _resolve_repo(g, repo_name)
        ref = branch or repo.default_branch
        contents = repo.get_contents(file_path, ref=ref)
        if isinstance(contents, list):
            return "Error: path is a directory, not a file."
        decoded = contents.decoded_content.decode("utf-8", errors="replace")
        return f"**{file_path}** (branch: {ref}, {contents.size} bytes):\n\n{decoded}"
    except Exception as e:
        return f"Error reading file: {e}"


def github_create_or_update_file(
    repo_name: str,
    file_path: str,
    content: str,
    commit_message: str,
    branch: str = "",
    approval_token: str = "",
) -> str:
    """Create or update a file in a GitHub repository. Requires human approval.

    Args:
        repo_name: 'owner/repo' or just 'repo'.
        file_path: Path inside the repo (e.g. 'docs/README.md').
        content: The full file content to write.
        commit_message: Commit message for the change.
        branch: Target branch. Defaults to the repo's default branch.
        approval_token: Confirmation token from owner approval.

    Returns confirmation with the commit SHA.
    """
    allowed, err = _check_repo_allowed(repo_name)
    if not allowed:
        return err

    approved, msg = check_or_stage(
        action_name="github_create_or_update_file",
        params={"repo": repo_name, "path": file_path, "commit_message": commit_message},
        summary=f"Commit file '{file_path}' to '{repo_name}' with message: '{commit_message}'",
        approval_token=approval_token,
    )
    if not approved:
        return msg

    try:
        g = _get_github()
        repo = _resolve_repo(g, repo_name)
        ref = branch or repo.default_branch

        # Check if file exists (to decide create vs update)
        try:
            existing = repo.get_contents(file_path, ref=ref)
            if isinstance(existing, list):
                return "Error: path is a directory."
            result = repo.update_file(
                file_path, commit_message, content, existing.sha, branch=ref
            )
            return (
                f"Updated **{file_path}** on branch `{ref}`.\n"
                f"Commit: {result['commit'].sha}"
            )
        except Exception:
            # File doesn't exist — create it
            result = repo.create_file(
                file_path, commit_message, content, branch=ref
            )
            return (
                f"Created **{file_path}** on branch `{ref}`.\n"
                f"Commit: {result['commit'].sha}"
            )
    except Exception as e:
        return f"Error creating/updating file: {e}"


# ── Issues ──────────────────────────────────────────────────────────────


def github_list_issues(
    repo_name: str, state: str = "open", limit: int = 10
) -> str:
    """List issues in a GitHub repository.

    Args:
        repo_name: 'owner/repo' or just 'repo'.
        state: 'open', 'closed', or 'all'.
        limit: Max issues to return (default 10).

    Returns issue number, title, labels, and assignee.
    """
    try:
        g = _get_github()
        repo = _resolve_repo(g, repo_name)
        issues = repo.get_issues(state=state)
        lines = []
        for i, issue in enumerate(issues):
            if i >= limit:
                break
            # Skip pull requests (GitHub API returns them as issues too)
            if issue.pull_request is not None:
                continue
            labels = ", ".join(l.name for l in issue.labels) or "none"
            assignee = issue.assignee.login if issue.assignee else "unassigned"
            lines.append(
                f"• #{issue.number} — **{issue.title}**\n"
                f"  Labels: {labels}  |  Assignee: {assignee}"
            )
        return "\n".join(lines) if lines else f"No {state} issues found."
    except Exception as e:
        return f"Error listing issues: {e}"


def github_create_issue(
    repo_name: str,
    title: str,
    body: str = "",
    labels: str = "",
    approval_token: str = "",
) -> str:
    """Create a new issue in a GitHub repository. Requires human approval.

    Args:
        repo_name: 'owner/repo' or just 'repo'.
        title: Issue title.
        body: Issue body/description (optional).
        labels: Comma-separated label names (optional, e.g. 'bug,urgent').
        approval_token: Confirmation token from owner approval.

    Returns confirmation with the issue number and URL.
    """
    allowed, err = _check_repo_allowed(repo_name)
    if not allowed:
        return err

    approved, msg = check_or_stage(
        action_name="github_create_issue",
        params={"repo": repo_name, "title": title},
        summary=f"Open issue in '{repo_name}': '{title}'",
        approval_token=approval_token,
    )
    if not approved:
        return msg

    try:
        g = _get_github()
        repo = _resolve_repo(g, repo_name)
        label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else []
        issue = repo.create_issue(title=title, body=body, labels=label_list)
        return (
            f"Created issue **#{issue.number}**: {issue.title}\n"
            f"URL: {issue.html_url}"
        )
    except Exception as e:
        return f"Error creating issue: {e}"


def github_comment_issue(
    repo_name: str,
    issue_number: int,
    comment: str,
    approval_token: str = "",
) -> str:
    """Add a comment to a GitHub issue or pull request. Requires human approval.

    Args:
        repo_name: 'owner/repo' or just 'repo'.
        issue_number: The issue or PR number.
        comment: Comment text.
        approval_token: Confirmation token from owner approval.

    Returns confirmation with the comment URL.
    """
    allowed, err = _check_repo_allowed(repo_name)
    if not allowed:
        return err

    approved, msg = check_or_stage(
        action_name="github_comment_issue",
        params={"repo": repo_name, "issue_number": issue_number},
        summary=f"Post comment on issue #{issue_number} in '{repo_name}'",
        approval_token=approval_token,
    )
    if not approved:
        return msg

    try:
        g = _get_github()
        repo = _resolve_repo(g, repo_name)
        issue = repo.get_issue(number=issue_number)
        c = issue.create_comment(body=comment)
        return f"Comment added to #{issue_number}.\nURL: {c.html_url}"
    except Exception as e:
        return f"Error commenting on issue: {e}"


# ── Pull Requests ───────────────────────────────────────────────────────


def github_list_prs(
    repo_name: str, state: str = "open", limit: int = 10
) -> str:
    """List pull requests in a GitHub repository.

    Args:
        repo_name: 'owner/repo' or just 'repo'.
        state: 'open', 'closed', or 'all'.
        limit: Max PRs to return (default 10).

    Returns PR number, title, and head → base branches.
    """
    try:
        g = _get_github()
        repo = _resolve_repo(g, repo_name)
        prs = repo.get_pulls(state=state, sort="updated", direction="desc")
        lines = []
        for i, pr in enumerate(prs):
            if i >= limit:
                break
            lines.append(
                f"• #{pr.number} — **{pr.title}**\n"
                f"  {pr.head.ref} → {pr.base.ref}"
            )
        return "\n".join(lines) if lines else f"No {state} pull requests found."
    except Exception as e:
        return f"Error listing PRs: {e}"


def github_create_pr(
    repo_name: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
    approval_token: str = "",
) -> str:
    """Create a new pull request in a GitHub repository. Requires human approval.

    Args:
        repo_name: 'owner/repo' or just 'repo'.
        title: PR title.
        head: Source branch name.
        base: Target branch name (default 'main').
        body: PR description (optional).
        approval_token: Confirmation token from owner approval.

    Returns confirmation with the PR number and URL.
    """
    allowed, err = _check_repo_allowed(repo_name)
    if not allowed:
        return err

    approved, msg = check_or_stage(
        action_name="github_create_pr",
        params={"repo": repo_name, "title": title, "head": head, "base": base},
        summary=f"Create PR in '{repo_name}': '{title}' ({head} -> {base})",
        approval_token=approval_token,
    )
    if not approved:
        return msg

    try:
        g = _get_github()
        repo = _resolve_repo(g, repo_name)
        pr = repo.create_pull(title=title, body=body, head=head, base=base)
        return (
            f"Created PR **#{pr.number}**: {pr.title}\n"
            f"{pr.head.ref} → {pr.base.ref}\n"
            f"URL: {pr.html_url}"
        )
    except Exception as e:
        return f"Error creating PR: {e}"


# ── Code Search ─────────────────────────────────────────────────────────


def github_search_code(query: str, repo: str = "") -> str:
    """Search code on GitHub.

    Args:
        query: Search query string.
        repo: Optional 'owner/repo' to scope the search. If empty, searches all of GitHub.

    Returns matching file paths and text snippets (up to 10 results).
    """
    try:
        g = _get_github()
        q = f"{query} repo:{repo}" if repo else query
        results = g.search_code(query=q)
        lines = []
        for i, item in enumerate(results):
            if i >= 10:
                break
            lines.append(
                f"• **{item.repository.full_name}** / `{item.path}`\n"
                f"  {item.html_url}"
            )
        return "\n".join(lines) if lines else "No code results found."
    except Exception as e:
        return f"Error searching code: {e}"


# ── Export ──────────────────────────────────────────────────────────────

ALL = [
    github_list_repos,
    github_get_repo_info,
    github_read_file,
    github_create_or_update_file,
    github_list_issues,
    github_create_issue,
    github_comment_issue,
    github_list_prs,
    github_create_pr,
    github_search_code,
]
