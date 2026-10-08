from story_video_automation.story_quality import evaluate_story


def valid_story(**overrides):
    story = {
        "title": "The Lamp by the Old Well",
        "synopsis": "A village family follows a clue to restore an old well.",
        "script": "A lamp flickers by the well.\n\nMeena hears a familiar song.",
        "language": "en",
        "scenes": [
            {"visual_prompt": "A warm 1980s village evening", "narration": "A lamp flickers by the well."},
            {"visual_prompt": "A woman listens near an old well", "narration": "Meena hears a familiar song."},
        ],
        "trend_insights": {"themes": ["community"], "audience_hooks": ["mystery"]},
        "series_bible": {
            "setting": "A Telugu village in 1980s rural India",
            "characters": ["Meena", "Ramu"],
            "unresolved_threads": ["Who lit the lamp?"],
        },
        "continuity_bridge": "Meena returns to the well after yesterday's discovery.",
        "next_episode_hook": "A second lamp appears across the river.",
    }
    story.update(overrides)
    return story


def test_accepts_complete_serial_draft():
    report = evaluate_story(valid_story(), [{"title": "Village Life in 1980"}])
    assert report["passed"] is True
    assert report["errors"] == []


def test_rejects_script_that_does_not_match_scene_narration():
    report = evaluate_story(valid_story(script="A different script"))
    assert report["passed"] is False
    assert report["checks"]["script_matches_scenes"] is False


def test_rejects_exact_copy_of_research_title():
    report = evaluate_story(
        valid_story(title="Village Life in 1980"), [{"title": "Village Life in 1980"}]
    )
    assert report["passed"] is False
    assert any("exactly matches" in error for error in report["errors"])


def test_requires_next_episode_hook():
    report = evaluate_story(valid_story(next_episode_hook=""))
    assert report["passed"] is False
    assert report["checks"]["next_episode_hook"] is False


def test_trend_insights_are_required_when_references_exist():
    story = valid_story(trend_insights={})
    assert evaluate_story(story)["passed"] is True
    assert evaluate_story(story, [{"title": "Village Life"}])["passed"] is False


def test_checks_expected_scene_count_and_recurring_characters():
    story = valid_story()
    prior = {"series_bible": {"characters": [{"name": "Ramu"}, {"name": "Lakshmi"}]}}
    report = evaluate_story(story, expected_scene_count=3, previous_episode=prior)

    assert report["checks"]["scene_count"] is False
    assert report["checks"]["recurring_characters_preserved"] is False
    assert report["passed"] is False


def test_detects_exact_telugu_title_copy():
    title = "పాత బావి దగ్గర దీపం"
    report = evaluate_story(valid_story(title=title), [{"title": title}])

    assert report["checks"]["title_originality"] is False
