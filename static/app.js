const missions = {
  download: {
    title: "Baixar do YouTube",
    hint: "Cole o link. O arquivo fica disponível para download quando o job terminar.",
  },
  both: {
    title: "Baixar e transcrever",
    hint: "Baixa em MP3 e manda o áudio para a IA em seguida.",
  },
  transcribe: {
    title: "Transcrever arquivos",
    hint: "Envie áudio ou vídeo. Dá para mandar vários de uma vez.",
  },
  metadata: {
    title: "Título e descrição",
    hint: "Suba um .txt de transcrição já pronta.",
  },
};

const state = { mission: "download", timer: null };

const $ = (id) => document.getElementById(id);

function show(id, on) {
  $(id).classList.toggle("hidden", !on);
}

function errorDetail(body) {
  if (!body) return "Erro inesperado.";
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map((item) => item.msg || item).join(" ");
  return "Erro inesperado.";
}

function banner(text, id = "app-banner") {
  const node = $(id);
  if (!node) return;
  node.textContent = text || "";
  node.classList.toggle("on", Boolean(text));
}

function renderMissions() {
  $("rail").innerHTML = Object.entries(missions).map(([id, item]) => `
    <button class="mission ${state.mission === id ? "active" : ""}" data-id="${id}">
      ${item.title}
      <small>${item.hint}</small>
    </button>
  `).join("");
  $("hint").textContent = missions[state.mission].hint;
  show("youtube-fields", state.mission === "download" || state.mission === "both");
  show("format-fields", state.mission === "download");
  show("file-fields", state.mission === "transcribe" || state.mission === "metadata");
  show("batch-fields", state.mission === "transcribe");
  show("translate-field", state.mission !== "download" && state.mission !== "metadata");
  $("files").accept = state.mission === "metadata"
    ? ".txt"
    : ".mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm,.ogg,.flac";
  $("files").multiple = state.mission === "transcribe";
}

async function readStatus() {
  const res = await fetch("/api/status");
  return res.json();
}

function paintResults(job) {
  $("stage-label").textContent = job.stage || "—";
  $("percent-label").textContent = `${job.percent || 0}%`;
  $("bar-fill").style.width = `${job.percent || 0}%`;
  $("results").innerHTML = (job.results || []).map((file) => `
    <a class="file" href="${file.url}" download>
      <div>
        <strong>${file.name}</strong>
        <div><span>${file.folder}</span></div>
      </div>
      <span>baixar</span>
    </a>
  `).join("");
}

function watch(id) {
  $("progress").classList.add("on");
  clearInterval(state.timer);
  state.timer = setInterval(async () => {
    const res = await fetch(`/api/jobs/${id}`);
    const job = await res.json();
    paintResults(job);
    if (job.status === "done" || job.status === "error") {
      clearInterval(state.timer);
      if (job.error) banner(job.error);
    }
  }, 900);
}

async function submitJob(event) {
  event.preventDefault();
  banner("");
  $("results").innerHTML = "";
  const data = new FormData();
  let url = "/api/download";

  if (state.mission === "download" || state.mission === "both") {
    data.set("url", $("url").value.trim());
    data.set("media_format", state.mission === "both" ? "mp3" : $("format").value);
    data.set("transcribe_after", state.mission === "both" ? "true" : "false");
    data.set("translate", $("translate").checked ? "true" : "false");
  } else if (state.mission === "transcribe") {
    url = "/api/transcribe";
    data.set("translate", $("translate").checked ? "true" : "false");
    data.set("workers", $("workers").value);
    for (const file of $("files").files) data.append("files", file);
    if (!$("files").files.length) return banner("Selecione pelo menos um arquivo.");
  } else {
    url = "/api/metadata";
    for (const file of $("files").files) data.append("files", file);
    if (!$("files").files.length) return banner("Selecione uma transcrição .txt.");
  }

  $("go").disabled = true;
  try {
    const res = await fetch(url, { method: "POST", body: data });
    const job = await res.json();
    if (!res.ok) throw new Error(errorDetail(job));
    paintResults(job);
    watch(job.id);
  } catch (err) {
    banner(err.message);
  } finally {
    $("go").disabled = false;
  }
}

async function login(event) {
  event.preventDefault();
  banner("");
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: $("password").value }),
  });
  const body = await res.json();
  if (!res.ok) return banner(errorDetail(body), "login-banner");
  location.href = "/";
}

async function boot() {
  const status = await readStatus();
  const path = location.pathname;
  if (status.authRequired && !status.authenticated) {
    show("app", false);
    show("login", true);
    if (path === "/" ) location.replace("/login");
    return;
  }
  if (path === "/login" && (!status.authRequired || status.authenticated)) {
    location.replace("/");
    return;
  }
  show("login", false);
  show("app", true);
  if (!status.authRequired) $("logout").classList.add("hidden");
  if (!status.hasOpenAI) {
    $("openai-warn").classList.remove("hidden");
  }
  renderMissions();
}

document.addEventListener("click", (event) => {
  const button = event.target.closest(".mission");
  if (!button) return;
  state.mission = button.dataset.id;
  renderMissions();
});

$("form").addEventListener("submit", submitJob);
$("login-form").addEventListener("submit", login);
$("logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  location.href = "/login";
});

boot();
