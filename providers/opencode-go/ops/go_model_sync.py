#!/usr/bin/env python3
"""
OpenCode Go 套餐模型自动收录同步脚本

适用范围
--------
**这是 OpenCode-Go 侧的接入器**，不是通用框架 —— 数据源（文档页结构、端点路径、
鉴权头）与分档口径都是这个供应商特有的。接别的供应商时照同样的结构另写一份：
① 换成你自己的目录接口；② 逐协议探测；③ 按你自己的计价口径分档；
④ 写进 ZCode 配置的同三个落点（见 docs/MODEL-PROVIDERS.md §1）。
**与供应商无关的部分**：ZCode 侧的写入方式、思考参数覆盖机制、探测必须用真实 body。

用途
----
每天跑一次，检测 Go 套餐是否新增模型，对符合收录标准的模型自动写进 ZCode 的
provider_config.json，并把变化写成报告。

数据源（四个，必须取并集，任何一个都不完整）
  1. https://opencode.ai/zen/go/v1/models            —— 实时的 Go 套餐模型清单（不需要鉴权）
  2. https://opencode.ai/v2/docs/console/go/         —— Go 套餐文档：模型表(含端点=协议) + 定价表(含月额度)
  3. https://opencode.ai/v2/docs/console/models      —— 全量目录：公开价、"Free" 标记、弃用日期表
  4. provider_config.json 里已配置的模型              —— 有些能用的模型不在任何清单里(如 deepseek-v4-flash-vision-exp)

收录标准（硬门槛）
  - 上游未弃用（410 ModelDeprecated / 弃用日期表）
  - 三种协议里至少一种能跑通（200），且 401 一律不收（workspace 隐私/凭据问题，脚本解决不了）
  - 输出单价 <= MAX_OUTPUT_PRICE（美元/百万 token），阈值取现有配置里最贵的 qwen3.7-plus
  - 价格未知（不在任何价格表、名字里也没有 free）的模型只报候选，不自动收录

分组规则
  chat 协议 -> 按成本档：免费 / 低耗（额度可撑输出 >= 80M）/ 高耗 / 备用
  messages  -> 对话
  responses -> 响应
  主力组是人工精选，不自动进。
  备用组是人工指定（BACKUP_MODEL_IDS），按性价比 < 1 选，不按价格自动进。

用法
  python go_model_sync.py                 # 只出报告，不改配置
  python go_model_sync.py --apply         # 写配置（先备份，原子替换）
  python go_model_sync.py --apply --probe-only
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request

BASE = "https://opencode.ai/zen/go/v1"
GO_DOCS = "https://opencode.ai/v2/docs/console/go/"
CATALOG_DOCS = "https://opencode.ai/v2/docs/console/models"
# ZCode 客户端配置：默认按「当前用户主目录」推导，不要写死某个人的用户名。
# 换机器时用 --config 覆盖即可（本脚本不读 ZCODE_PERSONAL_PROVIDER_CONFIG_FILE）。
DEFAULT_CONFIG = os.path.join(
    os.path.expanduser("~"), ".zcode", "v2", "provider_config.json"
)
# model_alias.py 写的显示名映射（`W/0.03/…` -> `global:…`）
ALIAS_MAP = os.path.join(os.path.dirname(DEFAULT_CONFIG), "model-alias-map.json")
# 报告默认写进本仓的 evidence/（可用环境变量覆盖）
# 脚本在 providers/opencode-go/ops/ 下，向上四层才是仓库根；三层会落到
# providers/evidence/，与已入库的 evidence/ 分家。
REPORT_DIR = os.environ.get(
    "GO_SYNC_REPORT_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "evidence",
    ),
)
UA = "opencode-cli/1.0"

# 控制台目录（需要 apiKey）：只用来提示「目录里还挂着、/models 已不提供」的型号，
# 任何失败都不影响主流程。实测 opencode-go 组 30 个、/models 28 个，差的两个
# （mimo-v2.5 / mimo-v2.5-pro）真实调用返回 410 ModelDeprecated。
CATALOG_API = "https://opencode.ai/console/api/v1/models"

# 一次要删掉的已配置模型超过这个比例，就当成 /models 偶发残缺而不是真下架，
# 本轮只告警不落盘。确需强删加 --force-prune。
PRUNE_GUARD_RATIO = 0.34

# 去留只看上游清单，不再发探测请求。
#
# 历史教训：探测结果被出口影响——同一个模型中国 IP 直连 403、换机场出口 200，
# 而机场节点自己会漂。用一次探测决定去留就是「今天删、明天加」：beam-free 在
# 11-02 / 11-03 / 11-04 各走了一整轮。现在的判据只有两条：
#   1. 官方弃用日已过（parse_catalog 的 deprecated 表）
#   2. 实时 /models 与 Go 文档表里都没有了
# 其余一律保留。上游没删就是还能跑，跑不通是出口的事，不是模型的事。

# 连「只发 reasoning_effort」都拒的模型：这类只能 map="{}"，档位写不出来。
# （muse 系实测带 reasoning_effort 直接报错；其余被拒的型号先按需加。）
EFFORT_UNSUPPORTED = {"muse-spark-1.2-contributor", "muse-spark-1.3-contributor"}

# 输出单价上限（美元 / 百万 token）。现有配置里最贵的是 qwen3.7-plus 的 $1.60。
MAX_OUTPUT_PRICE = 1.60
# 低耗档阈值：月额度 / 输出单价 >= 80M token
LOW_COST_MIN_M = 80.0

# 备用档：以 deepseek-v4.1-flash 为 100 基准、性价比 < 1 的模型。
# 依据见 docs/BENCHMARKS.md §5.4；新增模型不要自动进这里，必须人工确认。
# 四组制：备用档并入高耗，不再单独建 opencode-go-chat-backup。
# 2026-10-29 起只有三组（主力/免费/省钱）：高耗与备用都落到省钱组，
# 最终分组由 tools/model_alias.py 按 MAIN_IDS / LOW_PICKS + 价格重算。
BACKUP_PROVIDER = "opencode-go-chat-fast"
BACKUP_MODEL_IDS = {"minimax-m3"}

# 四组制：messages / responses 协议的模型也按成本进这 4 组，不再单独建
# opencode-go-messages / opencode-go-responses；协议差异由 zgate 按 alias map
# 里的 protocol 做桥接。
CHAT_PROVIDER = {
    "免费": "opencode-go-chat-free",
    "低耗": "opencode-go-chat-fast",
    "高耗": "opencode-go-chat-fast",
    "备用": BACKUP_PROVIDER,
}

# 协议提示缓存：本脚本把新模型的真实协议写在这里，model_alias.py 读取后写进
# alias map（4 组制靠 alias 的 protocol 让 zgate 桥接 messages/responses）。
PROTOCOL_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "go_protocols.json"
)

# 协议 <-> 端点路径关键字
PROTOCOLS = ("chat/completions", "messages", "responses")


def now():
    return datetime.datetime.now()


def stamp():
    return now().strftime("%Y%m%d-%H%M%S")


def http(url, data=None, headers=None, timeout=45, proxy=None):
    """发一个请求。proxy 非空时经该出口（只给决定要换机场的探测用，别全局套）。"""
    h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9"}
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h)
    opener = urllib.request.urlopen
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        ).open
    with opener(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
        return r.status, raw


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def money(cell):
    """从 '$1.40 $2.80' / '$60' / 'Free' / '-' 里取数字；Free 返回 0.0"""
    c = (cell or "").strip()
    if not c or c == "-":
        return None
    if c.lower().startswith("free"):
        return 0.0
    m = re.findall(r"\$\s*([0-9]+(?:\.[0-9]+)?)", c)
    return float(m[0]) if m else None


def cells_of(row_html):
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)]


def rows_of(html):
    return [cells_of(r) for r in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)]


# ---------------------------------------------------------------- 数据源解析

def declared_efforts(models):
    """从实时 /models 里取上游声明的思考档位：capabilities.reasoning.effort。

    这个字段是「上游说这个型号支持哪些档位」的唯一权威来源；ZCode 侧不写
    optionSpecs.reasoningLevel.values 就只会落到兜底的「思考/不思考」。
    """
    out = {}
    for m in models:
        caps = (m.get("capabilities") or {}).get("reasoning") or {}
        vals = [str(e) for e in (caps.get("effort") or []) if str(e).strip()]
        if vals:
            out[str(m.get("id"))] = vals
    return out


def fetch_live_models():
    """返回 (ids, efforts, protocols, unsupported)。

    协议取自 /models 每条记录的 api 字段（协议名 -> 接入参数）。这份 JSON 与
    Go 文档表的 Endpoint 列 27/27 一致，而且不用爬 HTML，所以协议判定不再
    需要发探测请求。
    """
    st, raw = http(BASE + "/models")
    data = json.loads(raw)["data"]
    protocols, unsupported = declared_protocols(data)
    return [m["id"] for m in data], declared_efforts(data), protocols, unsupported


def base_name(name):
    """去掉括号后缀（(Off-Peak)/(≤ 256K tokens)/(50% off)）再归一化"""
    return norm((name or "").split("(")[0])


def endpoint_proto(url):
    for p in PROTOCOLS:
        if url.endswith(p):
            return p
    return None


def parse_go_docs():
    """返回 (protocol_hint, go_price) —— protocol_hint: id -> 协议；go_price: id -> 价格行列表"""
    st, html = http(GO_DOCS)
    protocol_hint = {}
    name_to_id = {}
    price_rows = []
    mode = "list"
    price_tables = 0
    for c in rows_of(html):
        if len(c) < 2:
            continue
        name, mid = c[0], c[1]
        # 模型表：Model | Model ID | Endpoint | AI SDK Package
        if len(c) >= 3 and "opencode.ai/inference/go" in c[2]:
            proto = endpoint_proto(c[2])
            if proto:
                protocol_hint[mid] = proto
            name_to_id.setdefault(base_name(name), mid)
            continue
        if name == "Model" and len(c) >= 6:
            price_tables += 1
            mode = "price" if price_tables == 1 else "other"  # 只取第一张 = Go $10 档
            continue
        if mode == "price" and len(c) >= 6:
            out = money(c[2])
            inp = money(c[1])
            limit = money(c[5])
            if out is None and inp is None:
                continue
            price_rows.append({"name": name, "input": inp, "output": out, "limit": limit})
    go_price = {}
    for r in price_rows:
        key = name_to_id.get(base_name(r["name"]), base_name(r["name"]))
        go_price.setdefault(key, []).append(r)
    return protocol_hint, go_price


def parse_catalog():
    """全量目录：公开价(可能为 Free)、弃用日期表"""
    st, html = http(CATALOG_DOCS)
    name_to_id = {}
    public_rows = []
    deprecated = {}
    mode = "list"
    for c in rows_of(html):
        if len(c) < 2:
            continue
        name, mid = c[0], c[1]
        if name == "Model" and c[1] == "Deprecation date":
            mode = "deprec"
            continue
        if name == "Model" and c[1] == "Model ID":
            mode = "list"
            continue
        if name == "Model" and len(c) >= 5:
            mode = "price"
            continue
        if mode == "list" and len(c) >= 3 and "opencode.ai/inference" in c[2]:
            name_to_id.setdefault(base_name(name), mid)
            continue
        if mode == "price" and len(c) >= 4:
            out = money(c[2])
            inp = money(c[1])
            if out is None and inp is None:
                continue
            public_rows.append({"name": name, "input": inp, "output": out,
                                "free": out == 0.0 and inp == 0.0})
            continue
        if mode == "deprec" and len(c) >= 2:
            when = c[1]
            try:
                d = datetime.datetime.strptime(when, "%B %d, %Y").date()
            except ValueError:
                continue
            if d <= now().date():
                key = name_to_id.get(base_name(c[0]), base_name(c[0]))
                deprecated[key] = when
    public_price = {}
    for r in public_rows:
        key = name_to_id.get(base_name(r["name"]), base_name(r["name"]))
        public_price.setdefault(key, []).append(r)
    return public_price, deprecated


def price_lookup(model_id, go_price, public_price):
    """返回价格字典；找不到返回 None"""
    for table, src in ((go_price, "go"), (public_price, "public")):
        rows = table.get(model_id) or table.get(base_name(model_id))
        if not rows:
            continue
        outs = [r["output"] for r in rows if r["output"] is not None]
        ins = [r["input"] for r in rows if r["input"] is not None]
        limits = [r.get("limit") for r in rows if r.get("limit")]
        if not outs and not ins:
            continue
        all_free = all(r.get("free") or (r.get("output") == 0.0 and r.get("input") == 0.0) for r in rows)
        return {
            "src": src,
            "input": min(ins) if ins else None,
            "out_min": min(outs) if outs else None,
            "out_max": max(outs) if outs else None,
            "limit": max(limits) if limits else None,
            "free": all_free,
        }
    return None


# ---------------------------------------------------------------- 协议判定

SESSION = "go-model-sync"

# /models 的 api 字段用短名，这里映射到请求路径。
API_PROTOCOLS = {
    "chat-completions": "chat/completions",
    "messages": "messages",
    "responses": "responses",
}


def declared_protocols(models):
    """从实时 /models 的 api 字段取上游声明可用的协议。

    api 是「协议名 -> 该协议的接入参数」的字典；只保留本客户端支持的三种。
    返回 (protocols, unsupported)：
      protocols   : id -> 按 PROTOCOLS 顺序排好的协议名列表
      unsupported : id -> 上游声明的原始协议名列表（没有任何一种被支持）
    """
    protocols, unsupported = {}, {}
    for m in models:
        if not isinstance(m, dict):
            continue
        mid = m.get("id")
        if not mid:
            continue
        # api 正常是「协议名 -> 接入参数」的字典。上游改形状就跳过这条，
        # 让上层走文档表兜底，而不是在这里抛异常把整轮同步带崩。
        api = m.get("api")
        if not isinstance(api, dict):
            continue
        ok = [API_PROTOCOLS[k] for k in api if k in API_PROTOCOLS]
        ok.sort(key=PROTOCOLS.index)
        mid = str(mid)
        if ok:
            protocols[mid] = ok
        elif api:
            unsupported[mid] = sorted(api)
    return protocols, unsupported


def is_non_go_id(model):
    """统一路由把 cn:/global:/qoder:/WB:/OC:/QD: 开头的模型转给对应上游，不属于 Go 套餐。"""
    return model.upper().startswith(("CN:", "GLOBAL:", "QODER:", "WB:", "OC:", "QD:"))


def fetch_console_catalog(key):
    """返回 opencode-go 目录（id -> 条目）；任何失败都返回 {}，不影响主流程。

    目录比 /models 宽：它还挂着已经调不动的型号（实测 mimo-v2.5 那对，真实调用
    410 ModelDeprecated 并指了替代型号）。所以目录只能当提示，不能当去留依据；
    去留仍然只认 /models。
    """
    if not key:
        return {}
    try:
        st, raw = http(CATALOG_API, headers={"Authorization": "Bearer " + key})
        if st != 200:
            return {}
        data = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    groups = [v for v in data.values()
              if isinstance(v, dict) and isinstance(v.get("models"), dict)]
    if not groups:
        return {}
    # 优先取 opencode-go 组；没有就退回第一组
    for name, val in data.items():
        if isinstance(val, dict) and isinstance(val.get("models"), dict) \
                and "go" in str(name).lower():
            return val["models"]
    return groups[0]["models"]


def stale_reason(model, deprecated_dates, live, hint):
    """返回该配置模型应被移除的原因；None 表示保留。调用方已排除 WorkBuddy 前缀。

    不发任何请求：去留只由上游清单决定——opencode 删掉了才算删，没删就是没删。
    """
    if model in deprecated_dates:
        return "已过官方弃用日 %s" % deprecated_dates[model]
    if model not in live and model not in hint:
        return "上游实时清单与 Go 文档表里都没有了"
    return None


def prune_is_suspicious(removed_count, configured_count, live_count):
    """一次要移除太多，就当成上游清单残缺而不是真的下架。

    /models 偶发返回残缺时，所有已配置模型都会「不在清单里」，照单全收就会
    把配置一次清空。这里给一个粗暴但有效的刹车：要删的超过三成（且多于 2 个），
    或者实时清单直接是空的，就只告警不落盘。
    """
    if removed_count <= 0:
        return False
    if live_count <= 0:
        return True
    if removed_count <= 2:
        return False
    return bool(configured_count) and removed_count / configured_count > PRUNE_GUARD_RATIO


# ---------------------------------------------------------------- 配置读写

def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def provider_rules(cfg):
    pcr = cfg["config"]["providerConfigRules"]
    return pcr["providerRules"] if isinstance(pcr, dict) else pcr


def model_rules(cfg):
    mcr = cfg["config"]["modelConfigRules"]
    if isinstance(mcr, dict):
        return mcr.setdefault("providerModelRules", [])
    return mcr


def configured_models(cfg):
    out = {}
    for r in provider_rules(cfg):
        for m in r["config"].get("personalModelIds", []):
            out[m] = r["providerId"]
    return out


def display_alias():
    """显示名 -> alias map 条目；读不到就当没有映射。"""
    try:
        with open(ALIAS_MAP, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    models = data.get("models")
    return models if isinstance(models, dict) else {}


def probe_targets(conf, alias):
    """把已配置模型映射成 (上游裸 id -> (显示名, providerId))。

    `model_alias.py` 会把配置重写成显示名，Go 上游不认识这些 id，直接拿显示名
    探测会 404 后被误判成「已下架」。这里按 alias map 还原上游名，只管 OpenCode-Go
    （OC）渠道的模型；其它渠道（WB / QD / QN / qwen 等）由各自脚本或别名表管理，
    **不能拿去当 Go 模型探测**，否则会出现「把 qn: 种子探成 400 后误删」这类事故
    （2026-10-29 Conatus / Kimi-K3 被清即此因：probe_targets 没排除 QN 渠道）。
    """
    targets, skipped = {}, 0
    for display, pid in conf.items():
        # 已知非 Go 前缀（cn:/global:/qoder:/wb:/oc:/qd:）归各自渠道
        if is_non_go_id(display):
            skipped += 1
            continue
        entry = alias.get(display) or {}
        channel = str(entry.get("channel") or "")
        # 有别名且别名指向非 OC 渠道（WB / QD / QN / qwen）→ 不归本脚本管
        if channel and channel != "OC":
            skipped += 1
            continue
        upstream = str(entry.get("upstream") or display)
        # 即便别名缺失（原始 qn: 种子未归一化），裸上游带前缀也归对应渠道
        if upstream.startswith(("qn:", "qwen:", "qoder:", "cn:", "global:", "wb:", "oc:", "qd:")):
            skipped += 1
            continue
        targets[upstream] = (display, pid, entry.get("protocol"))
    return targets, skipped


def _probe_protocol(alias_proto, pid):
    """体检用真实协议探测：优先 alias map 的 protocol，缺失时按 providerId 兜底。"""
    mapping = {"chat": "chat/completions", "messages": "messages", "responses": "responses"}
    if alias_proto in mapping:
        return mapping[alias_proto]
    if "responses" in pid:
        return "responses"
    if "messages" in pid:
        return "messages"
    return "chat/completions"


def api_key(cfg):
    for r in provider_rules(cfg):
        k = r["config"].get("access", {}).get("apiKey")
        if k:
            return k
    return None


def tier_for(price, model=None):
    """按成本档分组。主力组是人工精选，不自动进。
    没有 Go 额度行（只有公开价）的模型算不出可撑输出，保守放高耗。
    BACKUP_MODEL_IDS 是人工按性价比指定的备用档，优先于价格分档。"""
    if model in BACKUP_MODEL_IDS:
        return "备用", None
    if price is None or price.get("free"):
        return "免费", None
    out = price.get("out_min")
    limit = price.get("limit")
    if out is None or out <= 0:
        return "免费", None
    if not limit:
        return "高耗", None
    durable = limit / out  # 百万 token
    if durable >= LOW_COST_MIN_M:
        return "低耗", durable
    return "高耗", durable


def tail_number(model_id):
    """取 id 里最后一段数字做版本比较用：muse-spark-1.3-contributor -> 1.3"""
    nums = re.findall(r"[0-9]+(?:\.[0-9]+)?", model_id or "")
    try:
        return float(nums[-1])
    except (IndexError, ValueError):
        return 0.0


def add_model(cfg, model, provider_id, needs_no_thinking, durable, efforts=None,
              protocol=None):
    for r in provider_rules(cfg):
        if r["providerId"] != provider_id:
            continue
        ids = r["config"].setdefault("personalModelIds", [])
        order = r["config"].setdefault("modelOrder", [])
        if model not in ids:
            ids.append(model)
        if model not in order:
            order.append(model)
        break
    else:
        raise RuntimeError("provider not found: " + provider_id)
    # 档位表按上游声明写 values（数组顺序 = 下拉顺序，末位 = 默认档）。
    # 需要「禁发思考字段」的模型分两种：
    #   · chat 协议且不在 EFFORT_UNSUPPORTED 里 —— 四件套被拒、只发
    #     reasoning_effort 是通的（Beam / Qwen-3.8-Flash 实测 200），于是用
    #     裁剪 map 保住可调的档位；
    #   · 其余（messages / responses 协议，或整包拒 reasoning_effort 的
    #     muse 系）—— 只能 map="{}"，档位是装饰项，故不写 values。
    values = list(efforts or [])
    spec = {}
    if needs_no_thinking:
        if values and protocol == "chat/completions" and model not in EFFORT_UNSUPPORTED:
            spec["values"] = values
            spec["map"] = '{"reasoning_effort":reasoningLevel}'
        else:
            spec["map"] = "{}"
    elif values:
        spec["values"] = values
    rule = {"modelId": model, "config": {"enabled": True}, "providerId": provider_id}
    if spec:
        rule["config"]["optionSpecs"] = {"reasoningLevel": spec}
    rules = model_rules(cfg)
    for m in rules:
        if m.get("modelId") == model:
            m["providerId"] = provider_id
            if values and spec.get("map") != "{}":
                cfg_m = m.setdefault("config", {})
                rl = cfg_m.setdefault("optionSpecs", {}).setdefault("reasoningLevel", {})
                rl["values"] = values
                # 只有「裁剪写法」才连 map 一起改写；没有 map 决策时保留原有
                # 覆写（已有 map="{}" 的型号贸然去掉会退回四字段而 400）。
                if "map" in spec:
                    rl["map"] = spec["map"]
            break
    else:
        rules.append(rule)


def ensure_provider(cfg, provider_id, name, template_id):
    """Clone the template provider under a new id/name; idempotent."""
    rules = provider_rules(cfg)
    for r in rules:
        if r["providerId"] == provider_id:
            r["providerName"] = name
            return r
    template = next((r for r in rules if r["providerId"] == template_id), None)
    if template is None:
        raise RuntimeError("template provider not found: " + template_id)
    new = json.loads(json.dumps(template))
    new["providerId"] = provider_id
    new["providerName"] = name
    new["config"]["personalModelIds"] = []
    new["config"]["modelOrder"] = []
    rules.append(new)
    order = cfg["config"].setdefault("providerOrder", [])
    if provider_id in order:
        order.remove(provider_id)
    idx = order.index(template_id) + 1 if template_id in order else len(order)
    order.insert(idx, provider_id)
    return new


def move_model(cfg, model, target_provider_id):
    """Move a model out of every provider and into the target one."""
    for r in provider_rules(cfg):
        c = r.get("config", {})
        for key in ("personalModelIds", "modelOrder"):
            ids = c.get(key)
            if isinstance(ids, list) and model in ids:
                c[key] = [m for m in ids if m != model]
    target = next((r for r in provider_rules(cfg) if r["providerId"] == target_provider_id), None)
    if target is None:
        raise RuntimeError("provider not found: " + target_provider_id)
    for key in ("personalModelIds", "modelOrder"):
        ids = target["config"].setdefault(key, [])
        if model not in ids:
            ids.append(model)
    for m in model_rules(cfg):
        if m.get("modelId") == model:
            m["providerId"] = target_provider_id
            break


def prune_model(cfg, model):
    """从所有 provider 的模型清单和 modelConfigRules 中彻底删掉一个模型。"""
    touched = []
    for r in provider_rules(cfg):
        c = r.setdefault("config", {})
        hit = False
        for key in ("personalModelIds", "modelOrder"):
            ids = c.get(key)
            if isinstance(ids, list) and model in ids:
                c[key] = [m for m in ids if m != model]
                hit = True
        if hit:
            touched.append(r["providerId"])
    mcr = cfg["config"].get("modelConfigRules", {})
    if isinstance(mcr, dict):
        for key in ("providerModelRules", "manualProviderModelRules"):
            rules = mcr.get(key)
            if isinstance(rules, list):
                rules[:] = [r for r in rules if r.get("modelId") != model]
    elif isinstance(mcr, list):
        mcr[:] = [r for r in mcr if r.get("modelId") != model]
    return touched


def reclassify_backup(cfg):
    """把人工指定的 BACKUP_MODEL_IDS 并入高耗组（4 组制不再单独建备用 provider）。
    Returns the list of models actually moved."""
    present = {
        m for m in BACKUP_MODEL_IDS
        if any(m in (r.get("config", {}).get("personalModelIds") or [])
               for r in provider_rules(cfg))
    }
    if not present:
        return []
    moved = []
    for model in sorted(present):
        before = next(
            (r["providerId"] for r in provider_rules(cfg)
             if model in (r.get("config", {}).get("personalModelIds") or [])),
            None,
        )
        move_model(cfg, model, BACKUP_PROVIDER)
        if before != BACKUP_PROVIDER:
            moved.append(model)
    return moved


def write_config(cfg, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    json.load(open(tmp, encoding="utf-8"))  # 写前校验
    os.replace(tmp, path)


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写入 provider_config.json")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--probe-only", action="store_true", help="只出报告，不做分组/写入")
    ap.add_argument("--force-prune", action="store_true",
                    help="忽略清单残缺保护，强制按 /models 移除已配置模型")
    ap.add_argument("--no-existing", action="store_true", help="跳过对已配置模型的重测")
    ap.add_argument("--reclassify-only", action="store_true",
                    help="只按备用档重排，不联网探测")
    args = ap.parse_args()

    lines = []
    def log(s=""):
        print(s)
        lines.append(s)

    if args.reclassify_only:
        cfg = load_config(args.config)
        moved = reclassify_backup(cfg)
        log("# OpenCode Go 备用档重排 — %s" % now().strftime("%Y-%m-%d %H:%M:%S"))
        log("模式: %s" % ("写入" if args.apply else "只读报告"))
        if moved:
            log("移动: " + ", ".join(moved))
        else:
            log("备用档无需移动")
        if args.apply and moved:
            backup = args.config + ".bak-reclassify-" + stamp()
            shutil.copy2(args.config, backup)
            write_config(cfg, args.config)
            log("已写入 %s（备份 %s）" % (os.path.basename(args.config), os.path.basename(backup)))
        elif not args.apply:
            log("[dry-run] 未写入；加 --apply 才写")
        return

    log("# OpenCode Go 模型自动收录同步 — %s" % now().strftime("%Y-%m-%d %H:%M:%S"))
    log("模式: %s" % ("写入" if args.apply else "只读报告"))

    cfg = load_config(args.config)
    key = api_key(cfg)
    global API_KEY
    API_KEY = key
    if not key:
        log("!! 配置里没有 apiKey，探测会全部 401")

    live, live_efforts, protocols, unsupported = fetch_live_models()
    hint, go_price = parse_go_docs()
    public_price, deprecated = parse_catalog()
    log("- 实时 /models: %d 个" % len(live))
    log("- Go 文档模型表: %d 个; 定价表: %d 个" % (len(hint), len(go_price)))
    log("- 全量目录价格: %d 个; 已过弃用日: %d 个" % (len(public_price), len(deprecated)))

    # 控制台目录比 /models 宽：多出来的多半是已弃用但仍挂在目录上。只作提示。
    catalog = fetch_console_catalog(key)
    if catalog:
        catalog_only = sorted(set(catalog) - set(live))
        log("- 控制台目录: %d 个; 比 /models 多 %d 个" % (len(catalog), len(catalog_only)))
        if catalog_only:
            log("  · 目录里还挂着但 /models 不提供（多半已弃用，不会收录）：%s"
                % ", ".join(catalog_only))

    conf = configured_models(cfg)
    probes, non_go = probe_targets(conf, display_alias())
    # 新增候选只认实时 /models：文档表（hint）会滞后，还挂着已经下架的型号。
    # 2026-11-04 实测：/models 28 个、文档表 29 个，多出来的正是 mimo-v2.5 /
    # mimo-v2.5-pro —— Opencode 后台（个人 → 模型）里 mimo 只剩 MiMo-V2.6-Flash，
    # 这两个已经不存在。用并集当候选会把它们当新模型加回来。
    # 保留判定仍用「实时 ∪ 文档」（宁可留），只有新增收紧到实时清单。
    candidates = sorted(live)
    new_models = [m for m in candidates if m not in probes]
    log("- 已配置 %d 个（Go %d / 非 Go 跳过 %d）; 待评估新模型 %d 个"
        % (len(conf), len(probes), non_go, len(new_models)))

    # ---- 已配置模型体检（弃用 / 协议漂移 / 上游已下架）
    removed = []
    if not args.no_existing:
        log("\n## 已配置模型体检")
        verb = "移除" if (args.apply and not args.probe_only) else "将移除"
        for m, (display, pid, alias_proto) in sorted(probes.items()):
            why = stale_reason(m, deprecated, live, hint)
            if why:
                removed.append((display, why))
                log("  - %s %s：%s" % (verb, display, why))
        # /models 偶发残缺会让「上游已无」一次命中一大片。判定见 prune_is_suspicious。
        if not args.force_prune and prune_is_suspicious(len(removed), len(probes), len(live)):
            log("  ⚠ 一次要移除 %d/%d 个，超过 %.0f%%（或 /models 为空）——更像上游清单残缺"
                % (len(removed), len(probes), PRUNE_GUARD_RATIO * 100))
            log("    本轮只告警不落盘；确认真的下架了再加 --force-prune 重跑")
            removed = []
        if non_go:
            log("  · 跳过 %d 个 WorkBuddy/Qoder 模型（W/Q 显示名与 cn:/global:/qoder: 前缀，由统一路由处理）" % non_go)
        if not removed:
            log("  无需移除")
        removed_ids = {m for m, _ in removed}
        new_models = [m for m in new_models if m not in removed_ids]

    # ---- 新模型评估
    log("\n## 新模型评估")
    added, skipped = [], []
    for m in new_models:
        price = price_lookup(m, go_price, public_price)
        proto_hint = hint.get(m)
        if m in deprecated:
            skipped.append((m, "已过官方弃用日 %s" % deprecated[m]))
            continue
        if price is None:
            if "free" in m.lower():
                price = {"src": "free-name", "out_min": 0.0, "out_max": 0.0, "limit": None, "free": True}
            else:
                skipped.append((m, "价格未知（不在任何价格表），只列候选"))
                continue
        row = {"model": m, "price": price, "hint": proto_hint}
        if not price.get("free") and price.get("out_max") is not None and price["out_max"] > MAX_OUTPUT_PRICE:
            skipped.append((m, "输出单价 $%.2f 超过门槛 $%.2f" % (price["out_max"], MAX_OUTPUT_PRICE)))
            continue
        # 协议只从清单取：/models 的 api 优先，其次 Go 文档表，最后兜底 chat/completions
        if m in unsupported:
            skipped.append((m, "上游只提供 %s，客户端不支持" % "/".join(unsupported[m])))
            continue
        proto = (protocols.get(m) or [None])[0] or proto_hint or "chat/completions"
        if proto not in PROTOCOLS:
            skipped.append((m, "协议 %s 客户端不支持" % proto))
            continue
        row.update({"protocol": proto, "needs_no_thinking": False})
        if price.get("free"):
            tier, durable = "免费", None
        else:
            tier, durable = tier_for(price, m)
        provider_id = CHAT_PROVIDER[tier]
        row.update({"tier": tier, "provider": provider_id, "durable": durable})
        added.append(row)

    log("\n### 建议收录 %d 个" % len(added))
    for r in added:
        p = r["price"]
        if p.get("free"):
            price_txt = "免费"
        elif p.get("limit"):
            price_txt = "输入 $%.3f / 输出 $%.2f~%.2f / 月额度 $%s" % (
                p.get("input") or 0, p.get("out_min") or 0, p.get("out_max") or 0, p.get("limit"))
        else:
            price_txt = "输入 $%.3f / 输出 $%.2f~%.2f / 无 Go 额度表(按公开价)" % (
                p.get("input") or 0, p.get("out_min") or 0, p.get("out_max") or 0)
        durable_txt = ("额度可撑 %.0fM" % r["durable"]) if r.get("durable") else "—"
        log("  + %-28s 协议 %-16s 组 %-4s (%s) %s %s %s" % (
            r["model"], r["protocol"], r["tier"], r["provider"], price_txt, durable_txt,
            "  [需关思考覆盖]" if r["needs_no_thinking"] else ""))
    log("\n### 不收录 %d 个" % len(skipped))
    for m, why in skipped:
        log("  - %-28s %s" % (m, why))

    # 档位覆盖体检：新增模型必须带上游声明的 values，带不上要有明确原因。
    no_efforts = [r["model"] for r in added if not live_efforts.get(r["model"])]
    blocked = [r["model"] for r in added
               if live_efforts.get(r["model"]) and r["needs_no_thinking"]
               and (r.get("protocol") != "chat/completions"
                    or r["model"] in EFFORT_UNSUPPORTED)]
    if no_efforts:
        log("\n### 上游目录未声明档位（只能给「思考/不思考」开关）：%s"
            % ", ".join(no_efforts))
    if blocked:
        log("### 上游声明了档位但本模型需禁发思考字段（values 会是装饰项，未写）：%s"
            % ", ".join(blocked))

    # ---- 写入
    if args.apply and not args.probe_only:
        for m, _ in removed:
            touched = prune_model(cfg, m)
            if touched:
                log("  · 已从 %s 删除 %s" % (", ".join(touched), m))
        # 同一组内按版本号倒序追加，保持厂商块连续
        by_provider = {}
        for r in added:
            by_provider.setdefault(r["provider"], []).append(r)
        for pid, rows in by_provider.items():
            rows.sort(key=lambda r: tail_number(r["model"]), reverse=True)
            for r in rows:
                add_model(cfg, r["model"], pid, r["needs_no_thinking"], r.get("durable"),
                          live_efforts.get(r["model"]), r.get("protocol"))
        # 记录新模型的真实协议，供 model_alias.py 写进 alias map（4 组制靠它桥接）。
        try:
            hints = {}
            if os.path.exists(PROTOCOL_CACHE):
                with open(PROTOCOL_CACHE, encoding="utf-8") as f:
                    hints = json.load(f) or {}
            for r in added:
                hints[r["model"]] = ("chat" if r["protocol"] == "chat/completions"
                                     else r["protocol"])
            os.makedirs(os.path.dirname(PROTOCOL_CACHE), exist_ok=True)
            with open(PROTOCOL_CACHE, "w", encoding="utf-8") as f:
                json.dump(hints, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log("  · 协议提示缓存写入失败: %s" % e)
        moved = reclassify_backup(cfg)
        if moved:
            log("  · 备用档移动: " + ", ".join(moved))
        if added or moved or removed:
            backup = args.config + ".bak-gosync-" + stamp()
            shutil.copy2(args.config, backup)
            write_config(cfg, args.config)
            log("\n已写入 %s（备份 %s）" % (os.path.basename(args.config), os.path.basename(backup)))
        else:
            log("\n没有需要写入的新模型或失效模型，配置未改动")
    elif args.apply:
        log("\n只探测，配置未改动")

    # ---- 报告落盘
    try:
        os.makedirs(REPORT_DIR, exist_ok=True)
        rp = os.path.join(REPORT_DIR, "go-model-sync-%s.md" % stamp())
        with open(rp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        log("报告: %s" % rp)
    except Exception as e:
        log("报告写入失败: %s" % e)


if __name__ == "__main__":
    main()
