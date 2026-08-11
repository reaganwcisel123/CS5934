from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_gemini_key_stays_server_side_and_env_example_is_blank():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    frontend = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "dashboard" / "app").rglob("*.js"))
    assert "GEMINI_API_KEY=" in env
    assert "GEMINI_API_KEY=your" not in env
    assert "GEMINI_API_KEY" not in frontend
    assert "google.genai" not in frontend and "google-generativeai" not in frontend


def test_production_grant_code_contains_no_vector_retrieval_imports():
    source = "\n".join((ROOT / "src" / "grants" / name).read_text(encoding="utf-8") for name in ("recommender.py", "gemini.py", "pipeline.py"))
    assert "TfidfVectorizer" not in source
    assert "NearestNeighbors" not in source
    assert "sklearn.feature_extraction" not in source
