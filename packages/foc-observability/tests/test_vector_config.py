from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_vector_internal_logs_promote_metadata_level():
    config = (REPOSITORY_ROOT / "observability/vector.yaml").read_text()

    assert "is_object(.metadata) && is_string(.metadata.level)" in config
    assert ".level = .metadata.level" in config
