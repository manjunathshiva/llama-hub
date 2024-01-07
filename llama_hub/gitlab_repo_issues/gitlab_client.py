"""
GitLab API client for issues
"""

import os
from typing import Any, Dict, Optional, Protocol


class BaseGitLabIssuesClient(Protocol):
    def get_all_endpoints(self) -> Dict[str, str]:
        ...

    async def request(
        self,
        endpoint: str,
        method: str,
        headers: Dict[str, Any] = {},
        params: Dict[str, Any] = {},
        **kwargs: Any,
    ) -> Any:
        ...

    async def get_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        page: int = 1,
    ) -> Dict:
        ...


class GitLabIssuesClient:
    """
    An asynchronous client for interacting with the GitLab API for issues.

    The client requires a GitLab token for authentication, which can be passed as an argument
    or set as an environment variable.
    If no GitLab token is provided, the client will raise a ValueError.

    Examples:
        >>> client = GitLabIssuesClient("my_gitlab_token")
        >>> issues = client.get_issues("owner", "repo")
    """

    DEFAULT_BASE_URL = "https://gitlab.com/api/"
    DEFAULT_API_VERSION = "V4"

    def __init__(
        self,
        gitlab_token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        api_version: str = DEFAULT_API_VERSION,
        verbose: bool = False,
    ) -> None:
        """
        Initialize the GitLabIssuesClient.

        Args:
            - gitlab_token (str): GitLab token for authentication.
                If not provided, the client will try to get it from
                the GITLAB_TOKEN environment variable.
            - base_url (str): Base URL for the GitLab API
                (defaults to "https://gitlab.com/api/").
            - api_version (str): GitLab API version (defaults to "V4").

        Raises:
            ValueError: If no GitLab token is provided.
        """
        if gitlab_token is None:
            gitlab_token = os.getenv("GITLAB_TOKEN")
            if gitlab_token is None:
                raise ValueError(
                    "Please provide a GitLab token. "
                    + "You can do so by passing it as an argument to the GitLabReader,"
                    + "or by setting the GITLAB_TOKEN environment variable."
                )

        self._base_url = base_url
        self._api_version = api_version
        self._verbose = verbose

        self._endpoints = {
            "getIssues": "/repos/{owner}/{repo}/issues",
        }

        self._headers = {
            "Accept": "application/vnd.gitlab+json",
            "Authorization": f"Bearer {gitlab_token}",
            "X-GitLab-Api-Version": f"{self._api_version}",
        }

    def get_all_endpoints(self) -> Dict[str, str]:
        """Get all available endpoints."""
        return {**self._endpoints}

    async def request(
        self,
        endpoint: str,
        method: str,
        headers: Dict[str, Any] = {},
        params: Dict[str, Any] = {},
        **kwargs: Any,
    ) -> Any:
        """
        Makes an API request to the GitLab API.

        Args:
            - `endpoint (str)`: Name of the endpoint to make the request to.
            - `method (str)`: HTTP method to use for the request.
            - `headers (dict)`: HTTP headers to include in the request.
            - `**kwargs`: Keyword arguments to pass to the endpoint URL.

        Returns:
            - `response (httpx.Response)`: Response from the API request.

        Raises:
            - ImportError: If the `httpx` library is not installed.
            - httpx.HTTPError: If the API request fails.

        Examples:
            >>> response = client.request("getIssues", "GET",
                                owner="owner", repo="repo", state="all")
        """
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "`https` package not found, please run `pip install httpx`"
            )

        _headers = {**self._headers, **headers}

        _client: httpx.AsyncClient
        async with httpx.AsyncClient(
            headers=_headers, base_url=self._base_url, params=params
        ) as _client:
            try:
                response = await _client.request(
                    method, url=self._endpoints[endpoint].format(**kwargs)
                )
                response.raise_for_status()
            except httpx.HTTPError as excp:
                print(f"HTTP Exception for {excp.request.url} - {excp}")
                raise excp
            return response

    async def get_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        page: int = 1,
    ) -> Dict:
        """
        List issues in a repository.

        Note: GitLab's REST API considers every pull request an issue, but not every issue is a pull request.
        For this reason, "Issues" endpoints may return both issues and pull requests in the response.
        You can identify pull requests by the pull_request key.
        Be aware that the id of a pull request returned from "Issues" endpoints will be an issue id.
        To find out the pull request id, use the "List pull requests" endpoint.

        Args:
            - `owner (str)`: Owner of the repository.
            - `repo (str)`: Name of the repository.
            - `state (str)`: Indicates the state of the issues to return.
                Default: open
                Can be one of: open, closed, all.

        Returns:
            - See https://docs.gitlab.com/en/rest/issues/issues?apiVersion=2022-11-28#list-repository-issues

        Examples:
            >>> repo_issues = client.get_issues("owner", "repo")
        """
        return (
            await self.request(
                endpoint="getIssues",
                method="GET",
                params={
                    "state": state,
                    "per_page": 100,
                    "sort": "updated",
                    "direction": "desc",
                    "page": page,
                },
                owner=owner,
                repo=repo,
            )
        ).json()


if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        """Test the GitLabIssuesClient."""
        client = GitLabIssuesClient()
        issues = await client.get_issues(owner="moncho", repo="dry", state="all")

        for issue in issues:
            print(issue["title"])
            print(issue["body"])

    asyncio.run(main())