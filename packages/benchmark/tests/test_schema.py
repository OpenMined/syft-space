"""The schema reflects the decisions from the brief, not just "some tables"."""

from syft_benchmark.db.models import Base, QaPair, Result, Run


def test_the_schema_is_measurement_plus_control_plus_configuration() -> None:
    """Three groups of tables, and they must not be mixed.

    The measurement is pairs, parsed material, runs and verdicts. Control is
    targets and jobs: who asked for a measurement, with what, and where it
    stands now. A ``runs`` row does not answer "is my launch still going" and
    cannot: its unit is "arm x block x model", and one launch holds dozens of
    them.

    Configuration is the third, and it is three tables rather than one on
    purpose. The settings are read on every launch, copied into a job's
    snapshot and every run's params and handed out by ``/defaults``; a provider
    key kept among them would travel everywhere they travel. The secrets sit
    apart and sealed. The model catalogue sits apart for a different reason: it
    is not configuration but a copy of somebody else's list.
    """
    assert set(Base.metadata.tables) == {
        "qa_pairs",
        "processed_units",
        "runs",
        "results",
        "targets",
        "jobs",
        "installation_settings",
        "credentials",
        "model_catalog",
    }


def test_no_secret_has_a_column_of_its_own_anywhere() -> None:
    """A secret is sealed in ``credentials`` or it is not stored.

    The Space tokens used to be a plain text column on ``targets``, which meant
    they were in every dump, backup and replica of this database. Nothing is to
    quietly grow such a column again — and a column called ``token`` or ``key``
    on any other table would be exactly that.
    """
    offenders = [
        f"{table}.{column.name}"
        for table, definition in Base.metadata.tables.items()
        if table != "credentials"
        for column in definition.columns
        if column.name in {"token", "secret", "api_key", "password"}
    ]
    assert offenders == []


def test_a_job_outlives_the_target_it_measured() -> None:
    """A target gets deleted, the history of measurements does not.

    A foreign key with a cascade would take away the answer to "what was ever
    done with this endpoint", and that outlives both the configuration and the
    target itself.
    """
    from syft_benchmark.db.models import Job

    assert not Job.__table__.columns["target"].foreign_keys


def test_a_target_keeps_overrides_rather_than_a_snapshot() -> None:
    """A target holds only what its owner set, not the full set of settings.

    A full snapshot would freeze the installation's defaults on the day the
    target was created, and a raised answer cap would not reach a single node.
    """
    from syft_benchmark.db.models import Target

    assert {"instrument", "probe"} <= set(Target.__table__.columns.keys())


def test_run_distinguishes_the_two_passes() -> None:
    """Without context_mode runs A and B merge, and the comparison is the point."""
    assert "context_mode" in Run.__table__.columns


def test_processed_unit_is_keyed_by_generator_and_cohort() -> None:
    """There are eight generators, and the same chunk goes to every one of them.

    Without the generator in the key, a second generator would silently skip
    everything the first managed to parse. The cohort is in the key for the same
    reason: rebuilding the set is a fresh parse of THE SAME material, and the
    mark of an earlier build must not stop it.
    """
    from syft_benchmark.db.models import ProcessedUnit

    keys = {c.name for c in ProcessedUnit.__table__.primary_key.columns}
    assert keys == {"space", "generator", "unit_id", "cohort"}


def test_a_question_may_repeat_in_another_cohort() -> None:
    """A repeated question between cohorts is legitimate and meaningful.

    It means the generator produced the same question from the same material,
    that is, that it is stable. Forbidding such a repeat would make a rebuild
    impossible: the second pass would be rejected whole.
    """
    unique = next(
        c
        for c in QaPair.__table__.constraints
        if getattr(c, "name", "") == "qa_pairs_unique"
    )
    assert {c.name for c in unique.columns} == {
        "space",
        "generator",
        "question_hash",
        "cohort",
    }


def test_pair_carries_review_status() -> None:
    """Rejecting reference answers: a pair only takes part in runs as active."""
    assert "status" in QaPair.__table__.columns


def test_result_records_mode_and_retrieval() -> None:
    """The endpoint's mode is fixed as of the run, not read afterwards.

    And the retrieval metrics are what raw mode is measured by, where there is
    no model at all.
    """
    columns = Result.__table__.columns
    assert "endpoint_response_type" in columns
    assert "retrieval_hit" in columns
    assert "retrieval_rank" in columns


def test_no_duplicate_questions_across_daily_runs() -> None:
    names = {c.name for c in QaPair.__table__.constraints}
    assert "qa_pairs_unique" in names


def test_run_records_the_arm_and_what_was_mixed_in() -> None:
    """Arm C is uninterpretable without a context source.

    "A model on raw chunks" and "a model handed someone else's finished
    conclusion" measure different things and give different numbers.
    """
    columns = set(Run.__table__.columns.keys())
    assert {"context_source", "profile", "params"} <= columns


def test_pair_says_what_correct_behaviour_is() -> None:
    """The correct behaviour is set by the question, not by whoever answers."""
    assert "expected_behavior" in QaPair.__table__.columns
    assert "expected_behavior" in Result.__table__.columns


def test_result_keeps_the_audit_trail() -> None:
    """The benchmark's number is a model's verdict: this is where it is checked."""
    assert "audit" in Result.__table__.columns
