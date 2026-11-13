(function () {
  const $ = (id) => document.getElementById(id);
  let state = { session_open: false, points_mode: "hiasan" };
  let cooling = false;

  function say(text, kind) {
    $("msg").textContent = text;
    $("msg").className = kind || "";
  }

  function updateCount() {
    $("count").textContent = `${$("body").value.length}/300`;
  }

  function showTab(name) {
    for (const b of $("tabs").querySelectorAll("button")) b.classList.toggle("active", b.dataset.tab === name);
    $("tab-kirim").hidden = name !== "kirim";
    $("tab-daftar").hidden = name !== "daftar";
    if (name === "daftar") refreshList();
  }

  async function refreshState() {
    try { state = await QnaApi.state(); } catch { return; }
    $("closed").hidden = state.session_open;
    $("form").hidden = !state.session_open;
    const upvote = state.points_mode === "upvote";
    $("tabs").hidden = !upvote;
    if (!upvote && !$("tab-daftar").hidden) showTab("kirim");
  }

  async function refreshList() {
    if (state.points_mode !== "upvote" || $("tab-daftar").hidden) return;
    let items;
    try { items = await QnaApi.publicList(); } catch { return; }
    $("empty").hidden = items.length > 0;
    $("list").innerHTML = items.map((q) => `
      <li class="qitem${q.showing ? " showing" : ""}">
        <p>${Qna.escapeHtml(q.body)}</p>
        <button type="button" class="vote${q.voted ? " on" : ""}" data-id="${Qna.escapeHtml(q.id)}"
                data-on="${q.voted ? "0" : "1"}" aria-pressed="${q.voted}">▲ <span>${q.votes}</span></button>
      </li>`).join("");
  }

  function startCooldown(seconds) {
    cooling = true;
    let left = seconds;
    const tick = () => {
      if (left <= 0) {
        cooling = false;
        $("send").disabled = false;
        $("send").textContent = "Kirim";
        return;
      }
      $("send").disabled = true;
      $("send").textContent = `Tunggu ${left} dtk`;
      left -= 1;
      setTimeout(tick, 1000);
    };
    tick();
  }

  $("body").addEventListener("input", updateCount);

  $("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (cooling) return;
    const body = $("body").value.trim();
    if (body.length < 3) return say(Qna.MESSAGES.invalid_body, "err");
    $("send").disabled = true;
    try {
      await QnaApi.submit(body);
      $("body").value = "";
      updateCount();
      say("Terkirim!", "ok");
      startCooldown(30);
    } catch (err) {
      say(err.message, "err");
      if (err.code === "cooldown") startCooldown(err.retryAfter || 30);
      else $("send").disabled = false;
      if (err.code === "session_closed") refreshState();
    }
  });

  $("tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-tab]");
    if (b) showTab(b.dataset.tab);
  });

  $("list").addEventListener("click", async (e) => {
    const btn = e.target.closest(".vote");
    if (!btn) return;
    btn.disabled = true;
    try { await QnaApi.vote(btn.dataset.id, btn.dataset.on === "1"); } catch { /* daftar dimuat ulang di bawah */ }
    refreshList();
  });

  refreshState();
  setInterval(refreshState, 10000);
  setInterval(refreshList, 5000);
})();
