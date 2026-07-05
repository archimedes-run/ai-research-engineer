"""S2-0: freeze guard for the Stage 1 retrieval benchmark pairs.

Changing a (query, target) pair must update FROZEN_PAIRS_SHA *and* leave a
CHANGELOG entry (with that digest) in benchmarks/knowledge/README.md. These two
tests fail otherwise, so query tuning after a miss always leaves a paper trail.
"""

from pathlib import Path

from benchmarks.knowledge import retrieval_recall as rr


_README = Path(rr.__file__).resolve().parent / "README.md"


def test_pairs_match_frozen_sha():
    # If PAIRS were edited without updating FROZEN_PAIRS_SHA, this bites.
    assert rr.frozen_pairs_sha() == rr.FROZEN_PAIRS_SHA, (
        "The frozen retrieval pairs changed. If intentional, update "
        "FROZEN_PAIRS_SHA to frozen_pairs_sha() and add a README CHANGELOG entry."
    )


def test_frozen_sha_recorded_in_readme():
    # The current SHA must appear in the CHANGELOG — so bumping the SHA forces a
    # documented entry rather than a silent constant edit.
    text = _README.read_text(encoding="utf-8")
    assert rr.FROZEN_PAIRS_SHA in text, (
        "FROZEN_PAIRS_SHA is not recorded in benchmarks/knowledge/README.md; "
        "add a dated CHANGELOG entry with the new digest."
    )


def test_pair_count_is_ten():
    assert len(rr.PAIRS) == 10
