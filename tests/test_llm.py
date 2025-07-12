from enum import StrEnum, auto

from ok.llm import check_verdict


class SomeVerdict(StrEnum):
    CONT = auto()
    OK = auto()
    FAIL = auto()


class ApprovedOrRejected(StrEnum):
    APPROVED = auto()
    REJECTED = auto()


def test_check_verdict_last_found():
    judgment = "CONT CONT CONT looks good looks fine OK OK OK"
    assert check_verdict(SomeVerdict, judgment) == SomeVerdict.OK

    judgment = "OK OK OK looks fine CONT CONT CONT actually not"
    assert check_verdict(SomeVerdict, judgment) == SomeVerdict.CONT


def test_check_verdict_single_verdict():
    judgment = "OK"
    assert check_verdict(SomeVerdict, judgment) == SomeVerdict.OK


def test_check_verdict_no_verdict():
    judgment = "This is some random text"
    assert check_verdict(SomeVerdict, judgment) is None


def test_check_verdict_partial_match():
    judgment = "CONTAINER"
    assert check_verdict(SomeVerdict, judgment) is None


def test_check_verdict_empty_judgment():
    judgment = ""
    assert check_verdict(SomeVerdict, judgment) is None


def test_check_verdict_last_line_only():
    judgment = "This is a test.\nAPPROVED APPROVED APPROVED"
    assert check_verdict(ApprovedOrRejected, judgment) == ApprovedOrRejected.APPROVED

    judgment = "This is a test.\nREJECTED REJECTED REJECTED"
    assert check_verdict(ApprovedOrRejected, judgment) == ApprovedOrRejected.REJECTED

    judgment = "This is a test.\nREJECTED REJECTED REJECTED\n\n"
    assert check_verdict(ApprovedOrRejected, judgment) == ApprovedOrRejected.REJECTED

    judgment = "This is a test.\nSomething else"
    assert check_verdict(ApprovedOrRejected, judgment) is None
