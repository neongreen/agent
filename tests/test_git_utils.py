from agent.git_utils import sanitize_branch_name


def test_sanitize_branch_name_invalid_chars():
    raw = "Feature/New Stuff!*?"
    cleaned = sanitize_branch_name(raw)
    assert cleaned == "feature/new-stuff"


def test_sanitize_branch_name_leading_trailing_hyphens():
    raw = "-Feature/New Stuff-"
    cleaned = sanitize_branch_name(raw)
    assert cleaned == "feature/new-stuff"


def test_sanitize_branch_name_empty_string():
    raw = ""
    cleaned = sanitize_branch_name(raw)
    assert cleaned == "no-name"
