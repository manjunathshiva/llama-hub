"""
GitLab repository issues reader.

Retrieves the list of issues of a GitLab repository and converts them to documents.

Each issue is converted to a document by doing the following:

    - The text of the document is the concatenation of the title and the body of the issue.
    - The title of the document is the title of the issue.
    - The doc_id of the document is the issue number.
    - The extra_info of the document is a dictionary with the following keys:
        - state: State of the issue.
        - created_at: Date when the issue was created.
        - closed_at: Date when the issue was closed. Only present if the issue is closed.
        - url: URL of the issue.
        - assignee: Login of the user assigned to the issue. Only present if the issue is assigned.
    - The embedding of the document is not set.
    - The doc_hash of the document is not set.

"""
import asyncio
import enum
import logging
from typing import Dict, List, Optional, Tuple

from llama_index.readers.base import BaseReader
from llama_index.readers.schema.base import Document

from llama_hub.gitlab_repo_issues.gitlab_client import (
    BaseGitLabIssuesClient,
    GitLabIssuesClient,
)

logger = logging.getLogger(__name__)


def print_if_verbose(verbose: bool, message: str) -> None:
    """Log message if verbose is True."""
    if verbose:
        print(message)


class GitLabRepositoryIssuesReader(BaseReader):
    """
    GitLab repository issues reader.

    Retrieves the list of issues of a GitLab repository and returns a list of documents.

    Examples:
        >>> reader = GitLabRepositoryIssuesReader("owner", "repo")
        >>> issues = reader.load_data()
        >>> print(issues)

    """

    class IssueState(enum.Enum):
        """
        Issue type.

        Used to decide what issues to retrieve.

        Attributes:
            - OPEN: Just open issues. This is the default.
            - CLOSED: Just closed issues.
            - ALL: All issues, open and closed.
        """

        OPEN = "open"
        CLOSED = "closed"
        ALL = "all"

    class FilterType(enum.Enum):
        """
        Filter type.

        Used to determine whether the filter is inclusive or exclusive.
        """

        EXCLUDE = enum.auto()
        INCLUDE = enum.auto()

    def __init__(
        self,
        gitlab_client: BaseGitLabIssuesClient,
        owner: str,
        repo: str,
        verbose: bool = False,
    ):
        """
        Initialize params.

        Args:
            - gitlab_client (BaseGitLabIssuesClient): GitLab client.
            - owner (str): Owner of the repository.
            - repo (str): Name of the repository.
            - verbose (bool): Whether to print verbose messages.

        Raises:
            - `ValueError`: If the gitlab_token is not provided and
                the GITLAB_TOKEN environment variable is not set.
        """
        super().__init__()

        self._owner = owner
        self._repo = repo
        self._verbose = verbose

        # Set up the event loop
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            # If there is no running loop, create a new one
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        self._gitlab_client = gitlab_client

    def load_data(
        self,
        state: Optional[IssueState] = IssueState.OPEN,
        labelFilters: Optional[List[Tuple[str, FilterType]]] = None,
    ) -> List[Document]:
        """
        Load issues from a repository and converts them to documents.

        Each issue is converted to a document by doing the following:

        - The text of the document is the concatenation of the title and the body of the issue.
        - The title of the document is the title of the issue.
        - The doc_id of the document is the issue number.
        - The extra_info of the document is a dictionary with the following keys:
            - state: State of the issue.
            - created_at: Date when the issue was created.
            - closed_at: Date when the issue was closed. Only present if the issue is closed.
            - url: URL of the issue.
            - assignee: Login of the user assigned to the issue. Only present if the issue is assigned.
        - The embedding of the document is None.
        - The doc_hash of the document is None.

        Args:
            - state (IssueState): State of the issues to retrieve. Default is IssueState.OPEN.
            - labelFilters: an optional list of filters to apply to the issue list based on labels.

        :return: list of documents
        """
        documents = []
        page = 1
        # Loop until there are no more issues
        while True:
            issues: Dict = self._loop.run_until_complete(
                self._gitlab_client.get_issues(
                    self._owner, self._repo, state=state.value, page=page
                )
            )

            if len(issues) == 0:
                print_if_verbose(self._verbose, "No more issues found, stopping")

                break
            print_if_verbose(
                self._verbose, f"Found {len(issues)} issues in the repo page {page}"
            )
            page += 1
            filterCount = 0
            for issue in issues:
                if not self._must_include(labelFilters, issue):
                    filterCount += 1
                    continue
                title = issue["title"]
                body = issue["body"]
                document = Document(
                    doc_id=str(issue["number"]),
                    text=f"{title}\n{body}",
                )
                extra_info = {
                    "state": issue["state"],
                    "created_at": issue["created_at"],
                    # url is the API URL
                    "url": issue["url"],
                    # source is the HTML URL, more conveninent for humans
                    "source": issue["html_url"],
                }
                if issue["closed_at"] is not None:
                    extra_info["closed_at"] = issue["closed_at"]
                if issue["assignee"] is not None:
                    extra_info["assignee"] = issue["assignee"]["login"]
                if issue["labels"] is not None:
                    extra_info["labels"] = [label["name"] for label in issue["labels"]]
                document.extra_info = extra_info
                documents.append(document)

            print_if_verbose(self._verbose, f"Resulted in {len(documents)} documents")
            if labelFilters is not None:
                print_if_verbose(self._verbose, f"Filtered out {filterCount} issues")

        return documents

    def _must_include(self, labelFilters, issue):
        if labelFilters is None:
            return True
        labels = [label["name"] for label in issue["labels"]]
        for labelFilter in labelFilters:
            label = labelFilter[0]
            filterType = labelFilter[1]
            # Only include issues with the label and value
            if filterType == self.FilterType.INCLUDE:
                return label in labels
            elif filterType == self.FilterType.EXCLUDE:
                return label not in labels

        return True


if __name__ == "__main__":
    """Load all issues in the repo labeled as bug."""
    gitlab_client = GitLabIssuesClient(verbose=True)

    reader = GitLabRepositoryIssuesReader(
        gitlab_client=gitlab_client,
        owner="manjunathshiva",
        repo="dry",
        verbose=True,
    )

    documents = reader.load_data(
        state=GitLabRepositoryIssuesReader.IssueState.ALL,
        labelFilters=[("bug", GitLabRepositoryIssuesReader.FilterType.INCLUDE)],
    )
    print(f"Got {len(documents)} documents")
