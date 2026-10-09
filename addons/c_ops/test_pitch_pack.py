import os
import re
import pytest

PITCH_DIR = os.path.join(os.path.dirname(__file__), "out", "pitch")


def test_slides_formatting():
    slides_path = os.path.join(PITCH_DIR, "slides.md")
    assert os.path.isfile(slides_path)

    with open(slides_path, "r", encoding="utf-8") as f:
        content = f.read()

    slides = [s for s in content.split("## Slide ") if s.strip() and not s.startswith("# Pitch Deck")]
    assert len(slides) == 7, f"Expected 7 slides, found {len(slides)}"

    for idx, slide in enumerate(slides, 1):
        lines = [line.strip() for line in slide.strip().split("\n") if line.strip()]
        title_line = lines[0]
        # Title should be after "X: "
        if ":" in title_line:
            title_text = title_line.split(":", 1)[1].strip()
        else:
            title_text = title_line
        title_words = title_text.split()
        assert len(title_words) <= 8, f"Slide {idx} title has {len(title_words)} words: '{title_text}'"

        bullets = [ln for ln in lines if ln.startswith("- ")]
        assert len(bullets) <= 3, f"Slide {idx} has {len(bullets)} bullets (max 3 allowed)"
        for b_idx, bullet in enumerate(bullets):
            bullet_text = bullet.lstrip("- ").strip()
            b_words = bullet_text.split()
            assert len(b_words) <= 12, f"Slide {idx} bullet {b_idx} has {len(b_words)} words: '{bullet_text}'"

        assert "**Speaker Notes:**" in slide
        notes_part = slide.split("**Speaker Notes:**")[1].split("---")[0].strip()
        sentences = [s.strip() for s in re.split(r"[.!?]+", notes_part) if s.strip() and s.strip() != "---"]
        assert 3 <= len(sentences) <= 4, f"Slide {idx} notes have {len(sentences)} sentences (expected 3-4): {sentences}"


def test_demo_script_structure():
    script_path = os.path.join(PITCH_DIR, "demo_script.md")
    assert os.path.isfile(script_path)

    with open(script_path, "r", encoding="utf-8") as f:
        text = f.read()

    expected_timestamps = ["0:00", "0:30", "1:15", "2:15", "2:35", "2:50"]
    for ts in expected_timestamps:
        assert ts in text, f"Missing timestamp {ts} in demo script"

    break_count = text.count("If something breaks:")
    assert break_count >= 6, f"Expected at least 6 'if something breaks' lines, found {break_count}"


def test_judge_questions_count_and_topics():
    jq_path = os.path.join(PITCH_DIR, "judge_questions.md")
    assert os.path.isfile(jq_path)

    with open(jq_path, "r", encoding="utf-8") as f:
        text = f.read()

    questions = [q for q in text.split("### Q") if q.strip() and not q.startswith("# 15")]
    assert len(questions) == 15, f"Expected 15 questions, found {len(questions)}"

    # Check required topics
    lower_text = text.lower()
    assert "covariance" in lower_text
    assert "accurate" in lower_text and "tle" in lower_text
    assert "trust" in lower_text and "manoeuvre" in lower_text
    assert "other object also manoeuvres" in lower_text
    assert "one constellation" in lower_text
    assert "ml model" in lower_text or "machine learning" in lower_text
    assert "existing services" in lower_text
    assert "real operations" in lower_text


def test_readme_exists():
    readme_path = os.path.join(os.path.dirname(__file__), "README.md")
    assert os.path.isfile(readme_path)
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "watch.py" in content
    assert "alert_feed.json" in content
    assert "predict_final_risk" in content
    assert "Known Gaps" in content
