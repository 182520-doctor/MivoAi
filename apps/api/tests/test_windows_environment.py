from __future__ import annotations

from app.shared.windows_environment import merge_registered_environment


def test_merges_new_user_environment_values_without_overwriting_process_values() -> None:
    environ = {"EXISTING": "process", "EMPTY": ""}

    changed = merge_registered_environment(
        [
            ("EXISTING", "registered"),
            ("EMPTY", "registered-empty"),
            ("STRATA_API_KEY", "test-key"),
            ("", "ignored"),
        ],
        environ,
    )

    assert changed == 2
    assert environ == {
        "EXISTING": "process",
        "EMPTY": "registered-empty",
        "STRATA_API_KEY": "test-key",
    }


def test_explicit_overwrite_replaces_existing_value() -> None:
    environ = {"EXISTING": "process"}

    changed = merge_registered_environment(
        [("EXISTING", "registered")],
        environ,
        overwrite=True,
    )

    assert changed == 1
    assert environ["EXISTING"] == "registered"
