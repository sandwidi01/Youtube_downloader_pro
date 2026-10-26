const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const res = await fetch(path, body && {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Erreur serveur.");
  return data;
}

function showError(msg) {
  $("error").textContent = msg || "";
  $("error").hidden = !msg;
}

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("");
  $("result").hidden = true;
  $("go").disabled = true;
  $("go").textContent = "Analyse…";
  try {
    const info = await api("/api/info", { url: $("url").value });
    $("thumb").src = info.thumbnail || "";
    $("title").textContent = info.title || "";
    $("uploader").textContent = info.uploader || "";
    const heights = info.heights.length ? info.heights : [720];
    $("quality").innerHTML = heights.slice().reverse()
      .map((h) => `<option value="${h}">${h}p</option>`).join("");
    $("bar").hidden = true;
    $("save").hidden = true;
    $("result").hidden = false;
  } catch (err) {
    showError(err.message);
  } finally {
    $("go").disabled = false;
    $("go").textContent = "Analyser";
  }
});

$("format").addEventListener("change", () => {
  $("quality").hidden = $("format").value === "mp3";
});

$("dl").addEventListener("click", async () => {
  showError("");
  $("dl").disabled = true;
  $("save").hidden = true;
  $("bar").hidden = false;
  $("fill").style.width = "0%";
  try {
    const { job_id } = await api("/api/download", {
      url: $("url").value,
      format: $("format").value,
      quality: Number($("quality").value) || 720,
    });
    while (true) {
      await new Promise((r) => setTimeout(r, 1000));
      const job = await api(`/api/jobs/${job_id}`);
      $("fill").style.width = `${job.progress || 0}%`;
      if (job.status === "error") throw new Error(job.error);
      if (job.status === "done") {
        $("save").href = `/api/file/${job_id}`;
        $("save").hidden = false;
        $("save").click();
        break;
      }
    }
  } catch (err) {
    showError(err.message);
    $("bar").hidden = true;
  } finally {
    $("dl").disabled = false;
  }
});
