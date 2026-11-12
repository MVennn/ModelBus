/* ModelBus 控制台 · 前端
 * > 一句话：hash 路由 8 页，统一消费 {ok,generated_at,ttl_ms,data} 包，零外部依赖、零外网请求。
 */
(() => {
  "use strict";

  const PAGES = [
    { id: "overview", name: "总览",   ico: "▦", sub: "网关与数据面一眼可见", routes: ["/api/overview", "/api/ops"] },
    { id: "models",   name: "模型",   ico: "◇", sub: "别名 · 探测 · 评分 · 配额 · 榜单", routes: ["/api/models", "/api/probe", "/api/scores", "/api/quota", "/api/arena"] },
    { id: "prices",   name: "价格",   ico: "＄", sub: "WorkBuddy 与 Qoder 价目快照", routes: ["/api/prices"] },
    { id: "health",   name: "健康",   ico: "✚", sub: "网关 /health 原样字段展开", routes: ["/api/gateway"] },
    { id: "traffic",  name: "流量",   ico: "⇅", sub: "请求日志尾部采样", routes: ["/api/traffic"] },
    { id: "accounts", name: "账号",   ico: "◎", sub: "只列存在性与掩码", routes: ["/api/accounts"] },
    { id: "logs",     name: "日志",   ico: "≡", sub: "zgate.log 尾部 + 实时流", routes: ["/api/logs"] },
    { id: "ops",      name: "运维",   ico: "⚙", sub: "占用候选 · 配置 · 动作记录", routes: ["/api/ops", "/api/config", "/api/actions/jobs"] },
  ];

  const $ = (s) => document.querySelector(s);
  const view = $("#view"), nav = $("#nav"), title = $("#page-title"), sub = $("#page-sub");
  const stamp = $("#stamp"), foot = $("#foot-meta"), toast = $("#toast");
  let timer = null, sse = null, current = "overview";

  const esc = (v) => String(v == null ? "" : v)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  const n = (v) => (typeof v === "number" ? v.toLocaleString("zh-CN") : esc(v));
  const bytes = (v) => {
    if (typeof v !== "number" || v < 0) return "—";
    const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0, x = v;
    while (x >= 1024 && i < u.length - 1) { x /= 1024; i++; }
    return (i === 0 ? x : x.toFixed(x < 10 ? 2 : 1)) + " " + u[i];
  };
  const short = (v, w = 90) => { const s = String(v == null ? "" : v); return s.length > w ? s.slice(0, w - 1) + "…" : s; };

  function tone(state) {
    const s = String(state == null ? "" : state).toLowerCase();
    if (/^(ok|up|true|running|healthy|200|ready|external|enabled)$/.test(s) || s.startsWith("2")) return "ok";
    if (/^(no_key|missing|down|false|error|bad|fail|timeout|stopped|disabled|5\d\d)$/.test(s) || /fail|error|timeout/.test(s)) return "bad";
    if (/cool|warn|idle|pending|try|probe|partial|slow/.test(s)) return "warn";
    return "muted";
  }
  const pillTone = { ok: "bg-green-lt", warn: "bg-yellow-lt", bad: "bg-red-lt", info: "bg-blue-lt", muted: "bg-secondary-lt" };
  // pill() 自己已对 label 做 esc()，输出是可信片段；用 data-mb-pill 让 table() 精确识别，避免二次转义。
  const pill = (label, t) => `<span class="badge ${pillTone[t] || pillTone.muted}" data-mb-pill>${esc(label == null || label === "" ? "—" : label)}</span>`;

  function table(headers, rows, opts = {}) {
    if (!rows || !rows.length) return empty(opts.emptyText || "这个数据源当前没有记录");
    const th = headers.map(h => `<th class="${h.num ? "text-end" : ""}">${esc(h.label)}</th>`).join("");
    const tr = rows.map(r => "<tr>" + r.map(c => {
      const cell = typeof c === "object" && c !== null && "html" in c ? c.html
        : (typeof c === "string" && c.startsWith('<span class="badge ') && c.includes("data-mb-pill") && c.endsWith("</span>") ? c : esc(c));
      const cls = typeof c === "object" && c !== null && c.num ? ' class="text-end num"' : "";
      return `<td${cls}>${cell}</td>`;
    }).join("") + "</tr>").join("");
    return `<div class="card"><div class="table-responsive"><table class="table table-vcenter card-table"><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div></div>`;
  }
  const H = (html, cls = "") => ({ html, cls });
  const num = (v) => ({ html: n(v), num: true });

  function empty(text) {
    return `<div class="empty"><p class="empty-icon" aria-hidden="true">◌</p><p class="empty-title">${esc(text)}</p><p class="empty-subtitle text-secondary">等数据源出现内容后会自动显示，不会拿占位数据冒充。</p></div>`;
  }
  function errorState(err) {
    return `<div class="alert alert-danger" role="alert"><div><strong>${esc(err.code || "读取失败")}</strong><div class="small text-secondary mt-1">${esc(err.message || "未知错误")}</div></div></div>`;
  }
  function kpi(label, value, note) {
    return `<div class="card"><div class="card-body"><div class="subheader">${esc(label)}</div><div class="kpi-value mt-2">${value}</div>${note ? `<div class="kpi-note small mt-1">${esc(note)}</div>` : ""}</div></div>`;
  }
  function section(head, body, hint) {
    return `<section class="mb-4"><div class="d-flex align-items-baseline justify-content-between gap-2 mb-2"><h2 class="subheader mb-0">${esc(head)}</h2>${hint ? `<span class="small text-secondary text-end">${esc(hint)}</span>` : ""}</div>${body}</section>`;
  }
  function kv(pairs) {
    return `<dl class="kv">${pairs.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("")}</dl>`;
  }

  async function api(path, opts = {}) {
    const resp = await fetch(path, {
      method: opts.method || "GET",
      headers: Object.assign({ Accept: "application/json" }, opts.headers || {}),
      cache: "no-store"
    });
    const env = await resp.json().catch(() => ({ ok: false, error: { code: "PARSE_ERROR", message: "响应不是 JSON" } }));
    if (!resp.ok || !env.ok) {
      const e = env.error || { code: "HTTP_" + resp.status, message: "HTTP " + resp.status };
      throw Object.assign(new Error(e.message), { code: e.code, payload: env });
    }
    return env;
  }
  async function all(paths) {
    const settled = await Promise.allSettled(paths.map(api));
    const out = {};
    settled.forEach((s, i) => { out[paths[i]] = s.status === "fulfilled" ? s.value : { __err: s.reason }; });
    return out;
  }
  const D = (bag, path) => (bag[path] && bag[path].data) || {};
  const E = (bag, path) => bag[path] && bag[path].__err;

  // ---- 页面 --------------------------------------------------------------
  function renderOverview(bag) {
    const d = D(bag, "/api/overview"), ops = D(bag, "/api/ops");
    if (E(bag, "/api/overview")) return errorState(E(bag, "/api/overview"));
    const segs = d.segments || {};
    const segRows = Object.entries(segs).map(([k, v]) => [
      esc(k), pill(v.state, tone(v.state)), v.key ? pill("已配 key", "ok") : pill("无 key", "bad"),
      H(`<span class="cell-clip" title="${esc(v.base || "")}">${esc(short(v.base, 60) || "—")}</span>`),
      esc(v.child || "—"),
    ]);
    const hop = d.hops || {}, pr = d.probe || {}, tr = d.traffic || {};
    const kpis = [
      kpi("网关状态", d.ok === true ? pill("正常", "ok") : pill("异常", "bad"), "来自 /health 的 ok 字段"),
      kpi("别名模型", n(d.alias_models ?? "—"), "alias.models"),
      kpi("渠道段", n(Object.keys(segs).length), "workbuddy / qoder / qwen / qiniu / gemini / hajimi / opencode"),
      kpi("跳数可用", n(hop.ok ?? "—") + " / " + n(hop.total ?? "—"), "hops 段 ok 计数"),
      kpi("探测通过", n(pr.ok ?? "—") + " / " + n(pr.total ?? "—"), "model_probe.json"),
      kpi("请求采样", n(tr.requests ?? "—"), tr.file ? esc(tr.file) : "当日 jsonl 尾部"),
      kpi("采样成功率", (tr.ok_rate != null ? (tr.ok_rate * 100).toFixed(1) : "—") + "%", "tail 800 行"),
      kpi("可复核占用", bytes(d.ops?.reclaimable_bytes ?? ops.reclaimable_bytes), "仅展示，后台不自动清理"),
    ];
    const cooling = d.cooling, guard = d.guard;
    const detail = section("运行细节", kv([
      ["运行秒数", `<span class="num">${n(d.uptime_s)}</span>`],
      ["冷却条目", `<span class="num">${n(cooling)}</span>`],
      ["Reasoning 守卫", guard ? `${pill(guard.mode || "—", "info")} ${esc((guard.channels || []).join(", ") || "无渠道带位")}` : "—"],
      ["/health 体积", `<span class="num">${bytes(d.health_bytes)}</span>`],
      ["平均耗时", `<span class="num">${n(tr.avg_ms)} ms</span>`],
      ["采样 token", `<span class="num">${n(tr.tokens)}</span>`],
    ]));
    const topOps = (ops.candidates || []).slice(0, 5).map(c => [
      esc(c.key), H(`<span class="cell-clip" title="${esc(c.path)}">${esc(c.path)}</span>`),
      num(c.count), num(bytes(c.bytes)), esc(c.review),
    ]);
    return section("关键指标", `<div class="grid kpi">${kpis.join("")}</div>`, "每 10 秒自动刷新；/health 每次触发 aliases.Reload()，不做高频轮询")
      + section("渠道段", table(
          [{ label: "渠道" }, { label: "状态" }, { label: "凭据" }, { label: "Base" }, { label: "Child" }],
          segRows))
      + detail
      + section("占用候选（只读）", table(
          [{ label: "项" }, { label: "路径" }, { label: "文件数", num: true }, { label: "体积", num: true }, { label: "处置建议" }],
          topOps, { emptyText: "没有可复核的占用候选" }));
  }

  function renderModels(bag) {
    const a = D(bag, "/api/models"), p = D(bag, "/api/probe"),
          s = D(bag, "/api/scores"), q = D(bag, "/api/quota"), ar = D(bag, "/api/arena");
    const firstErr = Object.values(bag).find(x => x && x.__err);
    if (firstErr && !Object.keys(a).length) return errorState(firstErr.__err);
    const aliasRows = (a.rows || []).map(r => {
      const spec = { ...r }; delete spec.name;
      return [esc(r.name), H(`<span class="cell-clip" title="${esc(JSON.stringify(spec))}">${esc(short(JSON.stringify(spec), 140))}</span>`)];
    });
    const probeRows = (p.rows || []).map(r => [
      esc(r.name), pill(r.status || "—", tone(r.status)), num(r.http), num(r.ms),
      esc(r.provider || "—"), H(`<span class="cell-clip" title="${esc(r.detail || "")}">${esc(short(r.detail, 80) || "—")}</span>`),
      r.ever_ok === true ? pill("曾通", "ok") : pill("—", "muted"),
    ]);
    const scoreRows = (s.rows || []).map(r => [esc(r.name), num(r.score), num(r.price), esc(r.source || "—")]);
    const quotaRows = (q.windows || []).map((w, i) => [
      num(i + 1), H(`<span class="cell-clip">${esc(short(JSON.stringify(w), 160))}</span>`),
    ]);
    const arenaRows = (ar.rows || []).slice(0, 20).map((r, i) => [
      num(i + 1), H(`<span class="cell-clip">${esc(short(JSON.stringify(r), 160))}</span>`),
    ]);
    return section("别名表", table([{ label: "模型名" }, { label: "映射规格（脱敏）" }], aliasRows),
        `${n(a.count ?? 0)} 条 · legacy ${n(a.legacy_count ?? 0)} 条 · ${esc(a.generated_at || "—")}`)
      + section("探测结果", table(
          [{ label: "探测键" }, { label: "状态" }, { label: "HTTP", num: true }, { label: "耗时 ms", num: true },
           { label: "Provider" }, { label: "详情" }, { label: "曾通" }], probeRows),
          `${n(p.ok ?? 0)} / ${n(p.total ?? 0)} 通过`)
      + section("评分与配额", `<div class="grid two">` +
          `<div>${table([{ label: "模型" }, { label: "分", num: true }, { label: "价", num: true }, { label: "源" }], scoreRows, { emptyText: "暂无评分" })}</div>` +
          `<div>${table([{ label: "#" }, { label: "配额窗口" }], quotaRows, { emptyText: "暂无配额窗口" })}</div></div>`,
          `评分 ${esc(s.checked_at || "—")}`)
      + section("榜单前 20 行", table([{ label: "#" }, { label: "行（脱敏）" }], arenaRows, { emptyText: "暂无榜单数据" }),
          `共 ${n(ar.total_rows ?? 0)} 行，只展开前 20 行`);
  }

  function renderPrices(bag) {
    const d = D(bag, "/api/prices");
    if (E(bag, "/api/prices")) return errorState(E(bag, "/api/prices"));
    const wbRows = (d.workbuddy || []).map(r => [
      esc(r.id || "—"), num(r.credits), num(r.eff_rate), num(r.list_rate),
      esc(r.promo_label || "—"), num(r.ctx), num(r.out),
      r.tool === true ? pill("支持", "ok") : pill("—", "muted"),
      esc(r.default_effort || "—"),
    ]);
    const qdRows = (d.qoder || []).map(r => [
      esc(r.name), num(r.price), num(r.peak), num(r.valley), num(r.off_peak),
    ]);
    return section("WorkBuddy 价目", table(
        [{ label: "模型" }, { label: "credits", num: true }, { label: "eff_rate", num: true }, { label: "list_rate", num: true },
         { label: "促销" }, { label: "上下文", num: true }, { label: "输出", num: true }, { label: "工具" }, { label: "默认 effort" }],
        wbRows), `${n(d.workbuddy_count ?? 0)} 条`)
      + section("Qoder 价目", table(
          [{ label: "模型" }, { label: "price", num: true }, { label: "peak", num: true }, { label: "valley", num: true }, { label: "off_peak", num: true }],
          qdRows), `${n(d.qoder_count ?? 0)} 条`);
  }

  function renderHealth(bag) {
    const d = D(bag, "/api/gateway");
    if (E(bag, "/api/gateway")) return errorState(E(bag, "/api/gateway"));
    const h = d.health || {};
    const rows = Object.entries(h).map(([k, v]) => [
      esc(k),
      H(`<span class="cell-clip" title="${esc(typeof v === "string" ? v : JSON.stringify(v))}">` +
         `<code>${esc(short(typeof v === "string" ? v : JSON.stringify(v), 220))}</code></span>`),
    ]);
    const models = d.models || {};
    const mlist = Array.isArray(models.data) ? models.data : (models.models || []);
    return section("网关契约", kv([
      ["网关", esc(d.gateway || "—")],
      ["/health", `${pill(h.ok === true ? "ok=true" : "ok 异常", h.ok === true ? "ok" : "bad")} ${esc(d.health_content_type || "—")}`],
      ["响应体积", `<span class="num">${bytes(d.health_bytes)}</span>`],
      ["/v1/models", `${pill(mlist.length + " 条", mlist.length ? "ok" : "muted")} ${esc(d.models_content_type || "—")}`],
      ["轮询下限", `<span class="num">${n(d.polling_hint_ms)} ms</span>`],
    ]))
      + section("/health 字段原样展开", table([{ label: "字段" }, { label: "值（脱敏 JSON）" }], rows),
          "网关响应一字不改；控制台只做 scrub 后展示")
      + section("/health 原始 JSON（脱敏）", `<div class="code-block">${esc(JSON.stringify(h, null, 2))}</div>`, "上方表格与此处同源");
  }

  function renderTraffic(bag) {
    const d = D(bag, "/api/traffic");
    if (E(bag, "/api/traffic")) return errorState(E(bag, "/api/traffic"));
    const kpis = [
      kpi("采样请求", n(d.count ?? 0), d.file ? esc(d.file) : "当日 jsonl"),
      kpi("成功", n(d.ok ?? 0), "tail 800 行"),
      kpi("成功率", ((d.ok_rate ?? 0) * 100).toFixed(1) + "%", "按 ok=true 计"),
      kpi("平均耗时", n(d.avg_ms ?? 0) + " ms", "duration_ms 均值"),
      kpi("采样 token", n(d.tokens ?? 0), "total_tokens 合计"),
    ];
    const modelRows = (d.by_model || []).map(([k, v]) => [esc(k), num(v)]);
    const statusRows = (d.by_status || []).map(([k, v]) => [pill(k, tone(k)), num(v)]);
    const hourRows = (d.hours || []).map(([k, v]) => [esc(k), num(v)]);
    const fileRows = (d.files || []).map(f => [esc(f.name), num(bytes(f.bytes))]);
    return section("请求概览", `<div class="grid kpi">${kpis.join("")}</div>`, esc(d.note || ""))
      + section("分布", `<div class="grid two">` +
          `<div>${table([{ label: "模型" }, { label: "请求数", num: true }], modelRows, { emptyText: "暂无模型分布" })}</div>` +
          `<div>${table([{ label: "状态" }, { label: "请求数", num: true }], statusRows, { emptyText: "暂无状态分布" })}</div></div>`)
      + section("小时分布与日志文件", `<div class="grid two">` +
          `<div>${table([{ label: "小时" }, { label: "请求数", num: true }], hourRows, { emptyText: "暂无小时分布" })}</div>` +
          `<div>${table([{ label: "文件" }, { label: "体积", num: true }], fileRows, { emptyText: "暂无日志文件" })}</div></div>`);
  }

  function renderAccounts(bag) {
    const d = D(bag, "/api/accounts");
    if (E(bag, "/api/accounts")) return errorState(E(bag, "/api/accounts"));
    const wb = (d.workbuddy?.rows || []).map(r => [
      esc(r.id), esc(r.nickname || "—"), esc(r.uid || "—"),
      r.credential_present ? pill("已配置", "ok") : pill("未配置", "bad"),
      esc(short(r.expires_at, 30) || "—"), num(bytes(r.bytes)),
    ]);
    const qd = (d.qoder?.rows || []).map(r => [esc(r.id), num(bytes(r.bytes))]);
    const pc = d.provider_config || {};
    return section("凭据红线", `<div class="card flat"><div class="card-body">` + kv([
      ["provider_config.json", pc.present ? pill("存在 · 值不导出", "ok") : pill("缺失", "warn")],
      ["credentials.json", d.credentials?.present ? pill("存在 · 值不导出", "ok") : pill("缺失", "warn")],
      ["展示口径", "账号 ID / UID 一律掩码；账号文件只解析存在性与掩码，凭据字段值永不输出"],
    ]) + `</div></div>`)
      + section("WorkBuddy 账号", table(
          [{ label: "ID（掩码）" }, { label: "昵称" }, { label: "UID（掩码）" }, { label: "凭据" }, { label: "过期" }, { label: "体积", num: true }],
          wb), `${n(d.workbuddy?.count ?? 0)} 个`)
      + section("Qoder 账号文件", table([{ label: "ID（掩码）" }, { label: "体积", num: true }], qd,
          { emptyText: "暂无 Qoder 账号文件" }), esc(d.qoder?.note || ""));
  }

  function renderLogs(bag) {
    const d = D(bag, "/api/logs");
    if (E(bag, "/api/logs")) return errorState(E(bag, "/api/logs"));
    const lines = d.gateway_tail || [];
    const fileRows = (d.files || []).map(f => [esc(f.name), num(bytes(f.bytes)), esc(short(f.mtime, 30) || "—")]);
    return section("zgate.log 实时流", `<div class="card"><div class="card-body"><p class="kpi-label">EventSource · 每 2 秒推一次尾部 20 行 · 上限 60 秒后页面自动重连</p><div class="code-block" id="sse-box">连接中…</div></div></div>`)
      + section("静态尾部", `<div class="code-block">${lines.length ? lines.map(esc).join("\n") : "（暂无日志行）"}</div>`,
          `最多 ${n(d.tail_limit ?? 160)} 行`)
      + section("日志文件体积", table([{ label: "文件" }, { label: "体积", num: true }, { label: "修改时间" }], fileRows,
          { emptyText: "暂无日志文件" }), esc(d.note || ""));
  }

  function renderOps(bag) {
    const op = D(bag, "/api/ops"), cfg = D(bag, "/api/config"), jobs = D(bag, "/api/actions/jobs");
    const cRows = (op.candidates || []).map(c => [
      esc(c.key), H(`<span class="cell-clip" title="${esc(c.path)}">${esc(c.path)}</span>`),
      num(c.count), num(bytes(c.bytes)), esc(c.review),
    ]);
    const envRows = (cfg.env || []).map(e => [
      esc(e.name), e.configured ? pill("已设置", "ok") : pill("未设置", "muted"),
    ]);
    const fileRows = (cfg.files || []).map(f => [
      esc(f.label), f.present ? pill("存在", "ok") : pill("缺失", "warn"),
      num(bytes(f.bytes)), esc(short(f.mtime, 30) || "—"),
    ]);
    const jobRows = (jobs.history || []).map(j => [
      esc(j.at), esc(j.action), j.ok ? pill("成功", "ok") : pill("失败", "bad"),
      num(j.status), H(`<span class="cell-clip">${esc(short(JSON.stringify(j.response || j.error || {}), 120))}</span>`),
    ]);
    const du = op.disk || {};
    return section("磁盘与占用", `<div class="grid kpi">` +
        kpi("可复核占用", bytes(op.reclaimable_bytes ?? 0), "仅候选合计，后台不删任何文件") +
        kpi("磁盘总量", bytes(du.total ?? 0), "shutil.disk_usage") +
        kpi("磁盘可用", bytes(du.free ?? 0), "—") +
        `</div>`)
      + section("占用候选", table(
          [{ label: "项" }, { label: "路径" }, { label: "文件数", num: true }, { label: "体积", num: true }, { label: "处置建议" }],
          cRows, { emptyText: "暂无候选" }), esc(op.policy || ""))
      + section("环境变量与配置文件", `<div class="grid two">` +
          `<div>${table([{ label: "变量" }, { label: "状态" }], envRows, { emptyText: "暂无变量" })}</div>` +
          `<div>${table([{ label: "文件" }, { label: "状态" }, { label: "体积", num: true }, { label: "修改时间" }], fileRows, { emptyText: "暂无配置" })}</div></div>`,
          `网关 ${esc(cfg.gateway || "—")} · 绑定 ${esc(cfg.bind || "—")}`)
      + section("动作记录", table(
          [{ label: "时间" }, { label: "动作" }, { label: "结果" }, { label: "HTTP", num: true }, { label: "响应" }],
          jobRows, { emptyText: "本进程还没有执行过重载" }),
          `允许动作：${esc((jobs.allowed || []).join(", ") || "—")} · 当前${jobs.running ? "运行中" : "空闲"}`);
  }

  const RENDER = { overview: renderOverview, models: renderModels, prices: renderPrices,
    health: renderHealth, traffic: renderTraffic, accounts: renderAccounts, logs: renderLogs, ops: renderOps };

  // ---- 路由 / 生命周期 ----------------------------------------------------
  function buildNav() {
    nav.innerHTML = PAGES.map(p => `<li class="nav-item"><a class="nav-link" href="#/${p.id}" data-id="${p.id}"><span class="nav-link-icon" aria-hidden="true">${p.ico}</span><span class="nav-link-title">${p.name}</span></a></li>`).join("");
  }
  function cleanup() {
    if (timer) { clearInterval(timer); timer = null; }
    if (sse) { sse.close(); sse = null; }
  }
  function toastMsg(text, kind = "") {
    toast.textContent = text;
    toast.className = "toast show " + kind;
    setTimeout(() => { toast.classList.remove("show"); }, 3200);
  }
  function setGatewayDot(ok) {
    const dot = $("#gw-dot"), t = $("#gw-text");
    dot.className = "status-dot " + (ok === true ? "status-green" : ok === false ? "status-red" : "status-secondary");
    t.textContent = ok === true ? "网关在线" : ok === false ? "网关不可达" : "网关检测中";
  }

  async function loadPage() {
    cleanup();
    const id = (location.hash.replace(/^#\/?/, "").split("/")[0] || "overview").toLowerCase();
    const page = PAGES.find(p => p.id === id) || PAGES[0];
    current = page.id;
    document.querySelectorAll("#nav .nav-link").forEach(a => {
      if (a.dataset.id === page.id) { a.setAttribute("aria-current", "page"); a.classList.add("active"); }
      else { a.removeAttribute("aria-current"); a.classList.remove("active"); }
    });
    if (navbarMenu) { navbarMenu.classList.remove("show"); navToggle.setAttribute("aria-expanded", "false"); }
    title.textContent = page.name; sub.textContent = page.sub;
    view.innerHTML = `<div class="empty"><div class="empty-icon"><span class="spinner-border text-primary" role="status"></span></div><p class="empty-title">正在读取本地数据源…</p></div>`;
    let bag;
    try { bag = await all(page.routes); }
    catch (e) { view.innerHTML = errorState(e); return; }
    const first = bag[page.routes[0]];
    const generated = first && first.generated_at ? first.generated_at : "—";
    const ttl = first && first.ttl_ms ? first.ttl_ms : 0;
    stamp.textContent = "更新 " + short(generated.replace("T", " ").slice(0, 19), 19);
    foot.textContent = `TTL ${n(ttl)} ms · ${page.routes.length} 个数据源`;
    setGatewayDot(bag["/api/gateway"] ? (bag["/api/gateway"].ok === true && !bag["/api/gateway"].__err) : (bag["/api/overview"] ? (bag["/api/overview"].ok === true && !bag["/api/overview"].__err) : undefined));
    try { view.innerHTML = RENDER[page.id](bag); }
    catch (e) { view.innerHTML = errorState(e); return; }

    if (page.id === "overview") timer = setInterval(loadPage, 10000);
    if (page.id === "logs") {
      const box = $("#sse-box");
      try {
        sse = new EventSource("/api/logs/stream");
        sse.onmessage = (ev) => {
          try {
            const payload = JSON.parse(ev.data);
            box.textContent = (payload.lines || []).join("\n") || "（暂无日志行）";
            box.scrollTop = box.scrollHeight;
          } catch (_) { /* 忽略单帧解析失败 */ }
        };
        sse.onerror = () => { if (box) box.textContent += "\n[流断开，页面会在下次切换时重连]"; };
      } catch (_) { if (box) box.textContent = "浏览器不支持 EventSource"; }
    }
  }

  // ---- 交互 --------------------------------------------------------------
  const navToggle = $("#nav-toggle"), navbarMenu = $("#navbar-menu");
  function setTheme(next) {
    const root = document.documentElement;
    root.setAttribute("data-theme", next);
    root.setAttribute("data-bs-theme", next);
    try { localStorage.setItem("mb-theme", next); } catch (_) {}
  }
  buildNav();
  navToggle.addEventListener("click", () => {
    const open = navbarMenu.classList.toggle("show");
    navToggle.setAttribute("aria-expanded", String(open));
  });
  window.addEventListener("hashchange", loadPage);
  $("#btn-refresh").addEventListener("click", () => { loadPage(); toastMsg("已刷新当前页"); });
  $("#btn-theme").addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    setTheme(next);
  });
  try {
    const saved = localStorage.getItem("mb-theme");
    if (saved === "dark" || saved === "light") setTheme(saved);
  } catch (_) {}

  const modal = $("#modal"), gwSpan = $("#modal-gw");
  $("#btn-reload").addEventListener("click", () => { gwSpan.textContent = "网关"; modal.hidden = false; $("#modal-ok").focus(); });
  $("#modal-cancel").addEventListener("click", () => { modal.hidden = true; });
  modal.addEventListener("click", (e) => { if (e.target === modal) modal.hidden = true; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !modal.hidden) modal.hidden = true; });
  $("#modal-ok").addEventListener("click", async () => {
    const btn = $("#modal-ok"); btn.disabled = true; btn.textContent = "执行中…";
    try {
      // 同源 POST 由浏览器自动携带 Origin；服务端缺 Origin 一律 403
      const env = await api("/api/actions/reload", { method: "POST" });
      const r = env.data || {};
      toastMsg(r.ok ? `重载成功 · HTTP ${r.status}` : `重载返回 HTTP ${r.status}`, r.ok ? "good" : "bad");
      if (current === "ops") loadPage();
    } catch (e) { toastMsg(`${e.code || "失败"}：${e.message}`, "bad"); }
    finally { btn.disabled = false; btn.textContent = "确认重载"; modal.hidden = true; }
  });

  loadPage();
})();
