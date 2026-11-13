(function () {
  const $ = (id) => document.getElementById(id);
  const pages = window.QNA_CONFIG.pages;
  const ACTIONS = {
    masuk: [["approve", "Setujui"], ["reject", "Tolak"]],
    disetujui: [["show", "Tampilkan"], ["reject", "Tolak"]],
    tampil: [["done", "Selesai"]],
    selesai: [["show", "Tampilkan lagi"]],
    ditolak: [["approve", "Setujui"]],
  };
  let data = { settings: {}, questions: [] };
  let loading = false;
  let again = false;
  let started = false;

  function toast(text) {
    const t = $("toast");
    t.textContent = text;
    t.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { t.hidden = true; }, 4000);
  }

  function fail(err) {
    if (err.code === "forbidden") {
      if (QnaApi.admin.needsLogin) return showLogin();
      window.location.href = "/login";
      return;
    }
    toast(err.message);
  }

  // Satu pemuatan dalam satu waktu; sinyal yang datang di tengahnya dilipat
  // jadi satu pemuatan susulan, supaya rentetan event tidak membanjiri server.
  async function load() {
    if (loading) { again = true; return; }
    loading = true;
    try {
      data = await QnaApi.admin.list();
      $("conn").classList.add("on");
      render();
    } catch (err) {
      $("conn").classList.remove("on");
      fail(err);
    } finally {
      loading = false;
      if (again) { again = false; load(); }
    }
  }

  function item(q) {
    const votes = data.settings.points_mode === "upvote" ? `<span class="muted">▲ ${q.votes}</span>` : "";
    const buttons = (ACTIONS[q.status] || []).map(([act, label]) =>
      `<button type="button" data-id="${Qna.escapeHtml(q.id)}" data-act="${act}"${act === "show" ? ' class="primary"' : ""}>${label}</button>`,
    ).join("");
    return `<li class="qitem"><p>${Qna.escapeHtml(q.body)}</p><div class="actions">${votes}${buttons}</div></li>`;
  }

  function render() {
    const s = data.settings;
    $("session").textContent = s.session_open ? "Tutup sesi" : "Buka sesi";
    $("session").classList.toggle("primary", !s.session_open);
    $("mode").value = s.points_mode;
    $("mode").disabled = !!s.session_open;
    $("tts").value = s.tts_engine;

    const groups = { masuk: [], disetujui: [], tampil: [], selesai: [], ditolak: [] };
    for (const q of data.questions) (groups[q.status] || []).push(q);
    const oldest = (a, b) => a.created_at.localeCompare(b.created_at);
    groups.masuk.sort(oldest);
    groups.disetujui.sort($("sort").value === "votes" ? (a, b) => b.votes - a.votes || oldest(a, b) : oldest);
    groups.selesai.sort((a, b) => (b.shown_at || "").localeCompare(a.shown_at || ""));
    for (const [status, list] of Object.entries(groups)) {
      $(`col-${status}`).innerHTML = list.map(item).join("");
      const counter = $(`n-${status}`);
      if (counter) counter.textContent = list.length;
    }
  }

  async function run(promise) {
    try { await promise; } catch (err) { fail(err); }
    load();
  }

  document.body.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    btn.disabled = true;
    const opts = btn.dataset.act === "show" ? showOptions() : undefined;
    run(QnaApi.admin.act(btn.dataset.id, btn.dataset.act, opts));
  });
  $("session").onclick = () => run(QnaApi.admin.settings({ session_open: !data.settings.session_open }));
  $("mode").onchange = () => run(QnaApi.admin.settings({ points_mode: $("mode").value }));
  $("tts").onchange = () => run(QnaApi.admin.settings({ tts_engine: $("tts").value }));
  $("sort").onchange = render;

  // Pilihan di toolbar berlaku untuk setiap klik "Tampilkan": admin bisa
  // menggantinya sebelum menampilkan pertanyaan berikutnya.
  $("intro").insertAdjacentHTML("beforeend",
    Qna.INTROS.map((t) => `<option value="${Qna.escapeHtml(t)}">${Qna.escapeHtml(t)}</option>`).join("")
    + '<option value="__custom">Tulis sendiri…</option>');
  $("intro").onchange = () => {
    $("introCustom").hidden = $("intro").value !== "__custom";
    if (!$("introCustom").hidden) $("introCustom").focus();
  };

  function showOptions() {
    const choice = $("intro").value;
    const custom = $("introCustom").value.trim();
    let intro = choice;
    if (choice === "__random" || (choice === "__custom" && !custom)) intro = Qna.pickRandom(Qna.INTROS);
    else if (choice === "__custom") intro = custom;
    const sfx = $("sfx").value === "__random" ? Qna.pickRandom(Qna.SFX) : $("sfx").value;
    return { intro, sfx };
  }
  $("hide").onclick = () => run(QnaApi.admin.screen("hide"));
  $("replay").onclick = () => run(QnaApi.admin.screen("replay"));
  $("linkOverlay").href = `${pages.display}?mode=overlay`;
  $("linkFull").href = `${pages.display}?mode=full`;

  function showLogin() {
    $("app").hidden = true;
    $("login").hidden = false;
    $("pin").focus();
  }

  function start() {
    $("login").hidden = true;
    $("app").hidden = false;
    if (started) return load();
    started = true;
    QnaApi.subscribe(() => load(), (on) => $("conn").classList.toggle("on", on));
  }

  $("login").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await QnaApi.admin.login($("pin").value);
      $("pin").value = "";
      start();
    } catch (err) {
      $("loginMsg").textContent = err.code === "forbidden" ? "PIN salah." : err.message;
    }
  });

  if (QnaApi.admin.needsLogin && !QnaApi.admin.hasPin()) showLogin();
  else start();
})();
