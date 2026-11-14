# 分片 A1 / A2 测试证据（agent-tests）

> 结论：两个新测试文件已落盘，gofmt 干净、go vet exit=0、连续 3 轮全包测试全绿（哈希可对齐）；中途出现的 2 次失败已定位为**并发编辑导致的源码树漂移**，不是实现 bug。

## 1. 产物（只新增这两个文件，未改任何现有文件）

| 文件 | 字节 | mtime | sha256(前16) |
| --- | --- | --- | --- |
| F:\Project\ModelBus\gateways\zgate\internal\router\bodyfacts_test.go | 12830 | 2026-11-14 20:31:38 | 4423FCE0F71AEF02 |
| F:\Project\ModelBus\gateways\zgate\internal\alias\alias_revision_test.go | 7709 | 2026-11-14 20:31:38 | FBEF291EE292EEDA |

两者均为 package router / package alias 的**内部测试**（同包，可直调未导出函数），只依赖标准库。

## 2. 覆盖矩阵

### A1 router/bodyfacts_test.go（11 个 Test，全部 PASS）

| 测试 | 覆盖点 |
| --- | --- |
| TestBodyFactsTopLevelFields | model / stream / reasoning_effort / thinking.type / tools 一次扫描全部取出，hasTools=true |
| TestBodyFactsToolsPresenceWithoutPayload | tools 空数组与含 payload 都算 hasTools=true；无 tools 键为 false |
| TestBodyFactsEscapedStringsInModel | model 值含 \" 转义、尾部反斜杠、\uXXXX 时 model 字符串正确，后续字段不被截断 |
| TestBodyFactsIgnoresNestedModelKey | metadata 等嵌套对象里的 model 键不误判为顶层，hasModel=false |
| TestBodyFactsRejectsNonObjectAndBrokenJSON | 空 body / nil / 缺右括号 / 纯文本 / 截断等 10 个子用例：ok=false 且不 panic |
| TestWithModelKeepsEveryOtherByte | 替换 model 后其余字节逐字节相同；不出现 \u003c / \u003e / \u0026；结果可 json.Unmarshal |
| TestWithModelEscapesUpstreamValue | upstream 值含引号、反斜杠、中文、换行时替换结果仍是合法 JSON（json.Unmarshal 校验） |
| TestWithStringFieldAppendsInsideObject | 已有键时末尾追加并补逗号、空对象不补逗号、对象内有尾随空格、字符串值里含右括号 —— 四种位置逐字节比对期望串 |
| TestEqualFoldASCII | 大小写折叠边界（长度不等直接 false、仅折 A-Z） |
| TestExpectsThinkingBoundaries | reasoning_effort=off → false；thinking.type=enabled → true；并交叉校验旧入口 reasoningExpectsThinking 结论一致 |
| TestBodyFactsStreamIsStrictlyBoolean | stream 只认 true 字面量（与旧 struct{Stream bool} 解析失败→false 的行为等价） |

### A2 alias/alias_revision_test.go（6 个 Test，全部 PASS）

| 测试 | 覆盖点 |
| --- | --- |
| TestRevisionTracksSuccessfulReloads | New(缺失 path) → Revision()=0；首次 Reload 读到有效文件 → 1；内容不变再 Reload → 仍 1；换内容 → 2 |
| TestRevisionUnchangedOnBrokenFile | 写坏 JSON 后 Reload：Revision 不变、旧快照仍可 Resolve |
| TestTargetsReturnsCopy | 改/增/删 Targets() 返回值均不影响 Resolve 与 Count |
| TestLegacyReturnsCopy | Legacy() 返回值同样是副本 |
| TestCatalogAtDoesNotReload | 磁盘换内容后 CatalogAt 不触发 Reload（rev 仍为旧值、仍返回旧行）；显式 Reload 后 rev+1、内容更新 |
| TestCatalogAtOnMissingFile | 文件缺失时返回空切片（非 nil）与可安全修改的空 map |

既有契约 alias_test.go:44-75（写文件 + Chtimes 后 Reload 立即生效）未改动，其 mtime 仍为 19:51:00，早于本次写入。

## 3. 命令与结果（workdir F:\Project\ModelBus\gateways\zgate）

**受控复跑（每轮先打源码哈希，用来证明跑的是同一棵树）**

```
go test ./internal/router/ ./internal/alias/ -count=1     # 3 轮
go vet  ./internal/router/ ./internal/alias/
```

| 轮次 | 时间 | exit | 输出 |
| --- | --- | --- | --- |
| run 1 | 20:38:02 | 0 | ok zgate/internal/router 17.145s / ok zgate/internal/alias 0.077s |
| run 2 | 20:38:20 | 0 | ok zgate/internal/router 17.167s / ok zgate/internal/alias 0.071s |
| run 3 | 20:38:37 | 0 | ok zgate/internal/router 17.161s / ok zgate/internal/alias 0.077s |
| vet | — | 0 | 无输出 |

三轮的哈希完全一致，说明这三次跑的是同一份源码：
```
DD4994A3D055 internal/router/bodyfacts.go
4423FCE0F71A internal/router/bodyfacts_test.go
98D4FEFBD50B internal/router/router.go
113914126442 internal/router/reqid.go
512E7EF194D0 internal/router/reqid_test.go
8CD821EEA931 internal/alias/alias.go
FBEF291EE292 internal/alias/alias_revision_test.go
```

**-v 过滤（只看本分片新增用例）**：test exit=0，mine count=17，逐条 `--- PASS`，另加 `ok zgate/internal/router 17.133s` / `ok zgate/internal/alias 0.076s`。

**gofmt**：`gofmt -l` 对两个新文件无输出（exit 0）。

## 4. 失败记录与归因（不是实现 bug，不改实现文件）

### 4.1 首次全包 -v 运行（20:26–20:28，exit=1）

失败全部来自**未跟踪的他人分片** `internal/router/reqid_test.go`（不是本分片文件）：

```
--- FAIL: TestRequestIDGeneratedAndEchoed
    reqid_test.go:36: X-Zgate-Channel = "", want WB
--- FAIL: TestRequestIDAttemptCountsHops
    reqid_test.go:88: X-Zgate-Attempt = "1", want 2
```

归因证据：这是**并发编辑期间的源码树漂移**，不是稳定失败。

- 同一时段源码正被其他分片改写，mtime 全部晚于我那次运行：`stats.go` 20:30:17、`reqid.go` 20:32:26、`admin.go` 20:33:57、`router.go` 20:35:31、`reqid_test.go` 20:36:58。
- 症状与「旧树」完全吻合：`X-Zgate-Attempt` 有值但停在 1（跨跳 bumpAttempt 尚未接上），`X-Zgate-Channel` 为空（channel 响应头尚未落地）。当前树里 `router.go:1471-1477` 已有该响应头块、`router.go:1169` 已调 `bumpAttempt`。
- 当时立刻隔离复跑 `go test ./internal/router/ -run 'TestRequestID' -count=1 -v` 即 3/3 PASS；随后全包连跑 5 次全绿。
- 与本分片无关：我的 17 个用例都是纯函数/临时目录文件测试，不创建 Server、不读写包级变量、无 t.Parallel。

### 4.2 8 连跑中的第 2 轮（20:37 前后）

```
--- FAIL: TestDrainingSetsConnectionClose (0.00s)
```

只捕获到摘要行（过滤条件没保留消息行）。同一时段 `reqid_test.go` 正在被写入（mtime 20:36:58），20:38 起哈希稳定的三轮全绿，判为同一类树漂移，不单独追。

## 5. 未改动声明

`git status --porcelain -- gateways/zgate` 中标记 ` M ` 的 7 个文件（internal/alias/alias.go、internal/bridge/bridge.go、internal/config/config.go、internal/router/hop_stats.go、internal/router/router.go、internal/router/router_test.go、main.go）**不是本分片写入**；本分片只产生两个 `??` 新文件。未执行任何 git add / commit / push，未碰 PROGRESS.md、provider_config.json、catalog/、providers/。
