"""Path setup and fixtures for the ci-watch skill."""

import sys

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "ci-watch"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))


def check(name, conclusion="success", status="completed"):
    return {"name": name, "status": status, "conclusion": conclusion}


class Clock:
    """A clock the tests drive, so no test ever sleeps."""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class Checks:
    """Returns a scripted sequence of check-run responses."""

    def __init__(self, *rounds, error=None, errors=0):
        self.rounds = list(rounds)
        self.error = error
        self.errors = errors
        self.calls = 0

    def __call__(self, *_args):
        self.calls += 1
        if self.errors > 0:
            self.errors -= 1
            raise self.error or RuntimeError("transient")
        if not self.rounds:
            return []
        if len(self.rounds) == 1:
            return self.rounds[0]
        return self.rounds.pop(0)
