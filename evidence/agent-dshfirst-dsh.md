# ModelBus × DSH：宿主「面向 agent」落点审计（只读）

> 结论：agent/preset/session/goal/subagent 在 DSH 里都已是服务级一等公民，模型面只留一个适配器接缝（`ctx.llm`）和一个瀑布钩子（`llm/stream`）。ModelBus 该把自己做成「一个 provider 插件 + 一个本地控制端点」，冷却/竞速/预算/别名留在网关进程，别往宿主里塞调度器。

- 取证口径：asar 内 `$D/ = dsh/node_modules/@deepseek-ai/`，行号为包内文件行号；只读，未改任何文件。
- 宿主配置面：`~/.dsh/profiles/desktop/`（`cordis.patch.yml` 624 行 / 21,164 B）。

## 0. 任务书里那条路径不存在（必读）

`F:/Program Files/DeepSeekRuntime` 本机不存在，只是显示层改名。真实目录名含空格：`F:/Program Files/DeepSeek <空格> Harness/resources/app.asar`；硬编码字面量必 ENOENT，正确取法是读父目录按 `seek`+`h` 模糊匹配再拼 `resources/app.asar`。asar 头在 offset 16、数据基址 5748140，Electron asar shim 只读挂载即可。

## 1. 一等公民：最小定义文件 + 加载顺序

| 概念 | 最小定义 | 顺序/生效 | 证据 |
|---|---|---|---|
| bundle | npm 包 + `package.json` 的 `dsh.bundle.patch` 指向自己的 `cordis.patch.yml` | profile `dsh.profile.bundles` 按序叠加 → `cordis.patch.yml` → `--patch` | `~/.dsh/profiles/desktop/cordis.yml:1-4`；`~/.dsh/plugins/src/dsh-ops-exec-guard/package.json` |
| plugin | 一个 ESM 模块：`export const name` + `export function apply(ctx, config)`，或默认导出 `class extends Service` | 行被 Loader 挂载时调 apply；服务落在该 scope | `~/.dsh/plugins/src/dsh-ops-exec-guard/index.js:7-11`；`$D/dsh-agent-default-model/lib/index.js:17,69` |
| composition / profile | `cordis.yml` 是空数组，树全由补丁合成，同 id 后者覆盖 | bundles → patch → overlays | `cordis.yml:1-5` |
| agent preset | `- insert: - id: preset-x / name: '@deepseek-ai/dsh-agent-preset' / config: {id, order, plugins: [...]}` | 注册表启动时建独立 scope + 内存 Loader 树；改动只影响之后创建的 agent；会话日志存 preset id | `$D/dsh-web-app/presets/cordis.patch.yml:4-9`；`$D/dsh-agent-preset/README.zh.md:12,40-48`；`$D/dsh-agent-preset-registry/README.zh.md:46,56` |
| skill | `<root>/<name>/SKILL.md` 或 `<root>/<name>.md`，frontmatter 必填 `name`/`description` | rank 100 项目 `.dsh/skills` → 200 `.agents/skills` → 300 customSkillDirs → 400 `~/.dsh/skills` → 500 `~/.agents/skills`，近层胜出 | `$D/dsh-skill-filesystem/README.zh.md:36,48-54,56`；`$D/dsh-skill/README.zh.md:53,84` |
| tool | `ctx.tools.register(defineTool({name, description, parameters, output, execute}))` | 注册即入该 scope 工具表 | `$D/dsh-tool-goal/lib/index.js:263-273`；api-catalog `tools:3993` |
| MCP | 一行 `dsh-mcp-client`：`serverName` + `transport: stdio\|streamable-http`（+ command/url/headers） | 连上即注入 `mcp__<server>__<tool>` | `$D/dsh-mcp-client/README.zh.md:28,34-53,57`；api-catalog `mcpResources:2007` |
| subagent | `dsh-subagent` + spawn provider + `dsh-tool-subagent(provider: spawn, toolName: subagent)` | 工具立即回 childId，后台 activation 结算后通知父级 | `$D/dsh-subagent/README.zh.md:34-43,45,61` |
| teammate | `dsh-session-persistence-jsonl` + `dsh-experimental-agent-team` + tool 包 | Lead 建成员，roster：running/inactive/provisioning/failed | `$D/dsh-experimental-agent-team/README.zh.md:38-45,60-62` |
| session | 仅追加事件日志，无持久化后端时只在内存 | 每 agent 一份；jsonl 后端落盘 | `$D/dsh-session/README.zh.md:12`；`$D/dsh-session-persistence-jsonl/README.zh.md:12` |
| goal | 由 session 日志自持的 goal 记录，驱动自动续轮 | activate/pause/resume/complete/block/disarm/clear | `$D/dsh-goal/README.zh.md:26`；api-catalog `goals:1550` |

## 2. 多 agent 机制，以及外部服务能插哪

| 机制 | 接口 | 外部参与度 |
|---|---|---|
| subagent 派发 | `ctx.subagents.startActivation({provider,label,request,signal,delivery})` → `{childId,result,dispose}`；事件 `subagent/start`:5178 | 插件可用 `registerProvider` 加自定义后端；但独立 preset、后续消息续跑只有进程内 spawn |
| team | `ctx.agentTeams.spawnTeammate / sendMessage / createTask / updateTask / waitForChange / interrupt` | 纯进程内；不支持跨进程协调、独立工作目录、自动释放 owner（README:32） |
| goal 续跑 | `ctx.goals.*` + `command-goal` 语法 + 事件 `goal/changed`:4970 | 只能经工具/命令驱动；无「外部 service 直接续跑」口 |
| session 隔离 | `ctx.agents.create/resume/list`、每 agent 独立 session | 只能进程内；外部只能经 SDK/CLI 拿到 sessionId |
| 消息总线 | `agent/inbox/{inserted,claimed,discarded}:4690`、Steer 到最近 step 边界 | 订阅可观测，注入需拿 agent 句柄 |
| 任务清单 | `agentTeams.createTask/updateTask`（依赖 + compare-and-set，重叠路径只告警） | 仅 team 内成员可写 |

外部服务真正能用的四条缝：

1. **插件 HTTP route**：`ctx.webServer.register({kind:'exact|prefix', path, handler})`；服务器本身不提供鉴权，route owner 自理（`$D/dsh-host-webserver/README.zh.md:59-63,132`），实例见 `$D/dsh-experimental-inspector/lib/index.js:2422-2430`（自调 `ctx.connection.authorizeIndex`）。
2. **RPC / Remote 方法**：`dsh-api-gateway` 的 Typert RPC + `@Remote` 方法（如 `llm.listProviders`、`schedule.*`），非 owner peer 的权限由 `dsh-api-remote-access` 按 role/policy 判定（README:12）；挂载点 `$D/dsh-client-connection/lib/index.js:871,1058`。
3. **stdio JSON-RPC**：`dsh-sdk-jsonrpc-server` 让进程外客户端按 `sessionId` 开会话、投提示词、收事件流，支持 `session/resume`（README:12,28,32,60）。
4. **CLI**：`dsh --profile headless "任务"` + `--json` 行事件流，进程不开端口（`$D/dsh-headless/README.zh.md:12`）。

事件面（88 个）：`llm/stream`[waterfall]:5018、`llm/models-updated`:5010、`agent/pre-step`:4698、`agent/request-error`:4706、`tools/pre-execute`:5226、`workspace/session-stop`:5322。`[待补: ctx.webhookRuntime:4274 只有 register/dispatch 签名，外部投递语义未取证]`

## 3. 模型目录与路由的消费面

- **读取路径**：`ctx.llm.listModels(provider)` / `resolveModelInfo()`（`$D/dsh-llm/lib/index.js:2086`）。profile 的 `models` 列表**整体替换**安装版目录，`modelOverrides` 只改个别模型（`$D/dsh-llm-pi-ai/README.zh.md:83,103`）。
- **发现**：目录未描述的路由才会去问端点，`openai-completions` 用 `GET {baseURL}/models` + bearer（pi-ai README:119）→ ModelBus 的 `/v1/models` 直接被吃。
- **字段白名单**（`$D/dsh-llm/lib/index.js:2124-2168`，`normalizeModelInfo`）：`provider, id, name, description?, inputModalities?, context.contextWindow?, defaultMaxTokens?, systemPromptUpdate?, toolUpdate?, reasoning{efforts[], defaultEffort?}`；额外只有选择器的 `badge`（README:28，实际渲染见 `$D/dsh-tmux-context/lib/index.js:1773-1781`）。其余值一律 `INVALID_MODEL_INFO` 拒。
- **没被消费的**：`cost`/`vendor`/`capabilities`/`aliases`。证据：`$D/dsh-llm-pi-ai/lib/index.js:270-280` 明写「harness 从不读 pi-ai 的 cost 元数据，`replay.ts` 把它清零，没有消费者上报花费」；`$D/dsh-llm/lib/index.js:2172` 明写不做 clamp 也不做 alias。
- **ModelBus 现在投的正好等于消费面**：`tools/dsh_sync.py:333-343` 只写 `contextWindow / maxTokens / input / reasoningEfforts / compat` + 路由级 `displayName / retryPolicy / api / baseURL / apiKeyEnv`。再往上加字段宿主不会读。
- **按 agent 选模型/上游，今天四条路**：
  1. Host 默认：`agent-default-model` 服务（config `provider`+`model`[+`reasoningEffort`]），只回答「新 agent 用哪个」，不校验目录成员（README:28-57）；本机现为 `zcode-main`/`Gemini-AIS`（`cordis.patch.yml:4-8`）。
  2. session 级：GUI「设置→模型」的选择覆盖默认，记在顶层 session，子 session 继承，改设置只影响新 session（`$D/dsh-tool-subagent/README.zh.md:73-77`）。
  3. subagent 参数：`modelSelection:true` 才公开 `provider/model/reasoning_effort`，`modelDiscovery:true` 才注册 `list_subagent_models`（独立开关、默认关）；standard/ptc preset 已开（`$D/dsh-web-app/presets/standard.patch.yml:94-100`）。且只能在「父 agent 当前路由」或「已记录路由列表」内选。
  4. preset 级：preset 里**没有** `model` 字段（`presets/*.patch.yml` 全表无该键），只能塞模型相关服务插件进 `plugins`。
  → 「按 agent 选不同上游」只能落到 provider 粒度（一个 provider = 一个 baseURL），没有 per-agent 上游组/权重/冷却。

## 4. ModelBus 想当模型控制面：最小插件形态

```
~/.dsh/plugins/src/modelbus-control/            # 或私有 npm 包，plugin_manager install_bundle 装进 profile
├─ package.json    {"dsh":{"bundle":{"patch":"./cordis.patch.yml"}}}
├─ cordis.patch.yml
└─ index.js
```

```yaml
# cordis.patch.yml
- insert:
    - id: modelbus-control
      name: '@local/modelbus-control'
      config: { gateway: 'http://127.0.0.1:7871', adminTokenEnv: MODELBUS_ADMIN_TOKEN }
```

```js
// index.js —— 骨架，25 行内
export const name = 'modelbus-control';
export function apply(ctx, cfg) {
  // 1) 目录：ModelBus 的 /v1/models 已能被 pi-ai 发现；要自建路由才 registerAdapter
  //    （ctx.llm.registerAdapter(['modelbus'], adapter) 后 ctx.emit('llm/models-updated','modelbus')）
  // 2) 别名/路由/冷却：llm/stream 是 waterfall，专门给 routing 用（api-catalog:5021）
  ctx.on('llm/stream', async function* (options, next) {
    const pick = await route(cfg, options);                       // POST /admin/route
    yield* next.call(this, pick ? { ...options, provider: pick.provider, model: pick.model } : options);
    observe(cfg, options, pick).catch(() => {});                  // POST /admin/observe，供冷却/预算
  });
  // 3) 控制面 HTTP：宿主 webserver 不鉴权，自己校验
  ctx.effect(() => ctx.webServer.register({
    kind: 'prefix', path: '/api/modelbus',
    handler: (req, res) => {
      if (!authorized(req, cfg)) { res.writeHead(401).end(); return; }
      proxy(req, res, cfg.gateway);                               // /catalog /alias /cooldown /budget
    },
  }));
  // 4) 可选：给模型一个 modelbus_status 工具（ctx.tools.register(defineTool({...}))）
}
```

注册面：服务/工具名取 `modelbus-control`、`modelbus_status`；要暴露的 ModelBus 端点 `GET /v1/models`（发现）、`POST /admin/route`（候选→选定，回 provider/model/reasoningEffort）、`GET /admin/catalog`（别名+能力）、`POST /admin/observe`（成败/延迟回写冷却）、`GET /admin/budget`；订阅宿主事件 `llm/models-updated`、`agent/request-error`、`goal/changed`。

## 5. DSH 侧没有的能力 → ModelBus 保留自研

| 能力 | DSH 现状证据 | 归属 |
|---|---|---|
| 跨上游竞速/择优 | 一次请求只解析到一个 provider+model，无候选集（`$D/dsh-llm/lib/index.js:2187-2200`）；retry 只重跑同一路由（`$D/dsh-llm-retry/README.zh.md:133-134`） | ModelBus |
| 冷却记忆 | `retryPolicy` 是静态配置（code 集 + 退避），无跨请求失败记忆；always 模式还会重试永久性失败（同上:134） | ModelBus |
| 额度/预算台账 | 只有错误码 `QUOTA`/`ACCOUNT_QUOTA`（llm:137-140）；`tokenMeter` 只做确定性估算（README:12,28） | ModelBus |
| 计价与花费 | pi-ai 的 cost 元数据被丢弃、无人消费（pi-ai:270-280） | ModelBus |
| 别名/改名 | DSH 明确 no clamping or aliasing（llm:2172），改名语义在网关（ModelBus CHANGELOG:48） | ModelBus |
| 目录/别名的写回 | 注册表不写声明，新建/覆盖只能 bundle 补丁 + `plugin_manager`（registry:48） | ModelBus 生成 YAML |
| 外部调度器 | 无「外部调度器」沙箱；team 不支持跨进程协调（team:32） | ModelBus 走 CLI/JSON-RPC，不进宿主 |
| 每 agent 独立工作目录 | team:32 | 保留在 ModelBus 一侧 |
