(function () {
  const API = "/x/timeline.cgi";
  const VIDEO = "/x/video.cgi?path=";
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
  let objectUrl = "";
  let loadToken = 0;
  let scrubbing = false;
  let scrubTarget = 0;
  let suppressClickUntil = 0;
  const playhead = document.createElement("div");
  playhead.className = "timeline-playhead";
  dayEl.appendChild(playhead);

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
      el.addEventListener("click", () => {
        if (Date.now() < suppressClickUntil) return;
        playSegment(s);
      });
      dayEl.appendChild(el);
    });

    setEmpty(todays.length === 0);
    updatePlayhead();
    const mb = todays.reduce((n, s) => n + Number(s.size || 0), 0) / 1048576;
    summaryEl.textContent = `${todays.length} segment${todays.length === 1 ? "" : "s"} · ${mb.toFixed(1)} MB`;
  }

  function setPlayhead(absMs) {
    if (!selected && !absMs) { playhead.style.display = "none"; return; }
    if (!dateEl.value) { playhead.style.display = "none"; return; }
    const dayStart = startOfLocalDay(dateEl.value);
    const pct = ((absMs - dayStart) / DAY_MS) * 100;
    if (pct < 0 || pct > 100) { playhead.style.display = "none"; return; }
    playhead.style.display = "block";
    playhead.style.left = pct + "%";
  }

  function updatePlayhead() {
    if (!selected) { playhead.style.display = "none"; return; }
    setPlayhead(selected.start + (player.currentTime || 0) * 1000);
  }

  function segmentAt(absMs) {
    let previous = null;
    for (const s of segments) {
      if (absMs >= s.start && absMs < s.end) return s;
      if (s.start <= absMs) previous = s;
    }
    return previous || segments[0] || null;
  }

  function timeFromPointer(event) {
    const rect = dayEl.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    return startOfLocalDay(dateEl.value) + ratio * DAY_MS;
  }

  async function playSegment(s, offsetSec = 0, autoplay = true) {
    const token = ++loadToken;
    selected = s;
    const label = `${fmtTime(s.start)} · ${fmtOffset(offset)}`;
    playerLabel.textContent = `Loading ${s.path.split("/").slice(-2).join("/")}…`;
    render();
    try {
      const response = await fetch(VIDEO + s.path, { cache: "no-store" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const blob = await response.blob();
      if (token !== loadToken) return;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(blob);
      player.src = objectUrl;
      player.muted = true;
      playerLabel.textContent = label + " · " + (blob.size / 1048576).toFixed(1) + " MB";
      await new Promise((resolve) => {
        if (player.readyState >= 1) return resolve();
        const done = () => { player.removeEventListener("loadedmetadata", done); resolve(); };
        player.addEventListener("loadedmetadata", done);
        setTimeout(done, 3000);
      });
      if (token !== loadToken) return;
      const duration = Number.isFinite(player.duration) ? player.duration : offsetSec;
      const seek = Math.max(0, Math.min(offsetSec, duration || offsetSec));
      if (seek > 0) player.currentTime = seek;
      updatePlayhead();
      if (autoplay) await player.play().catch(() => {});
    } catch (error) {
      if (token === loadToken) {
        playerLabel.textContent = "Unable to load " + s.path.split("/").pop() + ": " + error.message;
      }
    }
  }

  async function playNext() {
    if (!selected || !segments.length) return;
    const ordered = [...segments].sort((a, b) => a.start - b.start);
    let index = ordered.findIndex((s) => s.path === selected.path);
    if (index < 0) index = ordered.findIndex((s) => s.start === selected.start);
    const next = ordered[index + 1];
    if (!next) return;
    const nextKey = localDateKey(next.start);
    if (dateEl.value !== nextKey) {
      dateEl.value = nextKey;
      render();
    }
    await playSegment(next, 0, true);
  }

  dayEl.addEventListener("pointerdown", (event) => {
    if (!dateEl.value || !segments.length) return;
    scrubbing = true;
    scrubTarget = timeFromPointer(event);
    try { dayEl.setPointerCapture(event.pointerId); } catch (_) {}
    setPlayhead(scrubTarget);
    event.preventDefault();
  });

  dayEl.addEventListener("pointermove", (event) => {
    if (!scrubbing) return;
    scrubTarget = timeFromPointer(event);
    setPlayhead(scrubTarget);
  });

  dayEl.addEventListener("pointerup", (event) => {
    if (!scrubbing) return;
    scrubbing = false;
    const target = timeFromPointer(event);
    const s = segmentAt(target);
    if (!s) return;
    suppressClickUntil = Date.now() + 400;
    const seek = Math.max(0, (target - s.start) / 1000);
    if (selected && selected.path === s.path && player.src && Number.isFinite(player.duration)) {
      player.currentTime = Math.min(seek, player.duration);
      player.play().catch(() => {});
      updatePlayhead();
      return;
    }
    playSegment(s, seek, true);
  });

  player.addEventListener("timeupdate", updatePlayhead);
  player.addEventListener("loadedmetadata", updatePlayhead);
  player.addEventListener("ended", playNext);

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
      segments = (data.segments || []).map(parseSegment).sort((a, b) => a.start - b.start);
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
