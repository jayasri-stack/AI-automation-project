"""Streamlit review dashboard for generated video previews."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from story_video_automation.config import get_settings
from story_video_automation.db import initialize_database, list_jobs, record_approval


def main() -> None:
    settings = get_settings()
    initialize_database(settings.database_path)

    st.set_page_config(page_title="AI Automation Project", layout="wide")
    st.title("Story Video Review")
    st.caption("Review generated previews. Only an approved job may enter the upload workflow.")

    jobs = list_jobs(settings.database_path)
    if not jobs:
        st.info("No workflow jobs yet. The dashboard will show previews here when they are ready.")
        return

    for job in jobs:
        with st.container(border=True):
            left, right = st.columns([2, 1])
            with left:
                st.subheader(job["title"])
                st.write(f"Language: {job['language']} · Status: **{job['status']}**")
                preview = job.get("preview_path")
                if preview and Path(preview).is_file():
                    st.video(preview)
                elif job["status"] == "awaiting_approval":
                    st.warning("This job is awaiting approval, but its preview file is unavailable.")
            with right:
                if job["status"] == "awaiting_approval":
                    if st.button("Approve", key=f"approve-{job['id']}", type="primary"):
                        record_approval(job["id"], "approved", database_path=settings.database_path)
                        st.rerun()
                    if st.button("Reject", key=f"reject-{job['id']}"):
                        record_approval(job["id"], "rejected", database_path=settings.database_path)
                        st.rerun()
                elif job["status"] in {"approved", "rejected", "uploaded"}:
                    st.write(f"Decision: **{job['status']}**")
                    if job.get("youtube_video_id"):
                        st.write(f"YouTube video: `{job['youtube_video_id']}`")


if __name__ == "__main__":
    main()
