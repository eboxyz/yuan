/* Setup page UI. Question wording comes from the intake schema bundled in
   skill-bundle.js (title, description, x-labels, x-help, x-default), so the page
   and the generated tracker say the same thing. Answers autosave to this
   browser's localStorage; nothing is sent anywhere. */
(function () {
  "use strict";
  const B = window.JST_BUNDLE, L = window.JSTLib;
  const S = (path) => L.node(B.schema, path);
  const STORE = "jst-intake-v1";
  let resumeFile = null;

  // ---------- state ----------
  const defaults = {
    job_finder: S("basics.job_finder")["x-default"], drafting: S("basics.drafting")["x-default"],
    sources: S("job_finder.sources")["x-default"], run_size: S("job_finder.run_size")["x-default"],
    pickiness: S("job_finder.pickiness")["x-default"], drafts: S("job_finder.drafts")["x-default"],
    daily_run: S("job_finder.daily_run")["x-default"], daily_run_on: true, stories: {},
  };
  let answers = load();
  function load() {
    try { return Object.assign({}, defaults, JSON.parse(localStorage.getItem(STORE) || "{}")); }
    catch (e) { return Object.assign({}, defaults); }
  }
  let saveTimer;
  function save() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      const el = document.getElementById("saved");
      try { localStorage.setItem(STORE, JSON.stringify(answers)); el.textContent = "Saved in this browser"; }
      catch (e) { el.textContent = "Couldn't save in this browser. Download your answers before you leave."; }
    }, 250);
  }
  function set(key, value) { answers[key] = value; save(); }

  // ---------- tiny DOM helper ----------
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "text") el.textContent = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
    return el;
  }
  let uid = 0;
  const id = (k) => `f-${k}-${++uid}`;

  // ---------- fields ----------
  function wording(f) { const n = f.path ? S(f.path) : {}; return { title: f.title || n.title, help: f.help || n.description, labels: n["x-labels"] || {}, tips: n["x-help"] || {}, n }; }
  function labelled(f, control, cid) {
    const w = wording(f), hid = cid + "-help", eid = cid + "-err";
    control.setAttribute("aria-describedby", [w.help ? hid : null, eid].filter(Boolean).join(" "));
    return h("div", { class: "field" },
      h("label", { for: cid }, w.title, f.required ? h("span", { class: "req", "aria-hidden": "true" }, " *") : null),
      w.help ? h("span", { class: "help", id: hid }, w.help) : null,
      control, h("p", { class: "error", id: eid, "data-err": f.key }));
  }
  function textField(f, multiline) {
    const cid = id(f.key), n = f.path ? S(f.path) : {};
    const max = n.maxLength || (n.items && n.items.maxLength ? null : null);
    const attrs = { id: cid, name: f.key, placeholder: f.placeholder, maxlength: multiline ? (f.list ? null : max) : max,
      required: f.required, rows: f.rows, autocomplete: f.autocomplete || "off",
      oninput: (e) => set(f.key, e.target.value), disabled: f.disabled && f.disabled() };
    const el = multiline ? h("textarea", attrs) : h("input", Object.assign({ type: "text" }, attrs));
    el.value = answers[f.key] || "";
    return labelled(f, el, cid);
  }
  function group(f, kind) {
    const w = wording(f), name = id(f.key), cur = answers[f.key], disabled = f.disabled && f.disabled();
    const opts = (w.n.enum || w.n.items.enum).map((v) => {
      const checked = kind === "checkbox" ? (cur || []).includes(v) : cur === v;
      const input = h("input", { type: kind, name, value: v, checked, disabled,
        onchange: (e) => {
          if (kind === "checkbox") { const s = new Set(answers[f.key] || []); e.target.checked ? s.add(v) : s.delete(v); set(f.key, (w.n.items.enum).filter((x) => s.has(x))); }
          else { set(f.key, v); clear.hidden = false; applyConditions(); }
        } });
      return h("label", { class: "opt" }, input, h("span", null, w.labels[v] || v, w.tips[v] ? h("small", null, w.tips[v]) : null));
    });
    const clear = h("button", { type: "button", class: "btn ghost", hidden: kind === "checkbox" || !cur || f.required,
      onclick: () => { set(f.key, undefined); render(); } }, "Clear this answer");
    const hid = name + "-help";
    return h("fieldset", { class: "field", "aria-describedby": w.help ? hid : null },
      h("legend", null, w.title), w.help ? h("span", { class: "help", id: hid }, w.help) : null,
      f.note && disabled ? h("p", { class: "help" }, f.note) : null,
      h("div", { class: "opts" }, opts), kind === "radio" ? clear : null, h("p", { class: "error", "data-err": f.key }));
  }
  function toggle(f) {
    const w = wording(f), disabled = f.disabled && f.disabled();
    const input = h("input", { type: "checkbox", role: "switch", checked: answers[f.key] !== false && !disabled, disabled,
      onchange: (e) => { set(f.key, e.target.checked); applyConditions(); } });
    return h("div", { class: "field" }, h("label", { class: "switch" }, input, h("span", { class: "track", "aria-hidden": "true" }),
      h("span", { class: "text" }, h("strong", null, w.title), w.help ? h("span", { class: "help" }, w.help) : null,
        disabled && f.note ? h("span", { class: "help" }, f.note) : null)));
  }
  function select(f) {
    const w = wording(f), cid = id(f.key);
    const el = h("select", { id: cid, onchange: (e) => set(f.key, e.target.value || undefined) },
      h("option", { value: "" }, "Choose…"), w.n.enum.map((v) => h("option", { value: v, selected: answers[f.key] === v }, w.labels[v] || v)));
    return labelled(f, el, cid);
  }
  function dateField(f) {
    const cid = id(f.key);
    const el = h("input", { type: "date", id: cid, onchange: (e) => set(f.key, e.target.value || undefined) });
    el.value = answers[f.key] || "";
    return labelled(f, el, cid);
  }
  function rank(f) {
    const w = wording(f), max = w.n.maxItems, name = id(f.key);
    const cur = () => answers[f.key] || [];
    const buttons = w.n.items.enum.map((v) => {
      const pos = cur().indexOf(v);
      return h("button", { type: "button", "aria-pressed": pos >= 0 ? "true" : "false",
        "aria-label": `${w.labels[v]}${pos >= 0 ? `, ranked ${pos + 1}` : ""}`,
        onclick: () => {
          const list = cur().slice(), i = list.indexOf(v);
          if (i >= 0) list.splice(i, 1); else if (list.length < max) list.push(v); else return;
          set(f.key, list); render(`[data-rank="${v}"]`);
        }, "data-rank": v }, h("span", { class: "num", "aria-hidden": "true" }, pos >= 0 ? String(pos + 1) : "·"), w.labels[v]);
    });
    return h("fieldset", { class: "field" }, h("legend", null, w.title), h("span", { class: "help" }, w.help),
      h("span", { class: "help" }, `Choose up to ${max} in order: the first one you choose is #1. Choose again to remove.`),
      h("div", { class: "rank", role: "group", "aria-label": w.title }, buttons), h("p", { class: "error", "data-err": f.key }));
  }
  function timeField(f) {
    const cid = id(f.key), on = answers.daily_run_on !== false;
    const el = h("input", { type: "time", id: cid, disabled: !on, onchange: (e) => set("daily_run", e.target.value || "08:00") });
    el.value = answers.daily_run || "08:00";
    const sw = h("input", { type: "checkbox", role: "switch", checked: on, onchange: (e) => { set("daily_run_on", e.target.checked); el.disabled = !e.target.checked; } });
    const w = S("job_finder.daily_run");
    return h("div", { class: "field" },
      h("label", { class: "switch" }, sw, h("span", { class: "track", "aria-hidden": "true" }),
        h("span", { class: "text" }, h("strong", null, w.title), h("span", { class: "help" }, w.description))),
      h("label", { for: cid, class: "help mt-sm" }, "Time of day (24-hour)"), el, h("p", { class: "error", "data-err": "daily_run" }));
  }
  function fileField() {
    const cid = id("resume");
    const el = h("input", { type: "file", id: cid, accept: ".pdf,.doc,.docx,.md,.txt,.rtf,.odt",
      onchange: (e) => {
        const file = e.target.files[0], err = document.querySelector('[data-err="resume"]');
        if (file && file.size > 10 * 1024 * 1024) { e.target.value = ""; resumeFile = null; err.textContent = "That file is over 10 MB. Try a PDF export of it."; return; }
        resumeFile = file || null; err.textContent = ""; render();
      } });
    return labelled({ key: "resume", title: "Your resume",
      help: "PDF, Word, Markdown or text, up to 10 MB. It goes into your download and nowhere else. It isn't saved in this browser, so add it again if you reload the page." }, el, cid);
  }
  let conds = [];  // [{el, f}] for fields that appear only when relevant (f.showIf)
  function applyConditions() { for (const { el, f } of conds) el.hidden = !f.showIf(); }
  const FIELD = { text: (f) => textField(f, false), textarea: (f) => textField(f, true), list: (f) => textField(Object.assign({ list: true, rows: 4 }, f), true),
    checks: (f) => group(f, "checkbox"), radios: (f) => group(f, "radio"), select, toggle, date: dateField, rank, time: timeField, file: fileField };

  // ---------- steps ----------
  const finderOff = () => answers.job_finder === false;
  const draftingOff = () => finderOff() || answers.drafting === false;
  const visaQuestions = () => answers.status !== "no_sponsorship_needed";
  const STEPS = [
    { id: "welcome", name: "Welcome", render: welcome },
    { id: "you", name: "You", title: "Let's start with you", fields: [
      { key: "preferred_name", path: "basics.preferred_name", type: "text", required: true, placeholder: "e.g. Priya", autocomplete: "given-name" },
      { key: "job_finder", path: "basics.job_finder", type: "toggle" },
      { key: "drafting", path: "basics.drafting", type: "toggle", showIf: () => !finderOff() } ] },
    { id: "want", name: "What you want", title: "What you want from this search",
      intro: "Start with what you want, before what you've done. Every offer is a trade, and knowing what matters most makes those choices easier. Skip anything you're unsure about; Claude will go through it with you.",
      fields: [
        { key: "priorities", path: "what_you_want.priorities", type: "rank" },
        { key: "tradeoff", path: "what_you_want.tradeoff", type: "textarea", rows: 3 },
        { key: "pay_floor", path: "what_you_want.pay_floor", type: "text", placeholder: "e.g. $120K base" },
        { key: "pay_other", path: "what_you_want.pay_other", type: "checks" },
        { key: "pay_notes", path: "what_you_want.pay_notes", type: "textarea", rows: 3 },
        { key: "balance", path: "what_you_want.balance", type: "textarea", rows: 3 },
        { key: "work_arrangements", path: "what_you_want.work_arrangements", type: "checks" },
        { key: "locations", path: "what_you_want.locations", type: "text", placeholder: "e.g. Chicago, or remote in US time zones" },
        { key: "company_size", path: "what_you_want.company_size", type: "checks" },
        { key: "company_size_why", path: "what_you_want.company_size_why", type: "textarea", rows: 2 },
        { key: "timeline", path: "what_you_want.timeline", type: "text" },
        { key: "must_haves", path: "what_you_want.must_haves", type: "list" },
        { key: "dealbreakers", path: "what_you_want.dealbreakers", type: "list" } ] },
    { id: "auth", name: "Work authorization", title: "Work authorization and risk",
      intro: S("work_authorization").description,
      fields: [
        { key: "status", path: "work_authorization.status", type: "radios" },
        { key: "authorized_until", showIf: visaQuestions, path: "work_authorization.authorized_until", type: "date" },
        { key: "needs", showIf: visaQuestions, path: "work_authorization.needs", type: "checks" },
        { key: "green_card_timing", showIf: visaQuestions, path: "work_authorization.green_card_timing", type: "radios" },
        { key: "auth_notes", showIf: visaQuestions, path: "work_authorization.notes", type: "textarea", rows: 2 },
        { heading: "Risk", help: S("risk").description },
        { key: "comfort", path: "risk.comfort", type: "radios" },
        { key: "runway", path: "risk.runway", type: "select" },
        { key: "dependents", path: "risk.dependents", type: "radios" },
        { key: "layoff_impact", path: "risk.layoff_impact", type: "textarea", rows: 3 } ] },
    { id: "look", name: "Where to look", title: "Where to look", fields: [
      { key: "titles", path: "where_to_look.titles", type: "list", required: true },
      { key: "seniority", path: "where_to_look.seniority", type: "text" },
      { key: "industries_like", path: "where_to_look.industries_like", type: "list" },
      { key: "industries_avoid", path: "where_to_look.industries_avoid", type: "list" },
      { key: "companies_like", path: "where_to_look.companies_like", type: "list" },
      { key: "companies_skip", path: "where_to_look.companies_skip", type: "list" } ] },
    { id: "finder", name: "Job finder", title: "Your job finder",
      intro: "It searches public job listings and puts matches in a review queue on your dashboard. It never applies, logs in, or creates accounts for you.",
      off: finderOff,
      fields: [
        { key: "sources", path: "job_finder.sources", type: "checks" },
        { key: "run_size", path: "job_finder.run_size", type: "radios", required: true },
        { key: "pickiness", path: "job_finder.pickiness", type: "radios", required: true },
        { key: "drafts", path: "job_finder.drafts", type: "radios", required: true, disabled: draftingOff, note: "Cover-letter drafting is off (step 2)." },
        { key: "watch_companies", path: "job_finder.watch_companies", type: "list" },
        { key: "daily_run", type: "time" } ] },
    { id: "about", name: "About you", title: "About you", fields: [
      { type: "file" },
      { key: "strengths", path: "about_you.strengths", type: "textarea", rows: 4 },
      { key: "links", path: "about_you.links", type: "list", rows: 3 },
      { key: "voice_sample", path: "about_you.voice_sample", type: "textarea", rows: 6 } ] },
    { id: "stories", name: "Stories", render: stories },
    { id: "download", name: "Download", render: download },
  ];

  // ---------- rendering ----------
  let current = 0;
  function nav() {
    const ol = document.getElementById("steps"); ol.replaceChildren();
    STEPS.forEach((s, i) => ol.append(h("li", null, h("button", { type: "button", "aria-current": i === current ? "step" : null, class: i < current && !Object.keys(stepErrors(s)).length ? "done" : null,
      onclick: () => go(i) }, h("span", { class: "n", "aria-hidden": "true" }, String(i + 1)), s.name))));
  }
  function render(focusSel) {
    const s = STEPS[current], panel = document.getElementById("panel");
    panel.replaceChildren(...(s.render ? s.render() : formStep(s)));
    nav();
    const f = focusSel && panel.querySelector(focusSel);
    if (f) f.focus();
  }
  function formStep(s) {
    const out = [h("p", { class: "eyebrow" }, `Step ${current + 1} of ${STEPS.length}`), h("h2", { tabindex: "-1" }, s.title)];
    if (s.intro) out.push(h("p", { class: "lead" }, s.intro));
    if (s.off && s.off()) {
      out.push(h("div", { class: "note" }, "The job finder is off, so there's nothing to set here. ",
        h("button", { type: "button", class: "btn ghost", onclick: () => { set("job_finder", true); render(); } }, "Turn it on")));
    } else {
      conds = [];
      for (const f of s.fields) {
        const el = f.heading ? h("div", null, h("h3", null, f.heading), h("p", { class: "help" }, f.help)) : FIELD[f.type](f);
        if (f.showIf) { el.dataset.cond = f.key; el.hidden = !f.showIf(); conds.push({ el, f }); }
        out.push(el);
      }
    }
    out.push(actions());
    return out;
  }
  function actions(nextLabel) {
    return h("div", { class: "actions" },
      current > 0 ? h("button", { type: "button", class: "btn secondary", onclick: () => go(current - 1) }, "Back") : h("span"),
      current < STEPS.length - 1 ? h("button", { type: "button", class: "btn primary", onclick: next }, nextLabel || "Next") : null);
  }
  function stepErrors(s) {
    const errs = {};
    if (s.id === "you" && !(answers.preferred_name || "").trim()) errs.preferred_name = "Tell us what to call you.";
    if (s.id === "look" && !L.lines(answers.titles).length) errs.titles = "Add at least one job title to look for.";
    if (s.id === "finder" && !finderOff()) {
      if (!(answers.sources || []).length) errs.sources = "Choose at least one place to look, or turn the job finder off in step 2.";
      if (answers.daily_run_on !== false && !/^([01]?\d|2[0-3]):[0-5]\d$/.test(answers.daily_run || "")) errs.daily_run = "Choose a time, or turn the daily run off.";
    }
    return errs;
  }
  function showErrors(errs) {
    document.querySelectorAll("[data-err]").forEach((p) => {
      p.textContent = errs[p.dataset.err] || "";
      const field = p.closest(".field"), input = field && field.querySelector("input,textarea,select");
      if (input) input.setAttribute("aria-invalid", errs[p.dataset.err] ? "true" : "false");
    });
    const first = document.querySelector('[aria-invalid="true"]');
    if (first) first.focus();
  }
  function next() {
    const errs = stepErrors(STEPS[current]);
    if (Object.keys(errs).length) return showErrors(errs);
    go(current + 1);
  }
  function go(i) {
    current = Math.max(0, Math.min(STEPS.length - 1, i));
    history.replaceState(null, "", "#step=" + STEPS[current].id);
    render();
    const h2 = document.querySelector("#panel h1, #panel h2");
    if (h2) h2.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }

  function welcome() {
    return [
      h("h1", { tabindex: "-1" }, "Set up your job search tracker"),
      h("p", { class: "lead" }, "Answer some questions about what you want from your search. At the end you download one folder: your answers, your resume, and what Claude needs to build a private tracker on your computer and help you run your search from it."),
      h("h3", null, "What you get"),
      h("ul", { class: "plain" },
        h("li", null, "A dashboard of your applications, on your own computer."),
        h("li", null, "Claude as a guide: it helps you get clear on what you want, tell your experience in your own words, and checks in as things change."),
        h("li", null, "If you want it, a job finder that searches public job listings every day and drafts cover letters for you to review. It never applies for you.")),
      h("h3", null, "Before you start"),
      h("ul", { class: "plain" },
        h("li", null, "It takes about 15 to 20 minutes. Only your name and one job title are required."),
        h("li", null, "Your answers are saved in this browser as you go, so you can stop and come back."),
        h("li", null, "Have your resume handy.")),
      h("div", { class: "note seal" },
        h("strong", null, "Your answers stay with you. "),
        "This page has no accounts and no analytics, and it sends nothing anywhere. When you download, your answers and resume go into that file only. Later, on your computer, Claude reads your files using your own Claude account, and the job finder reads public job listings."),
      h("p", { class: "help" }, "Why “Yuan”? 缘 is the connection between people who are meant to meet. Written another way, 元, it's money."),
      actions("Start"),
    ];
  }

  function stories() {
    const st = S("stories"), prompts = st.items.properties.prompt["x-labels"];
    const out = [h("p", { class: "eyebrow" }, `Step ${current + 1} of ${STEPS.length}`), h("h2", { tabindex: "-1" }, "Your stories"),
      h("p", { class: "lead" }, "Answer as many as you like, in a few honest sentences. In your first session Claude asks one or two follow-up questions to help you tell them well."),
      h("div", { class: "note" }, st.description, h("br"), h("br"),
        h("em", null, "An invented example: “Two teams reported different on-time rates. I traced it to two definitions of ‘delivered’ and got both to agree on one; it's now the number the COO reports every week.”"))];
    for (const [key, label] of Object.entries(prompts)) {
      const cid = id("story-" + key);
      const ta = h("textarea", { id: cid, rows: 4, maxlength: 4000, oninput: (e) => { answers.stories = Object.assign({}, answers.stories, { [key]: e.target.value }); save(); } });
      ta.value = (answers.stories || {})[key] || "";
      const block = h("div", { class: "field story" }, h("label", { for: cid }, label));
      if (key === "other") {
        const tid = id("story-title");
        const t = h("input", { type: "text", id: tid, maxlength: 120, placeholder: "A short name for it", oninput: (e) => set("other_story_title", e.target.value) });
        t.value = answers.other_story_title || "";
        block.append(h("label", { for: tid, class: "help" }, "Give it a title"), t, h("label", { for: cid, class: "help mt-sm" }, "The story"));
      }
      block.append(ta);
      out.push(block);
    }
    out.push(actions());
    return out;
  }

  const STEP_OF = { basics: "you", what_you_want: "want", work_authorization: "auth", risk: "auth", where_to_look: "look", job_finder: "finder", about_you: "about", stories: "stories" };
  function friendly(err) {
    const [path, msg] = [err.slice(0, err.indexOf(":")), err.slice(err.indexOf(":") + 1).trim()];
    if (path === "where_to_look.titles" && /at least/.test(msg)) return { step: "look", text: "Add at least one job title to look for." };
    if (path === "basics.preferred_name") return { step: "you", text: "Tell us what to call you." };
    if (path === "job_finder.sources") return { step: "finder", text: "Choose at least one place for the job finder to look." };
    let title = path;
    try { title = S(path.replace(/\[\d+\]/g, "")).title || path; } catch (e) { /* keep path */ }
    return { step: STEP_OF[path.split(".")[0].replace(/\[.*/, "")] || "download", text: `${title}: ${msg}` };
  }
  function row(k, v) { return v ? h("div", null, h("dt", null, k), h("dd", null, v)) : null; }
  function download() {
    const intake = L.buildIntake(answers), { errors } = L.validate(intake, B.schema);
    const extra = [];
    if (!finderOff() && !(answers.sources || []).length) extra.push("job_finder.sources: none chosen");
    const problems = errors.concat(extra).map(friendly);
    const labels = (path, vals) => (vals || []).map((v) => S(path)["x-labels"][v] || v).join(", ");
    const wy = intake.what_you_want || {}, jf = intake.job_finder;
    const folder = `${L.slug(answers.preferred_name)}-job-search`;
    const out = [h("p", { class: "eyebrow" }, `Step ${current + 1} of ${STEPS.length}`), h("h2", { tabindex: "-1" }, "Review and download"),
      h("dl", { class: "summary" },
        row("Name", intake.basics.preferred_name),
        row("What matters most", labels("what_you_want.priorities", wy.priorities) || "Not ranked yet"),
        row("Job titles", (intake.where_to_look.titles || []).join(", ")),
        row("Job finder", jf ? `On: ${labels("job_finder.sources", jf.sources)}` : "Off"),
        row("Daily run", jf ? (jf.daily_run === "off" ? "Off" : `Every day at ${jf.daily_run}`) : null),
        row("Resume", resumeFile ? resumeFile.name : "Not added (you can add it to the folder later)"),
        row("Stories", intake.stories ? `${intake.stories.length} answered` : "None yet (Claude can help later)"))];
    if (problems.length) {
      out.push(h("div", { class: "problems", role: "alert" }, h("strong", null, "Before you download:"),
        h("ul", null, problems.map((p) => h("li", null, p.text, " ", h("button", { type: "button", onclick: () => go(STEPS.findIndex((s) => s.id === p.step)) }, "Fix this"))))));
    }
    const done = h("div", { id: "after", hidden: true },
      h("h3", null, "Next: open it with Claude"),
      h("ol", { class: "next" },
        h("li", null, "Unzip it and move the folder somewhere permanent, like your home folder (not Downloads)."),
        h("li", null, "If you don't have Claude Code yet, open Terminal and paste:", copyable("curl -fsSL https://claude.ai/install.sh | bash"), h("span", { class: "help" }, "On Windows, install WSL first and run it there.")),
        h("li", null, "Go into the folder and start Claude:", copyable(`cd ~/${folder}\nclaude`)),
        h("li", null, "Say hi. Claude builds your tracker from your answers and walks you through a short first session. It helps you install anything missing (Python, Postgres) and asks before installing anything.")),
      h("p", { class: "help" }, "The same steps are in START_HERE.txt inside the folder."));
    out.push(h("div", { class: "actions" },
      h("button", { type: "button", class: "btn secondary", onclick: () => go(current - 1) }, "Back"),
      h("span", { class: "btn-row" },
        h("button", { type: "button", class: "btn ghost", disabled: problems.length > 0, onclick: () => save_("json", done) }, "Download answers only"),
        h("button", { type: "button", class: "btn primary", disabled: problems.length > 0, onclick: () => save_("zip", done) }, "Download my tracker (.zip)"))));
    out.push(done, startOver());
    return out;
  }
  function copyable(text) {
    const btn = h("button", { type: "button", class: "btn ghost", onclick: () => {
      (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => { btn.textContent = "Copied"; }, () => { btn.textContent = "Select and copy it"; });
    } }, "Copy");
    return h("div", null, h("pre", { class: "cmd" }, text), btn);
  }
  async function save_(kind, done) {
    const resume = kind === "zip" && resumeFile ? { name: resumeFile.name, bytes: new Uint8Array(await resumeFile.arrayBuffer()) } : null;
    const pkg = L.buildPackage(answers, B, resume);
    if (pkg.errors.length) { render(); return; }
    const blob = kind === "zip" ? new Blob([pkg.zip], { type: "application/zip" })
      : new Blob([JSON.stringify(pkg.intake, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = h("a", { href: url, download: kind === "zip" ? pkg.folder + ".zip" : "intake.json" });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    done.hidden = false; done.querySelector("h3").setAttribute("tabindex", "-1"); done.querySelector("h3").focus();
  }
  function startOver() {
    const b = h("button", { type: "button", class: "btn danger", onclick: () => {
      if (b.dataset.armed) { try { localStorage.removeItem(STORE); } catch (e) { /* nothing saved */ } answers = Object.assign({}, defaults); resumeFile = null; go(0); return; }
      b.dataset.armed = "1"; b.textContent = "Click again to clear all your answers";
    } }, "Start over");
    return h("p", { class: "mt-lg" }, b);
  }

  // ---------- start ----------
  document.getElementById("version").textContent = `· setup files ${B.version}`;
  const want = (location.hash.match(/step=([a-z]+)/) || [])[1];
  current = Math.max(0, STEPS.findIndex((s) => s.id === want));
  render();
  window.JSTPage = { answers: () => answers, go, STEPS: STEPS.map((s) => s.id) }; // for testing
})();
