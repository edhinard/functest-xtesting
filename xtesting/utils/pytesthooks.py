import pytest

details = None
passed = None
failed = None
result = None
ok = None


def pytest_sessionstart(session):
    global details, passed, failed, result, ok
    details = dict(tests=[])
    passed = 0
    failed = 0
    result = 0
    ok = True


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    global details, passed, failed, result, ok
    outcome = yield
    outcome = outcome.get_result()
    if call.when == 'call':
        if outcome == 'passed':
            passed += 1
            test = dict(status='PASSED', result=call.result)
        elif outcome == 'failed':
            failed += 1
            ok = False
            test = dict(status='FAILED', result=call.excinfo)
        elif outcome == 'skipped':
            test = dict(status='SKIPPED', result=call.excinfo)
        else:
            test = {}
        if passed + failed:
            result = passed / (passed + failed)
        details['tests'].append(test)
