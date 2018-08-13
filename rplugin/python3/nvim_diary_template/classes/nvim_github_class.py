# pylint: disable=invalid-name
"""nvim_github_class

The Github class, with Neovim options to log information
back to the user.
"""

import json
from os import path
from typing import Any, Dict, List, Optional, Tuple, Union

from github import Github
from neovim import Nvim

from ..classes.github_issue_class import GitHubIssue, GitHubIssueComment
from ..classes.plugin_options import PluginOptions
from ..helpers.file_helpers import check_cache
from ..helpers.issue_helpers import (
    check_markdown_style,
    convert_utc_timezone,
    get_github_objects,
    split_comment,
)
from ..helpers.neovim_helpers import buffered_info_message
from ..utils.constants import CALENDAR_CACHE_DURATION, ISSUE_CACHE_DURATION

IntStrDict = Dict[str, Union[str, int]]
IntStrListDict = Dict[str, Union[str, int, List]]


class SimpleNvimGithub:
    """SimpleNvimGithub

    A class to deal with the simple interactions with the Github API.
    """

    def __init__(self, nvim: Nvim, options: PluginOptions) -> None:
        self.nvim: Nvim = nvim
        self.config_path: str = options.config_path
        self.repo_name: str = options.repo_name
        self.options: PluginOptions = options

        self.service: Any = self.setup_github_api()

        if self.service_not_valid():
            return

        loaded_issues: Union[List[Dict[str, Any]], List[GitHubIssue]] = check_cache(
            self.config_path,
            "open_issues",
            ISSUE_CACHE_DURATION,
            self.get_all_open_issues,
        )

        self.issues: List[GitHubIssue] = get_github_objects(loaded_issues)

        self.repo_labels: List[str] = check_cache(
            self.config_path,
            "repo_labels",
            CALENDAR_CACHE_DURATION,
            self.get_repo_issues,
        )

    @property
    def active(self) -> bool:
        """active

        Is the Github service active?
        """
        return not self.service_not_valid()

    def setup_github_api(self) -> Optional[Any]:
        """setup_github_api

            Sets up the initial Github service, which can then be used
            for future work.
        """

        try:
            with open(
                path.join(self.config_path, "github_credentials.json")
            ) as json_file:
                store: Dict[str, str] = json.load(json_file)

            access_token: str = store["access_token"]
        except (IOError, ValueError):
            self.nvim.err_write(
                "Credentials invalid, try re-generating or checking the path.\n"
            )
            return None

        service: Github = Github(access_token)

        return service

    def service_not_valid(self) -> bool:
        """service_not_valid

        Check if the Github API service is ready.
        """
        if self.service is None:
            return True

        if self.repo_name == "":
            return True

        return False

    def get_repo_issues(self) -> List[str]:
        """get_repo_issues

        Get the labels for the current repo.
        """

        if self.service_not_valid():
            self.nvim.err_write("Github service not currently running...\n")
            return []

        # TODO: Add a wrapper for all GitHub calls.
        repo_labels: Any = self.service.get_repo(self.repo_name).get_labels()

        return [label.name for label in repo_labels]

    def get_all_open_issues(self) -> List[GitHubIssue]:
        """get_all_open_issues

        Returns a list of all the open issues, including all comments.
        """

        if self.service_not_valid():
            self.nvim.err_write("Github service not currently running...\n")
            return []

        issues: Any = self.service.get_repo(self.repo_name).get_issues(state="open")

        issue_list: List[GitHubIssue] = []

        for issue in issues:

            initial_comment: GitHubIssueComment = GitHubIssueComment(
                number=0,
                body=split_comment(issue.body),
                tags=[],
                updated_at=convert_utc_timezone(
                    issue.updated_at, self.options.timezone
                ),
            )

            # Grab the comments for this issue too.
            all_comments: List[GitHubIssueComment] = self.format_comments(
                issue.get_comments()
            )

            issue_list.append(
                GitHubIssue(
                    number=issue.number,
                    complete=False,
                    title=issue.title,
                    all_comments=[initial_comment, *all_comments],
                    labels=[label.name for label in issue.labels],
                    metadata=[],
                )
            )

        return issue_list

    def format_comments(self, comments: List[Any]) -> List[GitHubIssueComment]:
        """format_comments

        Format all the comments that are passed into GitHubIssueComment
        objects.
        """

        comment_objs: List[GitHubIssueComment] = []

        current_comment: int = 1

        for comment in comments:
            comment_objs.append(
                GitHubIssueComment(
                    number=current_comment,
                    body=split_comment(comment.body),
                    tags=[],
                    updated_at=convert_utc_timezone(
                        comment.updated_at, self.options.timezone
                    ),
                )
            )

            current_comment += 1

        return comment_objs

    @staticmethod
    def filter_comments(
        issues: List[GitHubIssue], tag: str
    ) -> Tuple[List[Dict], List[Dict[str, int]]]:
        """filter_comments

        Filter comments for uploading, by a specific tag.
        """

        comments_to_upload: List[IntStrDict] = []
        change_indexes: List[Dict[str, int]] = []

        # For every issue, check the comments and check if the tags for that
        # comment contain the target tag. If it does, setup a dict with some
        # needed value as well as storing the index of the comment, so it can
        # be updated later.
        for issue_index, issue in enumerate(issues):
            for comment_index, comment in enumerate(issue.all_comments):
                if tag in comment.tags:
                    comment_lines: List[str] = comment.body
                    processed_comment_lines: List[str] = [
                        check_markdown_style(line, "github") for line in comment_lines
                    ]

                    comments_to_upload.append(
                        {
                            "issue_number": issue.number,
                            "comment_number": comment.number,
                            "comment": "\r\n".join(processed_comment_lines),
                        }
                    )

                    change_indexes.append(
                        {"issue": issue_index, "comment": comment_index}
                    )

        return comments_to_upload, change_indexes

    @staticmethod
    def filter_issues(
        issues: List[GitHubIssue], tag: str
    ) -> Tuple[List[Dict], List[int]]:
        """filter_issues

        Filter issues for uploading, by a specific tag.
        """

        issues_to_upload: List[IntStrListDict] = []
        change_indexes: List[int] = []

        # For every issue, check the metadata to see if it contains the target
        # tag. If it does, setup a dict with some needed value as well as
        # storing the index of the issue, so it can be updated later.
        for index, issue in enumerate(issues):
            if tag in issue.metadata:
                issue_body: List[str] = issue.all_comments[0].body
                processed_body: List[str] = [
                    check_markdown_style(line, "github") for line in issue_body
                ]

                issues_to_upload.append(
                    {
                        "number": issue.number,
                        "title": issue.title,
                        "labels": issue.labels,
                        "body": "\r\n".join(processed_body),
                    }
                )

                change_indexes.append(index)

        return issues_to_upload, change_indexes

    def upload_comments(
        self, issues: List[GitHubIssue], tag: str
    ) -> Tuple[List[GitHubIssue], List[Dict[str, int]]]:
        """upload_comments

        Upload comments with the specific tag to GitHub.
        """

        comments_to_upload, change_indexes = self.filter_comments(issues, tag)
        comments_to_ignore: List[Dict[str, int]] = []
        change_count: int = 0

        for comment, change_index in zip(comments_to_upload, change_indexes):
            issue_number: int = comment["issue_number"]
            comment_body: List[str] = comment["comment"]

            # We don't want to try and upload an empty comment.
            if comment_body == "":
                comments_to_ignore.append(change_index)
                continue

            new_comment: Any = (
                self.service.get_repo(self.repo_name)
                .get_issue(issue_number)
                .create_comment(comment_body)
            )

            current_issue: GitHubIssue = issues[change_index["issue"]]
            current_comment: GitHubIssueComment = current_issue.all_comments[
                change_index["comment"]
            ]
            current_comment.updated_at = convert_utc_timezone(
                new_comment.updated_at, self.options.timezone
            )

            change_count += 1

        buffered_info_message(
            self.nvim, f"Uploaded {change_count} comments to GitHub. "
        )

        return issues, comments_to_ignore

    def upload_issues(
        self, issues: List[GitHubIssue], tag: str
    ) -> Tuple[List[GitHubIssue], List[int]]:
        """upload_issues

        Upload issues with the specific tag to GitHub.
        """

        issues_to_upload, change_indexes = self.filter_issues(issues, tag)
        issues_to_ignore: List[int] = []
        change_count: int = 0

        for issue, index in zip(issues_to_upload, change_indexes):
            issue_title: str = issue["title"]
            issue_body: List[str] = issue["body"]
            issue_labels: List[str] = issue["labels"]

            # We don't want to try and upload an empty issue/title.
            if issue_title == "" or issue_body == "":
                issues_to_ignore.append(index)
                continue

            new_issue: Any = self.service.get_repo(self.repo_name).create_issue(
                title=issue_title, body=issue_body, labels=issue_labels
            )

            issues[index].number = new_issue.number
            issues[index].all_comments[0].updated_at = convert_utc_timezone(
                new_issue.updated_at, self.options.timezone
            )

            change_count += 1

        buffered_info_message(self.nvim, f"Uploaded {change_count} issues to GitHub. ")

        return issues, issues_to_ignore

    def update_comments(self, issues: List[GitHubIssue], tag: str) -> List[GitHubIssue]:
        """update_comments

        Update existing comments with the specific tag on GitHub.
        """

        comments_to_upload, change_indexes = self.filter_comments(issues, tag)

        for comment, change_index in zip(comments_to_upload, change_indexes):
            issue_number: int = comment["issue_number"]
            comment_number: int = comment["comment_number"]
            comment_body: List[str] = comment["comment"]

            # Comment 0 is actually the issue body, not a comment.
            if comment_number == 0:
                self.service.get_repo(self.repo_name).get_issue(issue_number).edit(
                    body=comment_body
                )

                # Grab the comment again, to sort the update time.
                github_comment: Any = self.service.get_repo(self.repo_name).get_issue(
                    issue_number
                )
            else:

                github_comment = (
                    self.service.get_repo(self.repo_name)
                    .get_issue(issue_number)
                    .get_comments()[comment_number - 1]
                )

                github_comment.edit(comment_body)

                # Grab the comment again, to sort the update time.
                github_comment = (
                    self.service.get_repo(self.repo_name)
                    .get_issue(issue_number)
                    .get_comments()[comment_number - 1]
                )

            current_issue: GitHubIssue = issues[change_index["issue"]]
            current_comment: GitHubIssueComment = current_issue.all_comments[
                change_index["comment"]
            ]
            current_comment.updated_at = convert_utc_timezone(
                github_comment.updated_at, self.options.timezone
            )

        buffered_info_message(
            self.nvim, f"Updated {len(comments_to_upload)} comments on GitHub. "
        )

        return issues

    def update_issues(self, issues: List[GitHubIssue], tag: str) -> List[GitHubIssue]:
        """update_issues

        Update existing issues with the specific tag on GitHub.
        """

        issues_to_upload, change_indexes = self.filter_issues(issues, tag)

        for issue, change_index in zip(issues_to_upload, change_indexes):
            issue_number: int = issue["number"]
            issue_title: str = issue["title"]
            issue_body: List[str] = issue["body"]
            issue_labels: List[str] = issue["labels"]

            github_issue: Any = self.service.get_repo(self.repo_name).get_issue(
                issue_number
            )

            github_issue.edit(title=issue_title, body=issue_body, labels=issue_labels)

            # Grab the issue again, to sort the update time.
            github_issue = self.service.get_repo(self.repo_name).get_issue(issue_number)
            current_issue: GitHubIssue = issues[change_index]
            issue_body_comment: GitHubIssueComment = current_issue.all_comments[0]
            issue_body_comment.updated_at = convert_utc_timezone(
                github_issue.updated_at, self.options.timezone
            )

        buffered_info_message(
            self.nvim, f"Updated {len(issues_to_upload)} issues on GitHub. "
        )

        return issues

    def complete_issues(self, issues: List[GitHubIssue]) -> None:
        """complete_issues

        Sort the complete status of the issues in the current buffer.
        We assume the buffer is always correct.
        """

        change_counter: int = 0

        for issue in issues:
            github_issue: Any = self.service.get_repo(self.repo_name).get_issue(
                issue.number
            )

            if issue.complete and github_issue.state == "open":
                github_issue.edit(state="closed")
                change_counter += 1
            elif not issue.complete and github_issue.state == "closed":
                github_issue.edit(state="open")
                change_counter += 1

        buffered_info_message(
            self.nvim,
            f"Changed the completion status of {change_counter} issues on GitHub. ",
        )
