/*
 * Embeddable support chat. Add to any website:
 *   <script src="https://YOUR-SERVER/widget.js" data-title="Help" data-color="#6B3E26" defer></script>
 * Optional: data-greeting="Hi! Ask me about orders, shipping or returns."
 */
(function () {
  var script = document.currentScript;
  var api = new URL(script.src).origin;
  var color = script.dataset.color || "#2563EB";
  var title = script.dataset.title || "Support";
  var greeting = script.dataset.greeting || "Hi! How can I help you today?";
  var storeKey = "supportbot:" + api;
  var state = { id: null, history: [] };
  try { state = JSON.parse(sessionStorage.getItem(storeKey)) || state; } catch (e) {}

  var host = document.createElement("div");
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });  // isolates our CSS from the host site
  root.innerHTML =
    '<style>' +
    ':host{all:initial}*{box-sizing:border-box;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}' +
    '.btn{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border-radius:50%;border:0;cursor:pointer;' +
    'background:' + color + ';color:#fff;font-size:26px;box-shadow:0 6px 20px rgba(0,0,0,.25);z-index:2147483646}' +
    '.panel{position:fixed;right:20px;bottom:88px;width:min(370px,calc(100vw - 32px));height:min(540px,calc(100vh - 120px));' +
    'background:#fff;border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.25);display:none;flex-direction:column;overflow:hidden;z-index:2147483647}' +
    '.panel.open{display:flex}.head{background:' + color + ';color:#fff;padding:14px 16px;font-weight:600;display:flex;justify-content:space-between}' +
    '.head button{background:none;border:0;color:#fff;font-size:20px;cursor:pointer}' +
    '.log{flex:1;overflow-y:auto;padding:14px;background:#F7F7F8;display:flex;flex-direction:column;gap:8px}' +
    '.msg{max-width:85%;padding:9px 12px;border-radius:12px;font-size:14px;line-height:1.4;white-space:pre-wrap;word-wrap:break-word}' +
    '.bot{background:#fff;color:#111;border:1px solid #E5E7EB;align-self:flex-start}.me{background:' + color + ';color:#fff;align-self:flex-end}' +
    '.src{font-size:11px;color:#6B7280;margin-top:6px}.typing{opacity:.6;font-style:italic}' +
    'form{display:flex;border-top:1px solid #E5E7EB}input{flex:1;border:0;padding:14px;font-size:14px;outline:none;color:#111;background:#fff}' +
    'form button{border:0;background:none;color:' + color + ';font-weight:600;padding:0 16px;cursor:pointer}' +
    '.mail{display:flex;gap:6px;margin-top:8px}.mail input{border:1px solid #D1D5DB;border-radius:8px;padding:7px;font-size:13px}' +
    '.mail button{border:0;border-radius:8px;background:' + color + ';color:#fff;padding:0 10px;cursor:pointer}' +
    '</style>' +
    '<button class="btn" aria-label="Open chat">&#128172;</button>' +
    '<div class="panel" role="dialog" aria-label="' + title + '"><div class="head"><span></span><button aria-label="Close">&times;</button></div>' +
    '<div class="log" aria-live="polite"></div><form><input placeholder="Type your question..." maxlength="1000" aria-label="Message">' +
    '<button type="submit">Send</button></form></div>';

  var panel = root.querySelector(".panel"), log = root.querySelector(".log");
  var form = root.querySelector("form"), input = form.querySelector("input");
  root.querySelector(".head span").textContent = title;
  root.querySelector(".btn").onclick = function () { panel.classList.toggle("open"); input.focus(); };
  root.querySelector(".head button").onclick = function () { panel.classList.remove("open"); };

  function save() { try { sessionStorage.setItem(storeKey, JSON.stringify(state)); } catch (e) {} }

  function add(text, who, sources) {
    var div = document.createElement("div");
    div.className = "msg " + who;
    div.textContent = text;
    if (sources && sources.length) {
      var s = document.createElement("div");
      s.className = "src";
      s.textContent = "Sources: " + sources.map(function (x) { return "[" + x.n + "] " + x.title; }).join(" · ");
      div.appendChild(s);
    }
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function askEmail(parent) {
    var box = document.createElement("form");
    box.className = "mail";
    box.innerHTML = '<input type="email" required placeholder="you@email.com" aria-label="Email"><button>OK</button>';
    box.onsubmit = function (e) {
      e.preventDefault();
      post("/api/handoff", { conversation_id: state.id, email: box.querySelector("input").value })
        .then(function (r) { box.replaceWith(document.createTextNode(r.ok ? " ✓" : " " + (r.error || ""))); });
    };
    parent.appendChild(box);
    log.scrollTop = log.scrollHeight;
  }

  function post(path, body) {
    return fetch(api + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json(); });
  }

  add(greeting, "bot");
  state.history.forEach(function (t) { add(t.content, t.role === "user" ? "me" : "bot"); });

  form.onsubmit = function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    input.value = "";
    add(text, "me");
    var typing = add("...", "bot typing");
    post("/api/chat", { message: text, conversation_id: state.id, history: state.history.slice(-6) })
      .then(function (r) {
        typing.remove();
        if (r.error) { add(r.error, "bot"); return; }
        state.id = r.conversation_id;
        var msg = add(r.answer, "bot", r.sources);
        if (r.handoff) askEmail(msg);
        state.history.push({ role: "user", content: text }, { role: "assistant", content: r.answer });
        state.history = state.history.slice(-12);
        save();
      })
      .catch(function () { typing.remove(); add("Connection problem. Please try again.", "bot"); });
  };
})();
