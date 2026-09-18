(() => {
  "use strict";

  const TYPE = "tuliprox-status-card";
  const TEXT = {
    en: {
      title: "Tuliprox", online: "Online", offline: "Offline", unknown: "Unknown",
      missing: "Entity not found", waiting: "Waiting for Home Assistant",
      users: "Active users", connections: "Connections", streams: "Streams",
      totals: "Server totals", live: "Active streams", filtered: "Filtered streams",
      empty: "No active streams", noMatch: "No streams for the selected users",
      noData: "Stream details not reported", unavailable: "Live data unavailable",
      user: "Unknown user", channel: "Unknown channel", version: "Version",
      uptime: "Uptime", cache: "Cache", updated: "Last update", days: "d",
      entity: "Server sensor", titleField: "Title", show_details: "Show details",
      filter: "Users", filterHelp: "Exact usernames, one per line. Empty shows all. Filters stream rows only; counts are server totals.",
      entityError: "Select a server sensor (sensor.*).", titleError: "Title must be text.",
      detailsError: "show_details must be true or false.",
      usersError: "users must be a list of non-empty usernames.",
    },
    da: {
      title: "Tuliprox", online: "Online", offline: "Offline", unknown: "Ukendt",
      missing: "Entitet ikke fundet", waiting: "Venter p\u00e5 Home Assistant",
      users: "Aktive brugere", connections: "Forbindelser", streams: "Streams",
      totals: "Servertotaler", live: "Aktive streams", filtered: "Filtrerede streams",
      empty: "Ingen aktive streams", noMatch: "Ingen streams for de valgte brugere",
      noData: "Streamdetaljer ikke rapporteret", unavailable: "Livedata er ikke tilg\u00e6ngelige",
      user: "Ukendt bruger", channel: "Ukendt kanal", version: "Version",
      uptime: "Oppetid", cache: "Cache", updated: "Seneste opdatering", days: "d",
      entity: "Serversensor", titleField: "Titel", show_details: "Vis detaljer",
      filter: "Brugere", filterHelp: "Pr\u00e6cise brugernavne, et pr. linje. Tomt viser alle. Filtrerer kun streamr\u00e6kker; tallene er servertotaler.",
      entityError: "V\u00e6lg en serversensor (sensor.*).", titleError: "Titlen skal v\u00e6re tekst.",
      detailsError: "show_details skal v\u00e6re true eller false.",
      usersError: "users skal v\u00e6re en liste med ikke-tomme brugernavne.",
    },
  };
  const language = (hass) => String(hass?.locale?.language || hass?.language || "en").toLowerCase().startsWith("da") ? "da" : "en";
  const text = (hass) => TEXT[language(hass)];
  const scalar = (value, fallback = "-") =>
    (typeof value === "string" && value.trim()) || (typeof value === "number" && Number.isFinite(value))
      ? String(value) : fallback;
  const count = (value) => typeof value === "number" && Number.isFinite(value) && value >= 0 ? String(value) : "-";
  const node = (tag, className, value) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (value !== undefined) element.textContent = value;
    return element;
  };
  function validate(config, hass, allowEmpty = false) {
    const t = text(hass);
    if (!config || typeof config !== "object" || Array.isArray(config)) throw new Error(t.entityError);
    if (!(allowEmpty && !config.entity) && (typeof config.entity !== "string" || !/^sensor\.[a-z0-9_]+$/.test(config.entity))) throw new Error(t.entityError);
    if (config.title !== undefined && typeof config.title !== "string") throw new Error(t.titleError);
    if (config.show_details !== undefined && typeof config.show_details !== "boolean") throw new Error(t.detailsError);
    if (config.users !== undefined && (!Array.isArray(config.users) || config.users.some((user) => typeof user !== "string" || !user.trim()))) throw new Error(t.usersError);
    return { ...config, show_details: config.show_details ?? true, ...(config.users ? { users: [...config.users] } : {}) };
  }

  const STYLE = `
    :host { display:block; min-width:0; height:100%; container-type:inline-size; color:var(--primary-text-color); }
    * { box-sizing:border-box; }
    ha-card { display:flex; flex-direction:column; height:100%; overflow:hidden; padding:18px;
      background:var(--ha-card-background,var(--card-background-color)); }
    header { display:flex; align-items:center; gap:12px; margin-bottom:18px; min-width:0; }
    .mark { display:grid; place-items:center; flex:none; width:40px; height:40px; border-radius:12px;
      background:var(--secondary-background-color); color:var(--primary-color); font-size:22px; font-weight:700; }
    h2 { font-size:18px; font-weight:600; line-height:1.3; margin:0; overflow-wrap:anywhere; }
    .heading { flex:1; min-width:0; }
    .status { display:flex; align-items:center; gap:6px; margin-top:5px; font-size:12px; color:var(--secondary-text-color); overflow-wrap:anywhere; }
    .status::before { content:""; width:7px; height:7px; border-radius:50%; flex:none; background:var(--warning-color,#c58a20); }
    .status.online::before { background:var(--success-color,#43a047); }
    .status.offline::before { background:var(--error-color,#db4437); }
    .eyebrow { font-size:11px; color:var(--secondary-text-color); letter-spacing:.04em; margin:0 0 8px; }
    .counts { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-bottom:18px; }
    .metric { padding:10px 8px; border-radius:10px; background:var(--secondary-background-color); min-width:0; }
    .value { display:block; font-size:24px; line-height:1.2; font-weight:600; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
    .label { display:block; margin-top:5px; color:var(--secondary-text-color); font-size:11px; overflow-wrap:anywhere; }
    h3 { font-size:13px; font-weight:500; margin:0 0 8px; }
    ul { padding:0; margin:0; list-style:none; max-height:300px; overflow:auto; }
    li { display:flex; align-items:center; gap:10px; padding:10px 0; border-top:1px solid var(--divider-color); }
    .stream-icon { flex:none; color:var(--secondary-text-color); font-size:16px; }
    .stream-text { min-width:0; }
    .channel { font-size:14px; line-height:1.4; overflow-wrap:anywhere; }
    .username { font-size:12px; color:var(--secondary-text-color); margin-top:2px; overflow-wrap:anywhere; }
    .empty { padding:16px 0; font-size:13px; color:var(--secondary-text-color); }
    dl { display:grid; grid-template-columns:auto minmax(0,1fr); gap:7px 16px; margin:14px 0 0;
      padding-top:14px; border-top:1px solid var(--divider-color); font-size:12px; }
    dt { color:var(--secondary-text-color); } dd { margin:0; text-align:end; overflow-wrap:anywhere; white-space:pre-wrap; }
    @media(max-width:360px) { ha-card { padding:14px; } .counts { gap:5px; } .value { font-size:21px; } }
    @container(max-width:300px) {
      .counts { grid-template-columns:1fr; gap:5px; }
      .metric { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:7px 10px; }
      .value { font-size:20px; } .label { margin:0; text-align:end; }
      dl { gap:7px 10px; }
    }
  `;

  class TuliproxStatusCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.shadowRoot.append(node("style", "", STYLE));
      this._card = node("ha-card");
      this.shadowRoot.append(this._card);
    }

    setConfig(config) {
      this._config = validate(config, this._hass);
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      // State strings are versions; streams can change without a state change.
      this._render();
    }

    static getConfigElement() { return document.createElement(`${TYPE}-editor`); }

    static getStubConfig(hass) {
      const entity = Object.keys(hass?.states || {}).find((id) => {
        const attrs = hass.states[id]?.attributes;
        return id.startsWith("sensor.") && attrs && "uptime_secs" in attrs && "active_user_connections" in attrs;
      });
      return { entity: entity || "", show_details: true };
    }

    getCardSize() { return Math.ceil((240 + Math.min(this._streamRows || 0, 5) * 56 + (this._config?.show_details !== false ? 140 : 0)) / 50); }
    getGridOptions() { return { columns: 12, min_columns: 6, min_rows: 3 }; }

    _render() {
      if (!this._config) return;
      const t = text(this._hass);
      const entity = this._hass?.states?.[this._config.entity];
      const snapshot = JSON.stringify([this._config, language(this._hass), !!this._hass, this._hass?.connected, entity]);
      if (snapshot === this._snapshot) return;
      this._snapshot = snapshot;
      const attrs = entity?.attributes || {};
      const state = scalar(entity?.state, "").trim().toLowerCase();
      const status = scalar(attrs.status, "").trim().toLowerCase();
      const disconnected = this._hass?.connected === false;
      const offline = disconnected || state === "unavailable" || ["offline", "error", "down", "unavailable", "failed"].includes(status);
      const available = !!entity && !!state && state !== "unknown" && !offline;
      const healthy = available && ["ok", "online", "healthy", "running", "up"].includes(status);
      let statusText = healthy ? t.online : scalar(attrs.status, t.unknown);
      if (!this._hass) statusText = t.waiting;
      else if (offline) statusText = t.offline;
      else if (!entity) statusText = t.missing;
      else if (!state || state === "unknown") statusText = t.unknown;

      const header = node("header");
      const mark = node("span", "mark", "T");
      mark.setAttribute("aria-hidden", "true");
      const heading = node("div", "heading");
      heading.append(node("h2", "", this._config.title || t.title));
      const statusNode = node("div", `status ${healthy ? "online" : offline ? "offline" : "unknown"}`, statusText);
      statusNode.setAttribute("role", "status");
      heading.append(statusNode);
      header.append(mark, heading);
      const counts = node("div", "counts");
      for (const [key, label] of [["active_users", t.users], ["active_user_connections", t.connections], ["stream_count", t.streams]]) {
        const metric = node("div", "metric");
        metric.append(node("span", "value", available ? count(attrs[key]) : "-"), node("span", "label", label));
        counts.append(metric);
      }
      const filtered = !!this._config.users?.length;
      const reported = Array.isArray(attrs.streams);
      const streams = available && reported ? attrs.streams.filter((stream) => stream && typeof stream === "object" && (!filtered || this._config.users.includes(stream.username))) : [];
      this._streamRows = streams.length;
      const list = node("ul");
      list.setAttribute("aria-label", filtered ? t.filtered : t.live);
      for (const stream of streams) {
        const row = node("li");
        const icon = node("span", "stream-icon", "\u25b6");
        icon.setAttribute("aria-hidden", "true");
        const content = node("div", "stream-text");
        content.append(node("div", "channel", scalar(stream.channel?.title, t.channel)), node("div", "username", scalar(stream.username, t.user)));
        row.append(icon, content);
        list.append(row);
      }
      const body = streams.length ? list : node("div", "empty", !available ? t.unavailable : !reported ? t.noData : filtered ? t.noMatch : t.empty);
      this._card.replaceChildren(header, node("p", "eyebrow", t.totals), counts, node("h3", "", filtered ? t.filtered : t.live), body);
      if (this._config.show_details) {
        const details = node("dl");
        const seconds = attrs.uptime_secs;
        const uptime = typeof seconds === "number" && Number.isFinite(seconds) && seconds >= 0
          ? `${Math.floor(seconds / 86400)}${t.days} ${Math.floor(seconds / 3600) % 24}h ${Math.floor(seconds / 60) % 60}m` : "-";
        let cache = scalar(attrs.cache);
        if (typeof attrs.cache === "boolean") cache = String(attrs.cache);
        else if (attrs.cache && typeof attrs.cache === "object") {
          try { cache = JSON.stringify(attrs.cache); } catch { cache = "-"; }
        }
        let updated = scalar(attrs.updated_at);
        if (typeof attrs.updated_at === "string" && attrs.updated_at.trim()) {
          const date = new Date(attrs.updated_at);
          if (Number.isFinite(date.getTime())) updated = date.toLocaleString(language(this._hass));
        }
        for (const [label, value] of [[t.version, available ? scalar(attrs.version, scalar(entity?.state)) : "-"], [t.uptime, available ? uptime : "-"], [t.cache, available ? cache : "-"], [t.updated, updated]]) {
          details.append(node("dt", "", label), node("dd", "", value));
        }
        this._card.append(details);
      }
    }
  }

  class TuliproxStatusEditor extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.shadowRoot.append(node("style", "", `
        :host { display:block; color:var(--primary-text-color); }
        label { display:block; margin:12px 0; font-size:14px; }
        input:not([type=checkbox]), textarea { display:block; box-sizing:border-box; width:100%; margin-top:6px; padding:10px;
          color:var(--primary-text-color); background:var(--card-background-color); border:1px solid var(--divider-color); border-radius:6px; font:inherit; }
        textarea { min-height:80px; resize:vertical; } p { color:var(--secondary-text-color); font-size:12px; }
        .error { color:var(--error-color,#db4437); }
      `));
      this._body = node("div");
      this._error = node("p", "error");
      this._error.setAttribute("role", "alert");
      this.shadowRoot.append(this._body, this._error);
    }

    setConfig(config) {
      const next = validate(config, this._hass, true);
      // The dashboard echoes config-changed; keep focused editor controls intact.
      if (JSON.stringify(next) === JSON.stringify(this._config)) return;
      this._config = next;
      this._render();
    }

    set hass(hass) {
      const previousLanguage = language(this._hass);
      this._hass = hass;
      if (!this._body.firstChild || previousLanguage !== language(hass)) this._render();
      else if (this._form) this._form.hass = hass;
    }

    _change(value) {
      try {
        const config = validate({ ...this._config, ...value }, this._hass);
        this._error.textContent = "";
        this._config = config;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      } catch (error) {
        this._error.textContent = error.message;
      }
    }

    _render() {
      if (!this._config) return;
      const t = text(this._hass);
      this._body.replaceChildren();
      this._form = undefined;
      // Do not depend on HA's lazy-loaded editor internals or Lit prototypes.
      if (customElements.get("ha-form")) {
        const form = node("ha-form");
        form.hass = this._hass;
        form.data = this._config;
        form.schema = [
          { name: "entity", required: true, selector: { entity: { domain: "sensor" } } },
          { name: "title", selector: { text: {} } },
          { name: "show_details", selector: { boolean: {} } },
          { name: "users", selector: { select: { options: [], multiple: true, custom_value: true } } },
        ];
        form.computeLabel = (schema) => ({ entity: t.entity, title: t.titleField, show_details: t.show_details, users: t.filter })[schema.name];
        form.addEventListener("value-changed", (event) => {
          event.stopPropagation();
          if (event.detail?.value) this._change(event.detail.value);
        });
        this._form = form;
        this._body.append(form);
      } else {
        for (const [key, labelText] of [["entity", t.entity], ["title", t.titleField], ["show_details", t.show_details], ["users", t.filter]]) {
          const label = node("label", "", labelText);
          const input = node(key === "users" ? "textarea" : "input");
          if (key === "show_details") { input.type = "checkbox"; input.checked = this._config.show_details; }
          else input.value = key === "users" ? (this._config.users || []).join("\n") : this._config[key] || "";
          if (key === "entity") { input.placeholder = "sensor.tuliprox_server"; input.required = true; }
          input.addEventListener("change", () => this._change({ [key]: key === "show_details" ? input.checked : key === "users" ? input.value.split("\n").filter((user) => user.trim()) : input.value }));
          label.append(input);
          this._body.append(label);
        }
      }
      this._body.append(node("p", "", t.filterHelp));
    }
  }

  if (!customElements.get(TYPE)) customElements.define(TYPE, TuliproxStatusCard);
  if (!customElements.get(`${TYPE}-editor`)) customElements.define(`${TYPE}-editor`, TuliproxStatusEditor);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === TYPE)) {
    window.customCards.push({ type: TYPE, name: "Tuliprox Status", description: "Tuliprox server health, connections and active streams.", preview: true });
  }
})();
