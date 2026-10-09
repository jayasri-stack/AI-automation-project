"""Streamlit topic selection, research, preview, and approval dashboard."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from story_video_automation.approval import decide, upload_approved_job
from story_video_automation.db import list_jobs
from story_video_automation.options import Options
from story_video_automation.state import (
    get_story,
    get_upload_privacy,
    get_made_for_kids,
    initialize,
    list_events,
    list_research,
    delete_job,
    reset_uncertain_upload,
    set_upload_settings,
)
from story_video_automation.channel_profile import build_search_queries
from story_video_automation.youtube_research import search_videos
from story_video_automation.telegram_bot import send_approval_notification
from story_video_automation.pipeline import revise_preview

def main() -> None:
    initialize()
    st.set_page_config(page_title="AI Automation Project", layout="wide")
    st.title("AI Story Video Studio")
    st.caption("Find recent high-velocity videos in your niche, select references, generate a draft, revise it by prompt, then approve before upload.")
    options = Options.from_env()
    if options.video_provider == "local" and options.speech_provider == "local":
        st.info(
            "No-cost mode is active: illustrated village scenes animate on your PC and narration uses an installed "
            "Windows voice. Gemini Flash stays on its free tier unless you link billing."
        )
    elif options.video_provider == "veo":
        st.warning("Veo video generation is a paid service. Each generated second may incur a charge.")
    st.markdown(
        "Uses the YouTube Data API. [Google Privacy Policy](https://policies.google.com/privacy) · "
        "[Local data and privacy notice](https://github.com/jayasri-stack/AI-automation-project/blob/main/docs/PRIVACY.md)"
    )

    with st.expander("Create a story video", expanded=not bool(st.session_state.get("research_results"))):
        with st.form("research-form"):
            st.info(
                "Fixed channel niche: peaceful Telugu village serials set in the 1980s, "
                "with traditional vintage life, calm narration, moral values, recurring "
                "characters, and connected cliffhanger episodes."
            )
            topic = st.text_input(
                "Optional episode idea or extra search words",
                placeholder="Leave blank for an automatic niche search; or add: a lost calf returns home",
                help="The app always searches the fixed channel niche. An episode idea narrows today's search.",
            )
            language = st.selectbox("Script language", [("te", "Telugu"), ("en", "English")],
                                    format_func=lambda item: item[1])[0]
            upload_privacy = st.selectbox(
                "YouTube upload visibility",
                ["private", "unlisted", "public"],
                index=["private", "unlisted", "public"].index(
                    Options.from_env().upload_privacy
                ),
                help="Shown here and in Telegram before approval. Default is private.",
            )
            configured_audience = Options.from_env().made_for_kids
            audience_choice = st.selectbox(
                "Audience declaration",
                ["choose", "yes", "no"],
                format_func=lambda value: {
                    "choose": "Choose made for kids or not made for kids",
                    "yes": "Made for kids",
                    "no": "Not made for kids",
                }[value],
                index={None: 0, True: 1, False: 2}[configured_audience],
                help="This declaration is sent to YouTube with an approved upload.",
            )
            submitted = st.form_submit_button("Find trending niche videos")
        if submitted:
            try:
                search_queries = build_search_queries(topic, language)
                st.session_state["research_results"] = search_videos(search_queries, language)
                st.session_state["research_topic"] = topic.strip() or "an original episode in the ongoing village story serial"
                st.session_state["research_language"] = language
            except Exception as exc:
                st.error(f"YouTube search failed: {exc}")

        results = st.session_state.get("research_results", [])
        if results:
            st.markdown("#### YouTube videos in this niche")
            st.caption("Searches use Telugu phrases for Telugu episodes and English phrases for English episodes. They cover 1980s village life, vintage VHS stories, traditional cooking, customs, and moral tales. Videos from any publication date may appear; duplicates are removed and results are ranked by estimated views per day. The top three guide an original story; source footage is never downloaded or reused.")
            for rank, result in enumerate(results, 1):
                cols = st.columns([0.6, 1, 4, 1.5])
                with cols[0]:
                    st.caption(f"#{rank}")
                with cols[1]:
                    if result.get("thumbnail_url"):
                        st.image(result["thumbnail_url"], width=140)
                with cols[2]:
                    st.markdown(f"[{result['title']}]({result['url']})  \n{result['channel_title']}")
                with cols[3]:
                    st.caption(f"Views: {result['view_count'] if result['view_count'] is not None else 'N/A'}\n\nEst. views/day: {result.get('views_per_day', 0):,.0f}")
            selected = results[:3]
            if st.button("Generate next episode from top trends", type="primary", disabled=not selected):
                try:
                    from story_video_automation.pipeline import start_workflow

                    job_id = start_workflow(
                        st.session_state["research_topic"],
                        st.session_state["research_language"],
                        references=selected,
                        upload_privacy=upload_privacy,
                        made_for_kids=(True if audience_choice == "yes" else
                                       False if audience_choice == "no" else None),
                    )
                    st.session_state.pop("research_results", None)
                    mode = Options.from_env().video_provider
                    if mode == "local":
                        from story_video_automation.pipeline import process_pending

                        result = process_pending(job_ids={job_id})
                        if result["completed"]:
                            st.success(f"Job #{job_id} is ready. Its preview is now in Video jobs, and Telegram was notified.")
                        else:
                            st.info(f"Job #{job_id} was created; check its status and error details in Video jobs.")
                    else:
                        st.success(f"Job #{job_id} created; Veo scene generation is running asynchronously.")
                except Exception as exc:
                    st.error(f"Could not start the workflow: {exc}")

    st.divider()
    st.subheader("Video jobs")

    jobs = list_jobs()
    focus_value = st.query_params.get("job_id")
    if focus_value and str(focus_value).isdigit():
        focus_id = int(focus_value)
        jobs.sort(key=lambda item: item["id"] != focus_id)
        st.info(f"Telegram linked to job #{focus_id}; its review is listed first below.")
    if not jobs:
        st.info("No jobs yet. Search a topic above to begin.")
        return

    for job in jobs:
        with st.container(border=True):
            left, right = st.columns([2, 1])
            with left:
                st.subheader(job["title"])
                st.write(f"Language: {job['language']} · Status: **{job['status']}**")
                if job.get("youtube_video_id"):
                    st.markdown(
                        f"[View uploaded video](https://www.youtube.com/watch?v={job['youtube_video_id']})"
                    )
                progress = {
                    "queued": 0.0, "researching": 0.1, "writing": 0.25,
                    "generating_video": 0.45, "narrating": 0.7, "editing": 0.85,
                    "awaiting_approval": 1.0, "approved": 1.0,
                    "uploading": 1.0, "uploaded": 1.0, "rejected": 1.0, "failed": 1.0,
                }
                st.progress(progress.get(job["status"], 0.0))
                if job.get("error"):
                    st.error(job["error"])
                story = get_story(job["id"])
                if story:
                    with st.expander("Story and script"):
                        st.markdown(f"**Synopsis:** {story['synopsis']}")
                        st.markdown(f"**Episode {story.get('episode_number', 1)} connection:** {story.get('continuity_bridge', '—')}")
                        st.markdown(f"**Next episode hook:** {story.get('next_episode_hook', '—')}")
                        st.text_area("Narration script", story["script"], height=160,
                                     key=f"script-{job['id']}", disabled=True)
                        insights = story.get("trend_insights", {})
                        if insights:
                            st.markdown("**Trend analysis used**")
                            st.write("Themes: " + ", ".join(map(str, insights.get("themes", []))))
                            st.write("Audience hooks: " + ", ".join(map(str, insights.get("audience_hooks", []))))
                        bible = story.get("series_bible", {})
                        if bible:
                            with st.expander("Series bible — recurring characters and open threads"):
                                st.write(f"Setting: {bible.get('setting', '—')}")
                                for character in bible.get("characters", []):
                                    st.markdown(f"- **{character.get('name', 'Character')}:** {character.get('description', '')}")
                                threads = bible.get("unresolved_threads", [])
                                st.write("Unresolved threads: " + ("; ".join(map(str, threads)) if threads else "None"))
                        report = story.get("quality_report", {})
                        if report:
                            st.markdown("**Automated draft checks:** " + ("Passed" if report.get("passed") else "Needs review"))
                            for warning in report.get("warnings", []):
                                st.warning(warning)
                        for scene in story["scenes"]:
                            st.caption(
                                f"Scene {scene['scene_number']}: "
                                f"{scene['operation_state']} — {scene['visual_prompt']}"
                            )
                references = list_research(job["id"])
                if references:
                    with st.expander(f"Research references ({len(references)})"):
                        st.caption("YouTube data shown as returned; search-result content is not redistributed.")
                        for reference in references:
                            st.markdown(
                                f"[{reference['title']}]({reference['url']}) — "
                                f"{reference['channel_title']} · views: "
                                f"{reference['view_count'] if reference['view_count'] is not None else 'N/A'} "
                                f"(as of {reference['collected_at']})"
                            )
                preview = job.get("preview_path")
                if preview and Path(preview).is_file():
                    st.video(preview)
                    if job["status"] == "awaiting_approval":
                        with st.form(f"revise-preview-{job['id']}"):
                            revision = st.text_area(
                                "Change this draft with a prompt",
                                placeholder="Make the opening more dramatic; add a hopeful ending; simplify the narration.",
                                key=f"revision-prompt-{job['id']}",
                            )
                            revise = st.form_submit_button(
                                "Apply prompt and regenerate preview",
                                disabled=Options.from_env().video_provider != "local",
                            )
                        if Options.from_env().video_provider != "local":
                            st.caption("Prompt revisions currently use the free local 2D village animator. Veo revisions are not available from this panel.")
                        if revise:
                            try:
                                revise_preview(job["id"], revision)
                                st.success("Updated preview created. Telegram was notified to review the new version.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not revise this draft: {exc}")
                elif job["status"] == "awaiting_approval":
                    st.warning("This job is awaiting approval, but its preview file is unavailable.")
            with right:
                if job["status"] == "awaiting_approval":
                    st.caption(f"Upload visibility: {get_upload_privacy(job['id'])}")
                    made_for_kids = get_made_for_kids(job["id"])
                    if made_for_kids is None:
                        audience_choice = st.selectbox(
                            "Audience declaration before approval",
                            ["choose", "yes", "no"],
                            format_func=lambda value: {
                                "choose": "Choose made for kids or not made for kids",
                                "yes": "Made for kids",
                                "no": "Not made for kids",
                            }[value],
                            key=f"audience-{job['id']}",
                        )
                        if audience_choice != "choose" and st.button(
                            "Save audience declaration", key=f"save-audience-{job['id']}"
                        ):
                            set_upload_settings(
                                job["id"], get_upload_privacy(job["id"]),
                                made_for_kids=(audience_choice == "yes"),
                            )
                            st.rerun()
                        st.info("Choose the audience declaration before approving or uploading.")
                    else:
                        st.caption("Audience: " + ("Made for kids" if made_for_kids else "Not made for kids"))
                    can_review = bool(
                        preview and Path(preview).is_file() and made_for_kids is not None
                    )
                    if can_review and st.button(
                        "Send Telegram approval", key=f"notify-{job['id']}"
                    ):
                        try:
                            send_approval_notification(job["id"])
                            st.success("Telegram approval buttons sent.")
                        except Exception as exc:
                            st.error(f"Could not notify Telegram: {exc}")
                    if st.button("Approve and upload", key=f"approve-{job['id']}",
                                 type="primary", disabled=not can_review):
                        try:
                            video_id = decide(job["id"], "approved", "dashboard")
                            if video_id:
                                st.success(f"Uploaded: https://www.youtube.com/watch?v={video_id}")
                            else:
                                st.success("Approval saved. Upload is ready once YouTube OAuth is configured.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Approval was saved, but upload could not finish: {exc}")
                    if st.button("Reject", key=f"reject-{job['id']}", disabled=not can_review):
                        decide(job["id"], "rejected", "dashboard")
                        st.success("Rejected. This job cannot be uploaded.")
                        st.rerun()
                elif job["status"] == "approved":
                    if st.button("Retry upload", key=f"retry-upload-{job['id']}"):
                        try:
                            video_id = upload_approved_job(job["id"])
                            st.success(f"Uploaded: https://www.youtube.com/watch?v={video_id}")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Upload did not complete: {exc}")
                elif job["status"] == "uploading":
                    st.warning("Upload outcome is uncertain. Check your YouTube Studio before retrying.")
                    confirmed_absent = st.checkbox(
                        "I checked YouTube Studio and this video is not there",
                        key=f"absent-{job['id']}",
                    )
                    if st.button("Reset to approved", key=f"reset-upload-{job['id']}",
                                 disabled=not confirmed_absent):
                        reset_uncertain_upload(job["id"], confirmed_absent=True)
                        st.rerun()
                elif job["status"] in {"approved", "rejected", "uploaded"}:
                    st.write(f"Decision: **{job['status']}**")
                with st.expander("Job history"):
                    for event in list_events(job["id"]):
                        st.caption(f"{event['created_at']} — {event['from_status'] or 'new'} → "
                                   f"{event['to_status']} · {event['detail'] or ''}")
                if st.button("Delete job and generated files", key=f"delete-{job['id']}"):
                    st.session_state["confirm_delete_job"] = job["id"]
                if st.session_state.get("confirm_delete_job") == job["id"]:
                    st.warning("This permanently removes the job record and its generated files.")
                    confirmed = st.checkbox("I understand", key=f"confirm-delete-{job['id']}")
                    if st.button("Delete permanently", key=f"delete-confirm-{job['id']}",
                                 disabled=not confirmed):
                        delete_job(job["id"])
                        st.session_state.pop("confirm_delete_job", None)
                        st.rerun()


if __name__ == "__main__":
    main()
