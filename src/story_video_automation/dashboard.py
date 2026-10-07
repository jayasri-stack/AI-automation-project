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
from story_video_automation.youtube_research import search_videos
from story_video_automation.telegram_bot import send_approval_notification


def main() -> None:
    initialize()
    st.set_page_config(page_title="AI Automation Project", layout="wide")
    st.title("AI Story Video Studio")
    st.caption("Research a topic, select references, generate a story, then review before upload.")
    options = Options.from_env()
    if options.video_provider == "local" and options.speech_provider == "local":
        st.info(
            "No-cost mode is active: scene cards render on your PC and narration uses an installed "
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
            topic = st.text_input("Topic or search query", placeholder="A Telugu folk tale about courage")
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
            submitted = st.form_submit_button("Search YouTube")
        if submitted:
            if not topic.strip():
                st.error("Enter a topic to search.")
            else:
                try:
                    st.session_state["research_results"] = search_videos(topic, language)
                    st.session_state["research_topic"] = topic.strip()
                    st.session_state["research_language"] = language
                except Exception as exc:
                    st.error(f"YouTube search failed: {exc}")

        results = st.session_state.get("research_results", [])
        if results:
            st.markdown("#### YouTube search results — select videos to keep with this job")
            st.caption("Titles, links, and statistics below come from YouTube. They are not sent to Gemini.")
            selected_ids: list[str] = []
            for result in results:
                cols = st.columns([0.6, 4, 1])
                with cols[0]:
                    selected = st.checkbox("Select", key=f"select-{result['video_id']}",
                                            label_visibility="collapsed")
                with cols[1]:
                    st.markdown(f"[{result['title']}]({result['url']})  \n{result['channel_title']}")
                with cols[2]:
                    st.caption(f"Views: {result['view_count'] if result['view_count'] is not None else 'N/A'}")
                if selected:
                    selected_ids.append(result["video_id"])
            selected = [item for item in results if item["video_id"] in selected_ids]
            if st.button("Generate original story and scenes", type="primary", disabled=not selected):
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
                    message = (
                        "local scene cards are ready to process"
                        if mode == "local"
                        else "Veo scene generation is running asynchronously"
                    )
                    st.success(f"Job #{job_id} created; {message}.")
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
                        st.text_area("Narration script", story["script"], height=160,
                                     key=f"script-{job['id']}", disabled=True)
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
