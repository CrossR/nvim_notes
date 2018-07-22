"""issue_helpers

Simple helpers to deal with Github issues.
"""
import re

from nvim_diary_template.helpers.neovim_helpers import (get_buffer_contents,
                                                        get_section_line,
                                                        set_line_content)
from nvim_diary_template.utils.constants import (BULLET_POINT, EMPTY_TODO,
                                                 ISSUE_COMMENT, ISSUE_HEADING,
                                                 ISSUE_START, PADDING,
                                                 SCHEDULE_HEADING)


def convert_issues(github_service, issue_list):
    """convert_issues

    Given a basic list of issues, grab the associated comments for printing.
    """

    formatted_issues = []

    # For every issue, grab the associated comments and combine. We treat the
    # issue body as the 0th comment, which is why it is added to the comments
    # item.
    for issue in issue_list:
        comments = github_service.get_comments_for_issue(issue['number'])
        formatted_issues.append({
            'number': issue['number'],
            'title': issue['title'],
            'all_comments': [issue['body']] + comments,
        })

    return formatted_issues


def insert_edit_tag(nvim):
    """insert_edit_tag

    Insert an edit tag for the current comment, so it can be uploaded.
    """

    # Grab the indexes needed to find the issue we are in.
    current_line = nvim.current.window.cursor[0]
    current_buffer = get_buffer_contents(nvim)
    issues_header_index = get_section_line(current_buffer, ISSUE_HEADING)
    schedule_header_index = get_section_line(
        current_buffer, SCHEDULE_HEADING) - 1

    inside_issues_section = (current_line >= issues_header_index and
                             current_line <= schedule_header_index)

    # If we are outside the issues section, return.
    if not inside_issues_section:
        return

    relevant_buffer = current_buffer[issues_header_index:current_line]
    line_index = -1

    # Search the buffer backwards and find the start of the current comment, to
    # get its line index.
    for index in range(len(relevant_buffer) - 1, 0, -1):
        line = relevant_buffer[index]
        if re.findall(ISSUE_COMMENT, line):
            line_index = index

            break

    # If we found no comment, return since we can't update it.
    if line_index == -1:
        return

    # If we did find a line, we want to append +edit to the end, and set it.
    # We need to update the line index to be relative to the full buffer.
    comment_line = relevant_buffer[line_index]
    comment_line += ' +edit'

    insert_index = issues_header_index + line_index + 1

    set_line_content(nvim,
                     [comment_line],
                     line_index=insert_index,
                     line_offset=1)


def insert_new_issue(nvim):
    """insert_new_issue

    Find the issue that the cursor is currently inside of, and get the next
    issue number. Then insert a new issue at the correct place with this
    number.
    """

    # Grab the indexes needed to find the issue we are in.
    current_buffer = get_buffer_contents(nvim)
    issues_header_index = get_section_line(current_buffer, ISSUE_HEADING)
    schedule_header_index = get_section_line(
        current_buffer, SCHEDULE_HEADING) - 1

    relevant_buffer = current_buffer[issues_header_index:schedule_header_index]

    # Search the buffer backwards and find the start of the last issue, to
    # get its number.
    for index in range(len(relevant_buffer) - 1, 0, -1):
        line = relevant_buffer[index]
        if re.findall(ISSUE_START, line):
            issue_number = int(re.findall(r"\d+", line)[0])

            break

    # Add new issue lines, and set them, and move the cursor to the end.
    new_line_number = schedule_header_index

    issue_start = f"{BULLET_POINT} {EMPTY_TODO} Issue {{{issue_number + 1}}}: +new"
    title_line = f"{PADDING}{BULLET_POINT} Title: "
    comment_line = f"{PADDING}{BULLET_POINT} Comment {{0}}:"
    new_comment = ['', issue_start, title_line, '', comment_line]

    set_line_content(nvim, new_comment, line_index=new_line_number)

    new_cursor_pos = (new_line_number + 3, len(title_line) - 1)
    nvim.current.window.cursor = new_cursor_pos


def insert_new_comment(nvim):
    """insert_new_comment

    Find the issue that the cursor is currently inside of, and get the next
    comment number. Then insert a new comment at the correct place with this
    number.
    """

    # Grab the indexes needed to find the issue we are in.
    current_line = nvim.current.window.cursor[0]
    current_buffer = get_buffer_contents(nvim)
    issues_header_index = get_section_line(current_buffer, ISSUE_HEADING)
    schedule_header_index = get_section_line(
        current_buffer, SCHEDULE_HEADING) - 1

    inside_issues_section = (current_line >= issues_header_index and
                             current_line <= schedule_header_index)

    # If we are outside the issues section, return.
    if not inside_issues_section:
        return

    relevant_buffer = current_buffer[current_line:schedule_header_index]
    new_line_number = 0

    # Search the buffer forwards and find the start of the next issue, to
    # insert before it. Then, find the last comment number and increment it.
    for index, line in enumerate(relevant_buffer):
        if re.findall(ISSUE_START, line):
            new_line_number = index - 1

            break

    # If we didn't change the new line number, we must be in the last comment.
    # Instead, just place above the next section heading.
    if new_line_number == 0:
        new_line_number = schedule_header_index

    relevant_buffer = current_buffer[issues_header_index:new_line_number]
    comment_number = 99

    # Search back to find the latest comment number, so we can increment it.
    for line in reversed(relevant_buffer):
        if re.findall(ISSUE_COMMENT, line):
            comment_number = int(re.findall(r"\d+", line)[0])

            break

    # Add a new issue comment line, and set the line, before moving the cursor
    # there.
    header_line = f"{PADDING}{BULLET_POINT} Comment {{{comment_number + 1}}}: +new"
    indent_line = f"{PADDING * 2}"
    new_comment = ['', header_line, indent_line]

    set_line_content(nvim, new_comment, line_index=new_line_number)

    new_cursor_pos = (new_line_number + 2, len(indent_line) - 1)
    nvim.current.window.cursor = new_cursor_pos