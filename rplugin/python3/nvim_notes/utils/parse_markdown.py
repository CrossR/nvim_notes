import json
import re
from datetime import date
from os import makedirs, path

from dateutil import parser

from nvim_notes.helpers.event_helpers import format_event
from nvim_notes.helpers.google_calendar_helpers import convert_events
from nvim_notes.helpers.neovim_helpers import (get_buffer_contents,
                                               get_section_line, open_file,
                                               set_buffer_contents,
                                               set_line_content)
from nvim_notes.utils.constants import (DATETIME_REGEX, EVENT_REGEX, FILE_TYPE,
                                        ISO_FORMAT, SCHEDULE_HEADING,
                                        START_OF_LINE, TIME_FORMAT, TIME_REGEX)
from nvim_notes.utils.make_schedule import produce_schedule_markdown
from nvim_notes.utils.make_todos import get_past_todos


def open_markdown_file(nvim, options, gcal_service):
    """open_markdown_file

    Open the actual markdown file.
    This includes the following steps:
        * Open the file if it already exists.
        * If not, put the default template in and save.
    """
    todays_file = path.join(
        options.notes_path,
        date.today().strftime("%Y"),
        date.today().strftime("%B"),
        str(date.today()) + FILE_TYPE
    )

    if path.isfile(todays_file):
        open_file(nvim, todays_file, options.open_method)
        return

    full_markdown = []

    full_markdown.extend(generate_markdown_metadata())

    for heading in options.headings:
        full_markdown.append(f"# {heading}")
        full_markdown.append("")

    rolled_over_todos = get_past_todos(nvim, options)
    full_markdown.extend(rolled_over_todos)

    todays_events = gcal_service.todays_events
    schedule_markdown = produce_schedule_markdown(todays_events)
    full_markdown.extend(schedule_markdown)

    makedirs(path.dirname(todays_file), exist_ok=True)
    open_file(nvim, todays_file, options.open_method)

    set_buffer_contents(nvim, full_markdown)
    nvim.command(":w")


def generate_markdown_metadata():
    """generate_markdown_metadata

    Add some basic metadata to the stop of the file
    in HTML tags.
    """

    metadata = []

    metadata.append("<!---")
    metadata.append(f"    Date: {date.today()}")
    metadata.append(f"    Tags:")
    metadata.append("--->")
    metadata.append("")

    return metadata


def parse_buffer_events(events, format_string):
    """parse_buffer_events

    Given a list of events, parse the buffer lines and create event objects.
    """

    formatted_events = []

    for event in events:
        if event == '':
            continue

        # TODO: Regex is probably going to be a giant pain here,
        # and won't work if the string pattern changes.
        matches_date_time = re.findall(DATETIME_REGEX, event)

        if len(matches_date_time) == 0:
            matches_time = re.findall(TIME_REGEX, event)
            start_date = parser.parse(matches_time[0]) \
                               .strftime(format_string)
            end_date = parser.parse(matches_time[1]) \
                             .strftime(format_string)
        else:
            start_date = parser.parse(matches_date_time[0]) \
                               .strftime(format_string)
            end_date = parser.parse(matches_date_time[1]) \
                             .strftime(format_string)

        event_details = re.search(EVENT_REGEX, event)[0]

        event_dict = {
            'event_name': event_details,
            'start_time': start_date,
            'end_time': end_date
        }

        formatted_events.append(event_dict)

    return formatted_events


def remove_events_not_from_today(nvim):
    """remove_events_not_from_today

    Remove events from the file if they are not for the correct date.
    """

    current_events = parse_markdown_file_for_events(nvim, ISO_FORMAT)
    date_today = date.today()
    schedule_index = get_section_line(
        get_buffer_contents(nvim),
        SCHEDULE_HEADING
    ) + 1

    for index, event in enumerate(current_events):
        event_date = parser.parse(event['start_time']).date()

        if date_today == event_date:
            continue

        event_index = schedule_index + index + 1

        set_line_content(nvim, [""], event_index)


def parse_markdown_file_for_events(nvim, format_string):
    """parse_markdown_file_for_events

    Gets the contents of the current NeoVim buffer,
    and parses the schedule section into events.
    """

    current_buffer = get_buffer_contents(nvim)

    buffer_events_index = get_section_line(current_buffer, SCHEDULE_HEADING)
    events = current_buffer[buffer_events_index:]
    formatted_events = parse_buffer_events(events, format_string)

    return formatted_events


def combine_events(nvim,
                   markdown_events,
                   google_events):
    """combine_events

    Takes both markdown and google events and combines them into a single list,
    with no duplicates.

    The markdown is taken to be the ground truth, as there is no online copy.
    """

    buffer_events = [
        format_event(event, ISO_FORMAT) for event in markdown_events
    ]

    formatted_calendar = convert_events(google_events, ISO_FORMAT)
    calendar_events = [
        format_event(event, ISO_FORMAT) for event in formatted_calendar
    ]

    combined_events = buffer_events
    combined_events.extend(
        event for event in calendar_events if event not in buffer_events
    )

    return [
        format_event(event, TIME_FORMAT) for event in combined_events
    ]
