(function () {
  const API = "/x/timeline.cgi";
  const PLAY = "/x/tool-file-manager.cgi?play=";
  const DAY_MS = 86400000;
  const SEGMENT_MS = 60000;

  const dayEl = document.getElementById("timelineDay");
  const emptyEl = document.getElementById("timelineEmpty");
  const dateEl = document.getElementById("timelineDate");
  const tzEl = document.getElementById("timelineTz");
  const summaryEl = document.getElementById("timelineSummary");
  const clockEl = document.getElementById("timelineClock");
  const refreshEl = document.getElementById("timelineRefresh");
  const player = document.getElementById("player");
  const playerLabel = document.getElementById("playerLabel");

  let offset = 28800;
  let segments = [];
  let selected = null;

  function pad(n) { return String(n).padStart(2, "0"); }

  function localDateKey(utcMs) {
    return new Date(utcMs + offset * 1000).toISOString().slice(0, 10);
  }

  function fmtTime(utcMs) {
    const d = new Date(utcMs + offset * 1000);
    return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
  }

  function fmtOffset(seconds) {
    const sign = seconds < 0 ? "-" : "+";
    const abs = Math.abs(seconds);
    const h = Math.floor(abs / 3600);
    const m = Math.floor((abs % 3600) / 60);
    return `UTC${sign}${pad(h)}:${pad(m)}`;
  }

  function startOfLocalDay(key) {
    const [y, m, d] = key.split("-").map(Number);
    return Date.UTC(y, m - 1, d) - offset * 1000;
  }

  function setEmpty(show) {
    emptyEl.style.display = show ? "grid" : "none";
  }

  function makeTzOptions() {
    tzEl.innerHTML = "";
    for (let hours = -12; hours <= 14; hours++) {
      const value = hours * 3600;
      const opt = document.createElement("option");
      opt.value = String(value);
      opt.textContent = fmtOffset(value);
      tzEl.appendChild(opt);
    }
    tzEl.value = String(offset);
  }

  function parseSegment(s) {
    const [y, m, d] = s.date.split("-").map(Number);
    const [hh, mm, ss] = s.time.split("-").map(Number);
    const start = Date.UTC(y, m - 1, d, hh, mm, ss);
    return { ...s, start, end: start + SEGMENT_MS };
  }

  function render() {
    dayEl.querySelectorAll(".timeline-tick, .timeline-segment, .timeline-ruler-label")
      .forEach((el) => el.remove());

    const key = dateEl.value;
    if (!key) {
      setEmpty(true);
      summaryEl.textContent = "Choose a day.";
      return;
    }

    const dayStart = startOfLocalDay(key);
    const todays = segments.filter((s) => s.start >= dayStart && s.start < dayStart + DAY_MS);

    for (let h = 0; h < 24; h += 2) {
      const tick = document.createElement("div");
      tick.className = "timeline-tick";
      tick.style.left = `${(h / 24) * 100}%`;
      dayEl.appendChild(tick);

      const label = document.createElement("span");
      label.className = "timeline-ruler-label";
      label.style.left = `${(h / 24) * 100}%`;
      label.textContent = `${pad(h)}:00`;
      dayEl.appendChild(label);
    }

    todays.forEach((s) => {
      const el = document.createElement("div");
      el.className = "timeline-segment";
      if (selected && selected.path === s.path) el.classList.add("active");
      if (s.path.endsWith("/") || Date.now() - s.start < 10 * 60000) el.classList.add("live");
      const left = Math.max(0, ((s.start - dayStart) / DAY_MS) * 100);
      const width = Math.max(0.045, (SEGMENT_MS / DAY_MS) * 100);
      el.style.left = `${left}%`;
      el.style.width = `${width}%`;
      el.title = `${fmtTime(s.start)} · ${s.path}`;
      el.addEventListener("click", () => playSegment(s));
      dayEl.appendChild(el);
    });

    setEmpty(todays.length === 0);
    const mb = todays.reduce((n, s) => n + Number(s.size || 0), 0) / 1048576;
    summaryEl.textContent = `${todays.length} segment${todays.length === 1 ? "" : "s"} · ${mb.toFixed(1)} MB`;
  }

  function playSegment(s) {
    selected = s;
    player.src = PLAY + encodeURIComponent(s.path);
    playerLabel.textContent = `${fmtTime(s.start)} · ${fmtOffset(offset)}`;
    player.play().catch(() => {});
    render();
  }

  async function setTimezone(value) {
    offset = Number(value);
    await fetch(`${API}?tz=${encodeURIComponent(String(offset))}`, { method: "POST" });
    tzEl.value = String(offset);
    const key = dateEl.value || localDateKey(Date.now());
    dateEl.value = key;
    render();
  }

  async function load() {
    summaryEl.textContent = "Loading recordings…";
    try {
      const response = await fetch(API, { cache: "no-store" });
      if (response.status === 401) {
        summaryEl.textContent = "Sign in required";
        setEmpty(true);
        window.location.href = "/login.html?next=" + encodeURIComponent("/preview.html");
        return;
      }
      const data = await response.json();
      offset = Number(data.offset || 0);
      segments = (data.segments || []).map(parseSegment);
      makeTzOptions();

      const latest = segments.reduce((a, b) => (!a || b.start > a.start ? b : a), null);
      dateEl.value = latest ? localDateKey(latest.start) : localDateKey(Date.now());
      render();
    } catch (error) {
      summaryEl.textContent = "Unable to load recordings.";
      emptyEl.textContent = error.message;
      setEmpty(true);
    }
  }

  tzEl.addEventListener("change", (e) => setTimezone(e.target.value));
  dateEl.addEventListener("change", render);
  refreshEl.addEventListener("click", load);

  setInterval(() => {
    const now = Date.now();
    const d = new Date(now + offset * 1000);
    clockEl.textContent = `now ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} ${fmtOffset(offset)}`;
  }, 1000);

  makeTzOptions();
  load();
})();
