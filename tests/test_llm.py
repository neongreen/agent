from enum import Enum

from agent.llm import check_verdict


class SomeVerdict(Enum):
    CONT = "CONT"
    OK = "OK"
    FAIL = "FAIL"


def test_check_verdict_last_found():
    judgment = "CONT CONT CONT looks good looks fine OK OK OK"
    assert check_verdict(SomeVerdict, judgment) == SomeVerdict.OK


def test_check_verdict_single_verdict():
    judgment = "OK"
    assert check_verdict(SomeVerdict, judgment) == SomeVerdict.OK


def test_check_verdict_no_verdict():
    judgment = "This is some random text"
    assert check_verdict(SomeVerdict, judgment) is None


def test_check_verdict_case_insensitivity():
    judgment = "ok ok ok"
    assert check_verdict(SomeVerdict, judgment) == SomeVerdict.OK


def test_check_verdict_mixed_case():
    judgment = "cOnT OK fAiL"
    assert check_verdict(SomeVerdict, judgment) == SomeVerdict.FAIL


def test_check_verdict_partial_match():
    judgment = "CONTAINER"
    assert check_verdict(SomeVerdict, judgment) is None


def test_check_verdict_empty_judgment():
    judgment = ""
    assert check_verdict(SomeVerdict, judgment) is None


def test_check_verdict_multiple_verdicts_last_cont():
    judgment = "OK OK OK CONT CONT CONT"
    assert check_verdict(SomeVerdict, judgment) == SomeVerdict.CONT


def test_check_verdict_multiple_verdicts_last_fail():
    judgment = "CONT OK FAIL"
    assert check_verdict(SomeVerdict, judgment) == SomeVerdict.FAIL
