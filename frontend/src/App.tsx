import { useCallback, useEffect, useMemo, useState } from "react";

type Scene = { scene_number: number; visual_prompt: string; narration: string };
type Story = {
  synopsis: string;
  script: string;
  episode_number: number;
  trend_insights: { themes?: string[]; audience_hooks?: string[] };
  series_bible: {
    setting?: string;
    characters?: { name: string; description: string }[];
    unresolved_threads?: string[];
  };
  continuity_bridge: string;
  next_episode_hook: string;
  quality_report: { passed?: boolean; warnings?: string[]; checks?: Record<string, boolean> };
  scenes: Scene[];
};
type Research = {
  title: string;
  channel_title?: string;
  url: string;
  thumbnail_url?: string;
  view_count?: number;
  views_per_day?: number;
};
type Job = {
  id: number;
  title: string;
  language: "te" | "en";
  status: string;
  preview_path?: string | null;
  youtube_video_id?: string | null;
  error?: string | null;
  story: Story | null;
  research: Research[];
  events: { to_status: string; detail?: string; created_at: string }[];
  upload_privacy: string;
  made_for_kids: boolean | null;
};

const API = "";
const savedToken = () => window.localStorage.getItem("story-studio-api-token") ?? "";

function PreviewVideo({
  jobId,
  previewPath,
  token,
}: {
  jobId: number;
  previewPath: string;
  token: string;
}) {
  const [src, setSrc] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = "";
    setSrc("");
    setError("");
    void fetch(`/api/jobs/${jobId}/preview`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Preview failed to load (${response.status}).`);
        return response.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Preview failed to load.");
        }
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [jobId, previewPath, token]);

  return (
    <>
      {error && <div className="notice error">{error}</div>}
      {src && <video className="preview-video" controls preload="metadata" src={src} />}
      {!src && !error && <p className="fine-print">Loading video preview…</p>}
    </>
  );
}

export default function App() {
  const [token, setToken] = useState(savedToken);
  const [tokenDraft, setTokenDraft] = useState(savedToken);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const value = Number(new URLSearchParams(window.location.search).get("job_id"));
    return Number.isSafeInteger(value) && value > 0 ? value : null;
  });
  const [niche, setNiche] = useState("Peaceful Telugu village stories set in the 1980s");
  const [topic, setTopic] = useState("");
  const [language, setLanguage] = useState<"te" | "en">("te");
  const [privacy, setPrivacy] = useState("private");
  const [audience, setAudience] = useState("");
  const [research, setResearch] = useState<Research[]>([]);
  const [revision, setRevision] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const selected = useMemo(
    () => jobs.find((job) => job.id === selectedId) ?? jobs[0] ?? null,
    [jobs, selectedId],
  );
  const request = useCallback(
    async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
      const headers = new Headers(init.headers);
      headers.set("Content-Type", "application/json");
      if (token) headers.set("Authorization", `Bearer ${token}`);
      const response = await fetch(`${API}${path}`, { ...init, headers });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail ?? `Request failed (${response.status})`);
      return body as T;
    },
    [token],
  );

  const refresh = useCallback(async () => {
    try {
      const [nextJobs, config] = await Promise.all([
        request<Job[]>("/api/jobs"),
        request<{ niche: string }>("/api/config"),
      ]);
      setJobs(nextJobs);
      setNiche(config.niche);
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not connect to the API.");
    }
  }, [request]);

  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const saveToken = () => {
    window.localStorage.setItem("story-studio-api-token", tokenDraft.trim());
    setToken(tokenDraft.trim());
    setMessage("API token saved in this browser.");
  };

  const search = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy("research");
    setError("");
    setMessage("");
    try {
      const results = await request<Research[]>("/api/research", {
        method: "POST",
        body: JSON.stringify({ topic, language }),
      });
      setResearch(results);
      if (!results.length)
        setMessage(
          "No recent videos were returned for this search. Try a more specific episode idea.",
        );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "YouTube research failed.");
    } finally {
      setBusy("");
    }
  };

  const generate = async () => {
    setBusy("generate");
    setError("");
    setMessage("");
    try {
      const job = await request<Job>("/api/jobs", {
        method: "POST",
        body: JSON.stringify({
          topic: topic || "an original episode in the ongoing village serial",
          language,
          references: research.slice(0, 3),
          upload_privacy: privacy,
          made_for_kids: audience === "yes",
        }),
      });
      setSelectedId(job.id);
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      setResearch([]);
      setMessage(`Episode draft #${job.id} created. Review it below.`);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The workflow could not create a draft.");
    } finally {
      setBusy("");
    }
  };

  const review = async (decision: "approved" | "rejected") => {
    if (!selected) return;
    setBusy(decision);
    setError("");
    setMessage("");
    try {
      const result = await request<{ message: string; job: Job }>(
        `/api/jobs/${selected.id}/decision`,
        {
          method: "POST",
          body: JSON.stringify({ decision }),
        },
      );
      setMessage(result.message);
      setJobs((current) => current.map((job) => (job.id === selected.id ? result.job : job)));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The review action failed.");
    } finally {
      setBusy("");
      await refresh();
    }
  };

  const revise = async () => {
    if (!selected) return;
    setBusy("revision");
    setError("");
    setMessage("");
    try {
      const result = await request<{ job: Job }>(`/api/jobs/${selected.id}/revision`, {
        method: "POST",
        body: JSON.stringify({ instructions: revision }),
      });
      setJobs((current) => current.map((job) => (job.id === selected.id ? result.job : job)));
      setRevision("");
      setMessage("Updated preview is ready for review.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The revision failed.");
    } finally {
      setBusy("");
      await refresh();
    }
  };

  const retryUpload = async () => {
    if (!selected) return;
    setBusy("upload");
    setError("");
    setMessage("");
    try {
      const result = await request<{ message: string; job: Job }>(
        `/api/jobs/${selected.id}/retry-upload`,
        { method: "POST" },
      );
      setMessage(result.message);
      setJobs((current) => current.map((job) => (job.id === selected.id ? result.job : job)));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed.");
    } finally {
      setBusy("");
      await refresh();
    }
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Village Story Studio home">
          <span className="brand-mark">✦</span>
          <span>
            Village Story Studio<small>AI production desk</small>
          </span>
        </a>
        <div className="topbar-right">
          <span className="live-dot" /> <span>Local workspace</span>
          <button className="quiet-button" onClick={() => void refresh()}>
            Refresh
          </button>
        </div>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow">A connected story, one episode at a time</p>
          <h1>
            From village idea
            <br />
            to <em>review-ready</em> film.
          </h1>
          <p className="hero-text">
            Find niche signals, shape the next chapter, and review every video before it goes
            anywhere.
          </p>
          <div className="niche-pill">
            <span>CHANNEL IDENTITY</span>
            {niche}
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="sun" />
          <div className="hill hill-back" />
          <div className="hill hill-front" />
          <div className="house">
            <div className="roof" />
            <div className="door" />
          </div>
          <div className="tree">
            <i />
            <b />
          </div>
          <div className="path" />
        </div>
      </section>

      <div className="workspace-grid">
        <section className="panel create-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">01 · RESEARCH & WRITE</p>
              <h2>Plan the next episode</h2>
            </div>
            <span className="step-number">01</span>
          </div>
          <form onSubmit={search}>
            <label htmlFor="episode-idea">
              Episode idea <span>optional</span>
            </label>
            <input
              id="episode-idea"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="A lost calf returns before the monsoon"
              maxLength={200}
            />
            <div className="form-row">
              <div>
                <label htmlFor="language">Script language</label>
                <select
                  id="language"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as "te" | "en")}
                >
                  <option value="te">Telugu</option>
                  <option value="en">English</option>
                </select>
              </div>
              <div>
                <label htmlFor="privacy">Upload visibility</label>
                <select id="privacy" value={privacy} onChange={(e) => setPrivacy(e.target.value)}>
                  <option value="private">Private (recommended)</option>
                  <option value="unlisted">Unlisted</option>
                  <option value="public">Public</option>
                </select>
              </div>
            </div>
            <label htmlFor="audience">YouTube audience declaration</label>
            <select id="audience" value={audience} onChange={(e) => setAudience(e.target.value)}>
              <option value="">Choose before generation</option>
              <option value="yes">Made for kids</option>
              <option value="no">Not made for kids</option>
            </select>
            <button className="primary-button" type="submit" disabled={busy !== ""}>
              {busy === "research" ? "Searching YouTube…" : "Find recent niche videos"}
              <span>↗</span>
            </button>
          </form>
          {research.length > 0 && (
            <div className="research-results">
              <div className="section-title">
                <h3>Recent research</h3>
                <span>Top {Math.min(3, research.length)} guide the story</span>
              </div>
              {research.slice(0, 5).map((item) => (
                <a
                  className="research-item"
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  key={item.url}
                >
                  {item.thumbnail_url && <img src={item.thumbnail_url} alt="" />}
                  <span>
                    <b>{item.title}</b>
                    <small>
                      {item.channel_title ?? "YouTube"} ·{" "}
                      {(item.views_per_day ?? 0).toLocaleString()} estimated views/day
                    </small>
                  </span>
                  <span>↗</span>
                </a>
              ))}
              <button
                className="primary-button generate-button"
                type="button"
                onClick={() => void generate()}
                disabled={Boolean(busy) || !audience}
              >
                {busy === "generate" ? "Creating and rendering…" : "Generate this episode"}
                <span>✦</span>
              </button>
              {!audience && (
                <p className="field-hint">
                  Choose the audience declaration before generating a video.
                </p>
              )}
            </div>
          )}
          <p className="fine-print">
            Research titles and stats are used only to understand broad audience interests. Original
            stories are generated; source videos are never reused.
          </p>
        </section>

        <section className="panel jobs-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">02 · REVIEW & APPROVE</p>
              <h2>Your video jobs</h2>
            </div>
            <span className="count-badge">{jobs.length}</span>
          </div>
          {jobs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">◌</div>
              <h3>Your story queue is clear</h3>
              <p>Search the fixed channel niche to build the first episode draft.</p>
              <button
                className="text-button"
                onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
              >
                Start with research ↑
              </button>
            </div>
          ) : (
            <div className="job-list">
              {jobs.map((job) => (
                <button
                  className={`job-row ${selected?.id === job.id ? "selected" : ""}`}
                  onClick={() => setSelectedId(job.id)}
                  key={job.id}
                >
                  <span className={`status-dot status-${job.status}`} />
                  <span className="job-row-copy">
                    <b>{job.title}</b>
                    <small>
                      Episode {job.story?.episode_number ?? 1} ·{" "}
                      {job.language === "te" ? "Telugu" : "English"}
                    </small>
                  </span>
                  <span className="status-label">{job.status.replaceAll("_", " ")}</span>
                </button>
              ))}
            </div>
          )}
          {selected && (
            <div className="selected-job">
              <div className="section-title">
                <h3>{selected.title}</h3>
                <span className={`status-chip status-${selected.status}`}>
                  {selected.status.replaceAll("_", " ")}
                </span>
              </div>
              {selected.error && <div className="notice error">{selected.error}</div>}
              {selected.preview_path && (
                <PreviewVideo
                  jobId={selected.id}
                  previewPath={selected.preview_path}
                  token={token}
                />
              )}
              {selected.story && (
                <div className="story-details">
                  <p>{selected.story.synopsis}</p>
                  {selected.story.continuity_bridge && (
                    <div className="story-note">
                      <span>THIS EPISODE CONTINUES</span>
                      <p>{selected.story.continuity_bridge}</p>
                    </div>
                  )}
                  {selected.story.next_episode_hook && (
                    <div className="story-note hook-note">
                      <span>COMING NEXT</span>
                      <p>{selected.story.next_episode_hook}</p>
                    </div>
                  )}
                  <details>
                    <summary>Read full narration and scenes</summary>
                    <pre>{selected.story.script}</pre>
                    {selected.story.scenes.map((scene) => (
                      <p className="scene-line" key={scene.scene_number}>
                        <b>Scene {scene.scene_number}</b> · {scene.visual_prompt}
                      </p>
                    ))}
                  </details>
                  {selected.story.series_bible && (
                    <details>
                      <summary>Series bible</summary>
                      <p>{selected.story.series_bible.setting}</p>
                      <ul>
                        {(selected.story.series_bible.characters ?? []).map((character) => (
                          <li key={character.name}>
                            <b>{character.name}</b> — {character.description}
                          </li>
                        ))}
                      </ul>
                      <p>
                        Open threads:{" "}
                        {(selected.story.series_bible.unresolved_threads ?? []).join(" · ") ||
                          "None"}
                      </p>
                    </details>
                  )}
                  {selected.story.trend_insights && (
                    <details>
                      <summary>Trend insights used</summary>
                      <p>Themes: {(selected.story.trend_insights.themes ?? []).join(" · ")}</p>
                      <p>
                        Audience hooks:{" "}
                        {(selected.story.trend_insights.audience_hooks ?? []).join(" · ")}
                      </p>
                    </details>
                  )}
                  {selected.story.quality_report && (
                    <div
                      className={`quality-note ${selected.story.quality_report.passed ? "quality-pass" : "quality-warn"}`}
                    >
                      <b>
                        {selected.story.quality_report.passed
                          ? "✓ Draft structure checks passed"
                          : "! Draft needs review"}
                      </b>
                      {(selected.story.quality_report.warnings ?? []).map((warning) => (
                        <p key={warning}>{warning}</p>
                      ))}
                    </div>
                  )}
                  {selected.status === "awaiting_approval" && (
                    <div className="review-actions">
                      <label htmlFor="revision">Ask for a change</label>
                      <textarea
                        id="revision"
                        value={revision}
                        onChange={(e) => setRevision(e.target.value)}
                        placeholder="Make the ending more hopeful and keep Meena's character consistent…"
                        maxLength={2000}
                      />
                      <button
                        className="secondary-button"
                        onClick={() => void revise()}
                        disabled={Boolean(busy) || revision.trim().length < 3}
                      >
                        {busy === "revision" ? "Revising…" : "Regenerate preview"}
                      </button>
                      <div className="decision-buttons">
                        <button
                          className="reject-button"
                          onClick={() => void review("rejected")}
                          disabled={Boolean(busy)}
                        >
                          Reject
                        </button>
                        <button
                          className="approve-button"
                          onClick={() => void review("approved")}
                          disabled={Boolean(busy)}
                        >
                          {busy === "approved" ? "Approving…" : "Approve & upload"}
                        </button>
                      </div>
                      <p className="fine-print">
                        Approval starts the YouTube upload. Visibility: {selected.upload_privacy}.
                        This project will not upload a rejected video.
                      </p>
                    </div>
                  )}
                  {selected.status === "approved" && (
                    <button
                      className="secondary-button"
                      onClick={() => void retryUpload()}
                      disabled={Boolean(busy)}
                    >
                      {busy === "upload" ? "Uploading…" : "Retry approved upload"}
                    </button>
                  )}
                  {selected.status === "uploaded" && selected.youtube_video_id && (
                    <a
                      className="uploaded-link"
                      href={`https://youtube.com/watch?v=${selected.youtube_video_id}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Watch on YouTube ↗
                    </a>
                  )}
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      <footer className="footer">
        <span>Made for stories worth passing down.</span>
        <span>Trend informed · Human reviewed · Approval gated</span>
      </footer>
      {error && (
        <div className="toast toast-error" role="alert">
          {error}
          <button onClick={() => setError("")}>×</button>
        </div>
      )}
      {message && (
        <div className="toast" role="status">
          {message}
          <button onClick={() => setMessage("")}>×</button>
        </div>
      )}
      <details className="connection-panel">
        <summary>API connection</summary>
        <label htmlFor="api-token">
          Bearer token (only needed if API_AUTH_TOKEN is configured)
        </label>
        <div>
          <input
            id="api-token"
            type="password"
            autoComplete="off"
            value={tokenDraft}
            onChange={(e) => setTokenDraft(e.target.value)}
            placeholder="Enter local API token"
          />
          <button className="secondary-button" onClick={saveToken}>
            Save in this browser
          </button>
        </div>
      </details>
    </main>
  );
}
