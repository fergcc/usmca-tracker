// Vercel serverless function: lets any visitor trigger a real, on-demand run
// of the tracker instead of waiting for the 6h cron. Rate-limited statelessly
// by checking the workflow's own most recent run via the GitHub API — no
// KV/DB needed. The GitHub token lives only in this server-side env var and
// is never echoed back to the client.

const REPO = "fergcc/usmca-tracker";
const WORKFLOW = "update-dashboard.yml";
const COOLDOWN_SECONDS = 600;

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "method_not_allowed" });
    return;
  }

  const token = process.env.GH_DISPATCH_TOKEN;
  if (!token) {
    res.status(500).json({ error: "server_misconfigured" });
    return;
  }

  const ghHeaders = {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  try {
    const runsRes = await fetch(
      `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?per_page=1`,
      { headers: ghHeaders }
    );
    if (runsRes.ok) {
      const runsBody = await runsRes.json();
      const last = runsBody.workflow_runs && runsBody.workflow_runs[0];
      if (last) {
        const elapsed = (Date.now() - new Date(last.created_at).getTime()) / 1000;
        if (elapsed < COOLDOWN_SECONDS) {
          res.status(429).json({
            error: "cooldown",
            retryAfterSeconds: Math.ceil(COOLDOWN_SECONDS - elapsed),
          });
          return;
        }
      }
    }

    const dispatchRes = await fetch(
      `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: ghHeaders,
        body: JSON.stringify({ ref: "main" }),
      }
    );

    if (dispatchRes.status === 204) {
      res.status(202).json({ status: "queued" });
    } else {
      const body = await dispatchRes.text();
      console.error("dispatch failed", dispatchRes.status, body);
      res.status(502).json({ error: "dispatch_failed" });
    }
  } catch {
    res.status(500).json({ error: "unexpected_error" });
  }
}
