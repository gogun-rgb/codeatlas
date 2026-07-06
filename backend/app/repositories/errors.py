from __future__ import annotations


class RepositoryError(Exception):
    user_message = "Repository analysis failed."

    def __init__(self, user_message: str | None = None) -> None:
        super().__init__(user_message or self.user_message)
        self.user_message = user_message or self.user_message


class InvalidRepositoryUrlError(RepositoryError):
    user_message = "Enter a GitHub URL like https://github.com/owner/repo or owner/repo."


class RepositoryNotFoundError(RepositoryError):
    user_message = "Repository was not found. Check that it exists and is public."


class PrivateRepositoryError(RepositoryError):
    user_message = "CodeAtlas can analyze public GitHub repositories only."


class GitHubRateLimitError(RepositoryError):
    user_message = "GitHub API rate limit reached. Try again later."


class GitHubNetworkError(RepositoryError):
    user_message = "Could not reach GitHub. Check the network connection and try again."


class UnsupportedRepositoryError(RepositoryError):
    user_message = "No supported source files were found in this repository."


class SourceLimitExceededError(RepositoryError):
    user_message = "Repository source size exceeded the MVP safety limit."
