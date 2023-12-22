from typing import List


def assignment_to_text(assignment: dict) -> str:
    """Returns a string representatin of an assignment in the following text format

    Course Code: code
    Title: title
    Description: description
    Due Date: due date
    """

    assignment_format = (
        "*Course Code*: {course_code}\n"
        "*Title*: {title}\n"
        "*Description*: {description}\n"
        "*Due Date*: {due_date}"
    )

    format_args = {
        "course_code": assignment["course_code"],
        "title": assignment["title"],
        "description": assignment["description"],
        "due_date": assignment["deadline"]
    }

    return assignment_format.format(**format_args)


def generate_get_assignments_message(assignments: List[dict]) -> str:
    """Formats and returns the get assignments response message"""
    # format assignments as text
    message_format = ("Hey 👋, here's a quick rundown of your pending assignments: \n\n"
                      "{assignment_section}")

    assignments_as_text = [assignment_to_text(ass) for ass in assignments]
    assignment_section = "\n\n".join(assignments_as_text)

    return message_format.format(assignment_section=assignment_section)


def generate_assignment_reminder_message(assignments: List[dict]) -> str:
    """Formats and returns an assigment reminder message from a list of assignments

    Args:
        assignments (List[dict]): List of assignments

    Returns:
        str: Reminder message
    """
    message_format = ("Hi there,\nDon't forget to complete your pending assigments! Here's  a quick "
                      "rundown of what you have today:\n\n{assignment_section}\n\n"
                      "Happy studying!\nYour friendly Assignment Reminder Bot")

    assignments_as_text = [assignment_to_text(ass) for ass in assignments]
    assignment_section = "\n\n".join(assignments_as_text)
    return message_format.format(assignment_section=assignment_section)
