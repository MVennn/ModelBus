#!/usr/bin/env python3
"""Rebuild ZCode's model list as four credit-based groups with stable aliases.

The display id is:

    <CHANNEL>/<CREDITS>/<MODEL>

    W/0.03/DeepSeek-41-Fs   WorkBuddy global, deepseek-v4.1-flash-sg
    O/0.11/DeepSeek-41-Fs   OpenCode-Go, deepseek-v4.1-flash
    O/0.09/Qwen-38-Fs       OpenCode-Go, qwen3.8-flash
    Q/0.00/DeepSeek-4-Fs    Qoder CN, DeepSeek-Flash (off-peak)

Channel letters are W (WorkBuddy), O (OpenCode-Go), Q (Qoder). Model names
drop the `V` and version dots (`DeepSeek-V4.1-FS` -> `DeepSeek-41-Fs`).

The three providers are 主力 / 免费 / 省钱. Anything above 0.11 that is not in
MAIN_IDS or LOW_PICKS is dropped instead of getting its own group. `gateways/zgate` reads the generated alias map and
forwards each display id to its original upstream model, so the display name
never has to be parseable.

Credit conversion
-----------------
WorkBuddy `eff_rate` is the base. OpenCode-Go is anchored on
deepseek-v4.1-flash ($0.15 in / $0.60 out = 0.11 credits, 1:1 blend).
Qoder `price_factor` is multiplied by 0.86, the median ratio of same-name
models against WorkBuddy (GLM-5.3 0.862, GLM-5.3-Flash 0.80,
MiniMax-M3.1-Flash 0.80, Kimi-K2.8 0.963, DeepSeek-V4-Pro 1.02).

This script is the final writer. The existing Go / WorkBuddy / Qoder syncs may
still run first to refresh pricing and probe caches; run this script after them
so their old ids are normalized away. It is idempotent and backs up first.

`~/.zcode/v2/arena-main.json` (written by `tools/arena_leaderboard.py`) can
extend 主力 with models that score near the DeepSeek baseline at a similar
price. The leaderboard is opt-in now: pass `--arena` to allow it.

Usage
-----
    python tools/model_alias.py                  # dry run, prints the full table
    python tools/model_alias.py --apply          # backup + write config + alias map
    python tools/model_alias.py --max-price 2.0  # widen the high tier (0 = no cap)
    python tools/model_alias.py --check          # drift check only; exit 1 on drift

Prices are derived, never inherited: every run recomputes each hop's price from
the current source (WB pricing cache / Qoder live / OC price table). The alias
map stores identity only (what the model is called and which upstreams it maps
to); a hop whose upstream no longer prices is dropped. `--check` compares the
recomputed result against the existing alias map so a frozen price shows up as
drift instead of silently staying in the config.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
WB_PRICING = REPO / "providers" / "workbuddy" / "cache" / "wb_pricing.json"
QD_ENV = REPO / "providers" / "qoder" / ".env.local"
# 千问的集合体（旗舰/代码/快速）：每条是一串上游 id，路由按顺序逐个烧。
POOLS_FILE = REPO / "providers" / "qwen" / "pools.json"
DEFAULT_ARENA = Path.home() / ".zcode" / "v2" / "arena-main.json"

PROVIDER_MAIN = "opencode-go-chat"
PROVIDER_FREE = "opencode-go-chat-free"
PROVIDER_LOW = "opencode-go-chat-fast"
PROVIDER_IDS = [PROVIDER_MAIN, PROVIDER_FREE, PROVIDER_LOW]
PROVIDER_NAMES = {
    PROVIDER_MAIN: "主力",
    PROVIDER_FREE: "免费",
    PROVIDER_LOW: "省钱",
}
GROUPS = ("main", "free", "low")
ROUTER_BASE = "http://127.0.0.1:7871/v1"
WB_BASE = "http://127.0.0.1:7863/v1"
QD_BASE = "http://127.0.0.1:8790/v1"
OC_BASE = "https://opencode.ai/zen/go/v1"
QW_BASE = "https://maas.qianwenaiapi.com/apps/anthropic/v1"
# 谷歌 Gemini（catiecli 中转，OpenAI 兼容直连）。第三方转售通道没有公开价目表，
# 价格按 DeepSeek 主力标准档估算，只影响组内排序与展示；渠道级返回 None 会让
# 整个渠道被判「无价」并被 --apply 拒绝（见 main 的 dead channel 闸门），
# 所以未收录的 id 一律返 None（该跳丢弃），已收录的给显式价。
GM_BASE = "https://catiecli.sukaka.top/v1"
# 哈基米（gemai.cc）福利通道：网页售卖站的 `[福利]gemini-3.8-flash` 是独立中转站上
# 与 ais 3.8 同代的模型。它和 GM 是两家独立中转、两把独立 key
# （HJM_API_KEY，providers/hajimi/.env.local），所以模型 id 一字不改地带上
# `[福利]` 前缀 —— 上游只认这个字符串。
# 2026-11-10 用户口径：catiecli 的 ais 全档排队/不可用时直接用它，所以它不再是
# Gemini-AIS 链里的一跳，而是独立模型 Gemini-3.8-Flash（见 ABBR 与 MAIN_ORDER）。
HJ_BASE = "https://api.gemai.cc/v1"
HJ_PRICES = {
    # 2026-11-11 现网实测：gemai.cc 的「福利」档 3.8 / 3.7 / 3.6 全部
    # model_not_found（「No available channel for model」），售卖站的价目在，
    # 分销通道已经停了。「满血 A/B/C/F」与「官逆 B」四档的 3.8-flash 实测可用
    # （200 / 4.6–8.4s，与「福利」同代同款），所以主力档换 [满血A]，
    # 同型号 3.8 → 3.7 → 3.6 逐跳降级（实测三档都 200，5.4–6.2s）。
    # 价目没有公开表，沿用原来的估算口径（比 catiecli 3.8 的 0.11 便宜）。
    # 不能写 0.0 冒充免费：family_entries 见同一族里同时存在 <=0 与 >0 的跳时，
    # 会把这条链拆成「付费 + -Free」两条（见 MERGE_FREE_GB 注释）。
    "[满血A]gemini-3.8-flash": 0.05,
    "[满血A]gemini-3.7-flash": 0.05,
    "[满血A]gemini-3.6-flash": 0.05,
}
GM_PRICES = {
    # 上游没有公开价目表，7 个跳一律沿用同一个估算值（0.11 = DeepSeek 标准档）。
    # 同价是刻意的：跳序不靠价格区分，靠 HOP_PRIORITY 显式压制（见该常量注释）。
    "ais-gemini-3.8-flash": 0.11,
    "ais-gemini-3.7-flash": 0.11,
    "ais-gemini-3.6-flash": 0.11,
    "ais-gemini-3.5-flash": 0.11,
    "ais-gemini-3.5-flash-lite": 0.11,
    "ais-gemini-3.1-flash-lite": 0.11,
    "ais-gemini-3-flash-preview": 0.11,
}
# 千问渠道是**预付额度**：先用掉「每模型 1M tokens」的试用池（2026-12-15 到期），
# 之后走 ¥300 学生额度（一年有效，到期作废，用不完也不退）。
# 预付额度的边际单价就是 0，所以整段窗口内按 0 记账；额度真烧光时上游返回配额错误，
# 路由的 hopFatal + 冷却会把这跳摘掉，不需要有人回来改配置。
QW_CREDIT_UNTIL = "2027-10-28"

# 七牛云 `qiniu/conatus-free` 是限时免费（到 2026-11-30）。过期后 price_of 返回 None，
# 这一跳自动消失 —— 和限免到期同一条机制，不需要人工回来删配置。
QN_FREE_UNTIL = "2026-11-30"

# Hand-picked core. `~/.zcode/v2/arena-main.json` can add more (see
# tools/arena_leaderboard.py); `--no-arena` restores this list only.
# 键一律 `<协议>:<上游 id>`：同一型号会以 chat / messages 两种形态出现
# （千问桥接版是 messages），只写型号名会把两条一起吸进主力。
# 主力顺序：组内按此顺序排（DeepSeek 置顶，千问渠道免费 DeepSeek 尾跳最后）。
# 组内排序的权威来源；MAIN_IDS 由它派生，避免"按厂商最低价排序把便宜厂商顶到前面"。
MAIN_ORDER = [
    # 用户 2026-11-10 口径：主力组只放 DeepSeek（原反代通道已整体移除）。
    # 原主力的 hy4std（2026-11-06 曾因竞技榜前十被拍到第一位）与
    # qoder:Qwen3.8-Max（AA 1122 的贵备份）一起下沉省钱组，见 LOW_ORDER；
    # 不补进 LOW_PICKS 的话它们价格 >0 又不在任何名单里，会被判 drop 直接掉档。
    # 日常主力：最便宜的付费档，两跳同型号（WB cn / OC 直连）
    "chat:cn:deepseek-v4.1-flash",
    "chat:deepseek-v4.1-flash",
    # 免费 DeepSeek（千问渠道，messages 协议）：¥300 预付额度先烧这一条。
    # 它由 MERGE_ACROSS_PROTOCOL 并进上一条的链尾（同一显示名、按跳派发协议），
    # 这里仍列出是为了让排序与「链路覆盖」自解释。
    "messages:deepseek-v4.1-flash",
    # 哈基米档（HJ 渠道）2026-11-10 拆成独立模型 Gemini-3.8-Flash。
    # 位置压在 Gemini-AIS 之前：ais 全档排队不可用时用户直接点它，主力组列表里
    # 先给「能用的 3.8」再给「会降级的 3.8」，点名候选也按这个先后。
    # 2026-11-11 起 HJ 这段变成同站 3.8 → 3.7 → 3.6 三跳（「福利」档已断供），
    # 三个 id 都得点名，否则 3.7 / 3.6 只能等配置里先出现才进链。
    "chat:hjm:[满血A]gemini-3.8-flash",
    "chat:hjm:[满血A]gemini-3.7-flash",
    "chat:hjm:[满血A]gemini-3.6-flash",
    # 谷歌 Gemini Flash 系列（用户 2026-11-10 口径：新建的 catiecli provider 并入主力）。
    # 7 个上游 id 共用显示名 Gemini-AIS（ABBR），生成时合并成**一条链**（默认 7 跳，CHAIN_CAP 可截短）。
    # 3.8 这一行是该家族的「名字主人」：chain 的链首与主力组内的位置都由它决定
    # （_pick_rank 命中链上第一跳就返回，链首恒为 3.8，见 HOP_PRIORITY）。
    # 另外 6 个必须一并列出：MAIN_ORDER 是「组内顺序 + 点名候选」的唯一权威，
    # whitelist_items 会给名单里点名、但配置里还没出现的 id 补候选条目；
    # 只写 3.8 的话，上游新返的 3.7/3.6/3.5/… 就只能等 provider_config 里先出现。
    "chat:gem:ais-gemini-3.8-flash",
    "chat:gem:ais-gemini-3.7-flash",
    "chat:gem:ais-gemini-3.6-flash",
    "chat:gem:ais-gemini-3.5-flash",
    "chat:gem:ais-gemini-3.5-flash-lite",
    "chat:gem:ais-gemini-3.1-flash-lite",
    "chat:gem:ais-gemini-3-flash-preview",
]
MAIN_IDS = set(MAIN_ORDER)

# 竞技榜（~/.zcode/v2/arena-main.json）只负责给主力"补候选"，不推翻用户分组：
# 用户 2026-11-10 口径是主力=DeepSeek，而榜单 candidates 里还挂着
# MiMo-2.6-Flash / Space-Bunny，不过滤会把它们重新拉回主力。
MAIN_UPSTREAM_HINTS = ("deepseek",)
# 省钱组：每个厂商留 1–2 个特色型号（用户 2026-10-28 口径：前旗舰/旧版本全砍，
# 只留"最能代表这家、日常会用"的）。
# ⚠️ 这是**严格有序白名单**：组内顺序由 LOW_ORDER 决定（不是按厂商最低价，
# 否则便宜厂商会顶到前面把列表打乱）；命中这里即进组，不受 LOW_MAX 价格上限约束，
# 所以小米 MiMo-2.6-Pro（0.19）也能留在省钱组当厂商旗舰。
# 名单之外还有一条自动补位（2026-11-02 用户口径）：**新冒出来的一家公司**、或
# **这家公司更新的一代**，只要价格 ≤ LOW_MAX 就自动收录一条 —— 见 pick_auto_low。
# 老型号、同代兄弟型号仍然不收录，组里不会堆废物。
# 省钱组排列顺序（唯一权威来源）：总价档无关，按"厂商代表型号"排。
# 价格随价格源走，不写死。LOW_PICKS 由它派生，避免两份名单各自维护而漂移。
# 各行尾注释说明「为什么这家留这个型号」：
LOW_ORDER = [
    # 旗舰先行（用户 2026-11-09 从主力下沉，价格 >LOW_MAX 故必须留在名单里）；
    # 同厂商仍受 VENDOR_QUOTA=2 约束：HY 为 hy4std + hy3-x，QW 为 Max + 一条 Flash。
    "chat:cn:hy4std",                # 腾讯：旗舰（0.29，原主力第一位）
    "chat:qoder:Qwen3.8-Max",        # Qwen：旗舰（0.43，原主力贵备份）
    "messages:qwen3.8-flash",        # Qwen：中文 / 长输出（AA 基准附近）
    "chat:qoder:Qwen3.8-Flash",      # Qwen：Qoder 侧错峰免费（pf 0.0；白天 0.1×0.86≈0.086）。
                                     # 与上一条同族，靠 MERGE_ACROSS_PROTOCOL 并成一条链：
                                     # QD 首跳（免费）→ OC messages 跳（0.09）。
    "chat:cn:glm-5.3-flash",         # 智谱：工具调用稳（AA 993）
    "chat:cn:minimax-m3.1-flash",    # MiniMax：1M 上下文
    "chat:mimo-v2.6-flash",          # 小米：每积分最耐用（AA 1087）
    "chat:mimo-v2.6-pro",            # 小米：旗舰（0.19，厂商代表型号）
    "chat:cn:hy3-x",                 # 腾讯：最便宜（0.05）
    "messages:claude-haiku-5-5",     # Anthropic：子代理 / 小改动（AA 1026）
    "responses:gpt-6-luna",          # OpenAI：responses 协议（AA 992）
    "chat:cn:space-bunny",           # Space：AA 1074，性价比最高之一
]
LOW_PICKS = set(LOW_ORDER)

# 每厂商在省钱组最多保留几个代表（用户 2026-11-06 口径：每家公司 1–2 个特色型号）。
# 超出的按「版本号高者优先、同版本贵者优先（旗舰先行）」裁掉，人工名单里被裁掉的
# 留在原名单但不进组 —— 名单本身不改，只影响分组。
VENDOR_QUOTA = 2

# 竞技榜分数文件（tools/model_score.py 产出）：{ "CHANNEL|upstream": {intel, price_idx, value} }
# 只有带 --scores 时才读；口径见 docs/BENCHMARKS.md 5.4 与 tools/model_score.py 模块注释。
DEFAULT_SCORES = Path.home() / ".zcode" / "v2" / "model-scores.json"
# 白名单条目被分数替代的最低门槛：智力指数不低于锚定型号的这么多，
# 且性价比不低于锚定型号的这么多 —— 低于它才裁（只降不升）。
SCORE_MIN_INTEL = 85.0
SCORE_MIN_VALUE = 1.0

# Base models whose free GB tier is folded into the paid entry instead of being
# listed separately: the paid entry tries the free upstream first, then the paid
# one, then CN. Display name keeps the paid price.
MERGE_FREE_GB = {"deepseek-v4.1-flash", "qwen3.8-flash"}
# 同一型号允许 chat 与 messages 跳并进同一条链（路由按每跳自己的协议派发）。
MERGE_ACROSS_PROTOCOL = {"deepseek-v4.1-flash", "qwen3.8-flash"}

# WB（WorkBuddy）永远是第一消费来源：排序键里给它最高的固定优先级，
# 不看价格、不受任何「临时降级」开关影响。历史教训 2026-11-05：曾用一个
# DEMOTE_HOPS 集合把 WB 跳降到 OC 之后躲 6004 限流，结果整条会话在无人察觉
# 的情况下全部跑在 opencode 上计费。该降级机制已彻底移除 —— 上游限流交给
# zgate 逐跳回落，不再改链序。
WB_FIRST_CHANNELS = {"WB"}

# 渠道消费优先级 —— 链内跳排序的**第一维**（用户 2026-11-06 口径：
# WB → OC → 千问 ¥300 额度 → 七牛限免）。取代原来「WB 布尔特判 + TAIL_HOPS 布尔特判」
# 两段并列逻辑，让「哪个渠道先烧」变成一个可读的表，而不是两条 if。
#   · WB=0：额度优先消费，固定链首，不看价格、不受任何降级开关影响（历史教训见上）
#   · OC / QD=1：平价付费档，同档内按价格排
#   · QW=2：一年期预付额度，必须排在所有付费跳之后（原 TAIL_HOPS 的等价表达）
#   · QN=3：限免渠道排最后 —— 免费不等于该优先烧，它的价值是兜底
# 与旧键等价性：旧键第 1 维「WB?0:1」+ 第 2 维「TAIL?1:0」在 WB(0,0)/OC(1,0)/QW(1,1)
# 三种情况下与 (0,1,2) 完全同序；QN 目前没有与其它渠道混链的条目，rank 3 无实际影响。
#   · GM=1：谷歌中转（catiecli）直连付费档，与 OC/QD 同档，同型号多跳时按价格排
CHANNEL_RANK = {"WB": 0, "OC": 1, "QD": 1, "QW": 2, "QN": 3, "GM": 1, "HJ": 1}
CHANNEL_RANK_DEFAULT = 4

# 跳级优先级 —— 链内跳排序的**第二维**（紧跟 CHANNEL_RANK，在价格之前）。
# 为什么需要：GM（catiecli 中转）7 个 Gemini Flash 档**同价**（GM_PRICES 全是 0.11），
# 光靠 (价格, upstream 字符串) 排会把 "ais-gemini-3.5-flash" 排到
# "ais-gemini-3.8-flash" 前面 —— 字符串里 "3.5" < "3.8"，用户拿到的新一代
# 反而成了尾跳。版本新者必须先试，所以把「新一代优先」写成显式数字表。
# 只对表里的 upstream 生效；其它渠道的跳不在表里 → 取 HOP_PRIORITY_DEFAULT(99)
# → 同价时的相对顺序与加这张表之前完全一致（行为不变）。
# 2026-11-10 哈基米福利档拆成独立模型后已从表里移除：单跳族没有链内顺序，
# 留在表里反而会让这张表的语义（「链内跳序」）和实际链对不上。
# 同族但不同站的跳（哈基米 HJ）也在这里排：键是 upstream，值小的在前。
# 2026-11-11 起 Gemini-3.8-Flash 是 HJ 同站三跳，必须显式写 0/1/2，
# 否则三跳都取默认 99、并列时按 upstream 字符串序，链首会变成 3.6。
HOP_PRIORITY = {
    "[满血A]gemini-3.8-flash": 0,
    "[满血A]gemini-3.7-flash": 1,
    "[满血A]gemini-3.6-flash": 2,
    "ais-gemini-3.8-flash": 0,
    "ais-gemini-3.7-flash": 1,
    "ais-gemini-3.6-flash": 2,
    "ais-gemini-3.5-flash": 3,
    "ais-gemini-3.5-flash-lite": 4,
    "ais-gemini-3.1-flash-lite": 5,
    "ais-gemini-3-flash-preview": 6,
}
HOP_PRIORITY_DEFAULT = 99

# 链长上限 —— 只对「按次计费」的族生效，收窄 chain/fallbacks，不动 legacy_ids。
# Gemini-AIS 是 catiecli 按次扣额度（0.11/次，不看 token），而 GM 下 7 个 Gemini
# Flash 档质量差三档：3.8 是新一代、3.7/3.6 够用，3.5 / 3.5-lite / 3.1-lite /
# 3-flash-preview 是上一代和更老的小模型。按次计费的账是「每多一跳就多付一次
# 额度」，所以走到那四跳不但白付钱，用户拿到的还是更差的答案 —— 不如直接报错。
# 用户 2026-11-11 口径：「能 3.8 就 3.8，兜底只是兜底」。
# 被裁掉的跳仍登记在 legacy_ids 里：老会话点名 ais-gemini-3.5-flash 照样解析到
# Gemini-AIS，只是链不再真去打它。
CHAIN_CAP = {"Gemini-AIS": 3}


# 千问「每模型 1M tokens」试用池到期日（¥300 额度见 QW_CREDIT_UNTIL）。
# 试用池到期后边际成本从 0 变真钱，所以它比额度本身更早需要预警 —— 见 write_quota_windows。
QW_TRIAL_UNTIL = "2026-12-15"

# 机场出口：opencode.ai 的「地区受限」型号（gpt / beam / muse）从中国 IP 拿
# 403 `unsupported_country_region_territory`，必须经机场出去。路由器上这个入站口
# 绑死 🤖 AI接口 组（ShellcrashRules 的 `config/yamls/user.yaml` → listeners），
# 不看规则匹配，所以它只表示「这条出口是机场」。
# 2026-10-30 起 opencode.ai 本身走直连，机场只留给真正进不去的型号。
AIRPORT_PROXY = "http://10.0.0.1:7896"


def with_airport_fallback(hops: list[dict]) -> list[dict]:
    """给 OC 跳补一条「同上游、经机场」的孪生跳，排在链尾。

    为什么排链尾：回落是顺序的，机场是最后手段 —— 前面还有国内免费跳
    （DeepSeek 的千问尾跳）时，先试它们再花机场流量。地区受限的型号
    本来只有 OC 一跳，孪生跳就成了「直连被拒 → 换机场」的第二跳。
    已经有孪生跳就不再加，反复生成保持幂等。
    """
    out = list(hops)
    have = {
        (h["channel"], h["upstream"])
        for h in hops
        if str(h.get("proxy") or "") == AIRPORT_PROXY
    }
    for h in hops:
        if h.get("channel") != "OC" or str(h.get("proxy") or ""):
            continue
        if (h["channel"], h["upstream"]) in have:
            continue
        twin = dict(h)
        twin["proxy"] = AIRPORT_PROXY
        out.append(twin)
        have.add((h["channel"], h["upstream"]))
    return out
# ── 收录 / 价格口径（统一真值源）──────────────────────────────────────────
# 基准 = DeepSeek 标准（用户 2026-11-09：「按照 deepseek 的标准走就好」）：
# 以 deepseek-v4.1-flash 在本渠道的 WorkBuddy 积分价 0.11 为收录 / 超价不收的参照，
# 见下方 OC_PRICES["deepseek-v4.1-flash"]["off"] 与模块 docstring「Credit conversion」
# （$0.15 in / $0.60 out，1:1 混合 = 0.11 积分）；性能参照另见下方「以 DeepSeek-4.1
# 为参考」的竞技榜裁量口径与 SCORE_MIN_INTEL / SCORE_MIN_VALUE，两者是不同功能阈值。
# 各家价格一律统一折算为 WorkBuddy 积分后再比较（用户 2026-11-09：「价格转换我统一
# 成了 workbuddy 的积分」）：wb_prices() 给出 WB 积分权威价，price_of() 是唯一取价出口。
# 本次仅正规化口径：数值 / 阈值 / 分支 / 执行顺序 / 输出格式一字不变
# （用户 2026-11-09：「还是按照之前的逻辑，只是正规化一点」）。
DEEPSEEK_BASELINE_CREDITS = 0.11
FREE_MAX = 0.0
LOW_MAX = DEEPSEEK_BASELINE_CREDITS          # = 0.11，省钱档上限与 DeepSeek 基准同值
# Qoder price_factor → WorkBuddy 积分的统一折算倍率（同型号对 WB 中位比，见 docstring）。
QD_FACTOR = 0.86
# OpenCode-Go 美元挂牌价 → WorkBuddy 积分的折算锚：由基准反推
# (0.15 + 0.60) / 2 / 0.11 = 3.409 USD per credit（1:1 输入 / 输出混合）。
# 仅用于把 docs/MODEL-PROVIDERS.md §2 的 USD 价预折算进 OC_PRICES；运行时零折算。
USD_PER_WB_CREDIT = 3.409

# OC_PRICES 是「已折算完的 WorkBuddy 积分」结果表，不是 USD 挂牌价表：
# 每条目录入时已按「统一折算为 WorkBuddy 积分」口径换算完毕，price_of() 直接取用、
# 运行时不再做任何乘除。折算锚 = DeepSeek 标准（见 DEEPSEEK_BASELINE_CREDITS 与
# USD_PER_WB_CREDIT）；flat 键表示该型号无峰谷计价，直接返回单一积分价。
# OpenCode-Go prices from docs/MODEL-PROVIDERS.md §2, converted with the
# deepseek-v4.1-flash anchor (1 credit = $3.409/M, 1:1 input/output blend).
OC_PRICES = {
    # DeepSeek V4.1 Flash / V4 Pro are the only OpenCode-Go models with
    # time-based pricing (peak UTC Mon-Fri 01:00-04:00 and 06:00-10:00).
    "deepseek-v4.1-flash": {"off": 0.11, "peak": 0.22},
    "deepseek-v4-pro": {"off": 0.39, "peak": 0.77},
    "deepseek-v4-flash-vision-exp": None,
    "mimo-v2.6-pro": {"flat": 0.19},
    "mimo-v2.5-pro": {"flat": 0.19},
    "glm-5.3-flash": {"flat": 0.10},
    "mimo-v2.6-flash": {"flat": 0.06},
    "mimo-v2.5": {"flat": 0.06},
    "hy3": {"flat": 0.11},
    "longcat-2.0": {"flat": 0.22},
    "minimax-m3": {"flat": 0.22},
    "minimax-m3.1-flash": {"flat": 0.11},
    "beam-free": {"flat": 0.00},
    # 2026-10-28 实测：上游 usage 自带 cost=0 / list_cost=0，按免费档收录。
    "iceman-contributor-free": {"flat": 0.00},
    "claude-haiku-5-5": {"flat": 0.09},
    "qwen3.8-flash": {"flat": 0.09},
    "qwen3.7-plus": {"flat": 0.29},
    "minimax-m2.7": {"flat": 0.22},
    "gpt-6-luna": {"flat": 0.09},
    "gpt-5.6-luna": {"flat": 0.21},
    "muse-spark-1.3-contributor": {"flat": 0.04},
    "muse-spark-1.2-contributor": {"flat": 0.04},
}
# Qoder fallback if the hub is not reachable; live /v1/models wins.
QD_PRICES = {
    "DeepSeek-Flash": 0.0,
    "GLM-5.3-Flash": 0.1,
    "MiniMax-M3.1-Flash": 0.1,
    "DeepSeek-V4-Pro": 0.5,
    "Qwen3.8-Max": 0.5,
    "GLM-5.3": 0.8,
    "Kimi-K2.8-Preview": 0.8,
}

# 补建条目（provider_config 里原本没有、由 whitelist_items 新建的型号）默认只有
# enabled:true；dsh_sync.py 对缺失字段的处理是「不写键」，落宿主自己默认值，
# 不会兜 1000000 / 128000 —— 要控阈值只能在这里按上游 id 补真值。
# 一旦拿到某型号的真实 context / output 上限，在这里按上游 id 补元数据，
# 值直接贴合 providerModelRules 的 config 形态；当前无需要补建的型号。
MODEL_META = {}

ABBR = {
    # 七牛云网关的 id 形如 `qiniu/conatus-free`：去掉 `qiniu/` 前缀，Conatus 自成系列。
    "qiniu/conatus-free": "Conatus",
    # catiecli 中转的谷歌 id 形如 ais-gemini-3.8-flash：ais- 是中转站自己的前缀，
    # 不是谷歌型号的一部分，显示名里去掉。
    # 上游 /v1/models 实返 7 个 Gemini Flash 档（3.8 / 3.7 / 3.6 / 3.5 / 3.5-lite /
    # 3.1-lite / 3-preview），七个 id 是同一家的同一系列，全部收进同一个显示名
    # **Gemini-AIS**：组里只留一条「Gemini-AIS」，7 个上游成为这条链的跳，长度受 CHAIN_CAP 限制
    # （跳序由 HOP_PRIORITY 决定，见 family_entries 的排序键）。
    # 为什么不按型号各起一个名：用户 2026-11-10 口径是「一个 Gemini 条目，
    # 版本差异交给逐跳回落」，7 个名字会让选择器里堆 7 行同名系列。
    "ais-gemini-3.8-flash": "Gemini-AIS",
    # 哈基米档 2026-11-10 拆成独立族：显示名 Gemini-3.8-Flash（HJ 渠道）。
    # 以前它和 ais 同名、混在一条链里当兜底；用户口径改成「ais 不可用时直接用它」，
    # 于是从 Gemini-AIS 链里摘出来，不再参与那条链的降级。
    # 2026-11-11：「福利」档断供后这一族改成 [满血A] 的 3.8/3.7/3.6 三跳，
    # 显示名仍是 Gemini-3.8-Flash（链首 3.8 持有名字，跳序 3.8 → 3.7 → 3.6）。
    # 显示名去掉渠道档位前缀：上游 id 只认 [满血A]，用户侧只该看到一个 Gemini 名字。
    "gemini-3.8-flash": "Gemini-3.8-Flash",
    "gemini-3.7-flash": "Gemini-3.8-Flash",
    "gemini-3.6-flash": "Gemini-3.8-Flash",
    "ais-gemini-3.7-flash": "Gemini-AIS",
    "ais-gemini-3.6-flash": "Gemini-AIS",
    "ais-gemini-3.5-flash": "Gemini-AIS",
    "ais-gemini-3.5-flash-lite": "Gemini-AIS",
    "ais-gemini-3.1-flash-lite": "Gemini-AIS",
    "ais-gemini-3-flash-preview": "Gemini-AIS",
    "moonshotai/kimi-k3-free": "Kimi-K3",
    "deepseek-v4.1-flash": "DeepSeek-4.1-Flash",
    "deepseek-v4.1-flash-sg": "DeepSeek-4.1-Flash",
    "deepseek-v4-flash": "DeepSeek-4-Flash",
    "deepseek-v4-flash-vision-exp": "DeepSeek-4-Flash-Vision",
    "deepseek-v4-pro": "DeepSeek-4-Pro",
    "deepseek-v3-2-volc": "DeepSeek-3.2",
    "deepseek-flash": "DeepSeek-4-Flash",
    "qwen3.8-max": "Qwen-3.8-Max",
    "qwen3.8-flash": "Qwen-3.8-Flash",
    "qwen3.7-max": "Qwen-3.7-Max",
    "qwen3.7-plus": "Qwen-3.7-Plus",
    "qwen3.7-flash": "Qwen-3.7-Flash",
    "qwen-max": "Qwen-Max",
    "qwen3-coder-plus": "Qwen-3-Coder-Plus",
    "qwen3-coder-flash": "Qwen-3-Coder-Flash",
    "qwen-plus": "Qwen-Plus",
    "qwen-flash": "Qwen-Flash",
    "qwen3-vl-plus": "Qwen-3-VL-Plus",
    "qwq-plus": "QwQ-Plus",
    "glm-5.3": "GLM-5.3",
    "glm-5.3-flash": "GLM-5.3-Flash",
    "glm-5.2": "GLM-5.2",
    "glm-4.6": "GLM-4.6",
    "glm-4.6v": "GLM-4.6V",
    "minimax-m3.1-flash": "MiniMax-M3.1-Flash",
    "minimax-m3": "MiniMax-M3",
    "minimax-m2.7": "MiniMax-M2.7",
    "minimax-m2.5": "MiniMax-M2.5",
    "kimi-k2.8-preview": "Kimi-K2.8-Preview",
    "kimi-k3": "Kimi-K3",
    "kimi-k2.6": "Kimi-K2.6",
    "kimi-k2.5": "Kimi-K2.5",
    "hy3": "HY3",
    "hy3-x": "HY3-X",
    # 预览桶一律写全 -Preview：缩写 -Pre 与 -Std 一样，读者分不清是档位还是版本。
    "hy4-preview": "HY4-Preview",
    "hy4-preview-f": "HY4-Preview",
    "hy4-preview-ctrl": "HY4-Preview",
    "hy4-preview-exp": "HY4-Preview",
    "hy4-preview-x": "HY4-Preview",
    "hy4free": "HY4-Free",
    # hy4std 的上游回包 model 就是 hy4，-Std 只是 WorkBuddy 的档位名，不是型号名；
    # 同族只剩它一个付费档，去掉尾缀。只有 HY4-Free 必须带 Free 区分配额池。
    "hy4std": "HY4",
    "hy3-b": "HY3",
    "hy3-c": "HY3",
    "fast-model": "HY-Fast",
    "step-5-preview": "Step-5-Preview",
    "space-bunny": "Space-Bunny",
    "mimo-v2.6-pro": "MiMo-2.6-Pro",
    "mimo-v2.6-flash": "MiMo-2.6-Flash",
    "mimo-v2.5": "MiMo-2.5",
    "mimo-v2.5-pro": "MiMo-2.5-Pro",
    "longcat-2.0": "LongCat-2.0",
    "longcat-2.5-preview-free": "LongCat-2.5-Preview",
    "beam-free": "Beam",
    "iceman-contributor-free": "Iceman",
    "claude-haiku-5-5": "Claude-Haiku-5.5",
    "gpt-6-luna": "GPT-6-Luna",
    "gpt-5.6-luna": "GPT-5.6-Luna",
    "muse-spark-1.3-contributor": "Muse-Spark1.3",
    "muse-spark-1.2-contributor": "Muse-Spark1.2",
}

# 显示名改名表：旧名 → 新名。--apply 落盘时 legacy 里会留着旧名（历史条目是
# 自指形式 "Gemini-3.8-Flash" -> "Gemini-3.8-Flash"），改名后旧 target 不再是
# 任何模型的新 id，resolved_legacy 会把整条记录当成死链丢掉 —— 老会话里选中的
# 模型就解析不到了。main() 在 resolved_legacy 过滤前逐条补映射（缺失或自指才改写）。
# 2026-11-10：原来这里有一条 "Gemini-3.8-Flash" -> "Gemini-AIS"。哈基米福利档拆出来
# 独立成模型时正好复用了这个 id，它现在是 live 模型名 —— 改名映射必须撤掉。
# zgate 的 Resolve 先查 models 再查 legacy，路由本来就是新模型；但 legacy 里留一条
# 指向 AIS 的同名脏映射会误导排查，main() 另有一处「同名 legacy 一律丢弃」兜底。
NAME_RENAMES = {}


# 「无公司/匿名代号」模型（用户口径：一律沉到每组最下面）。名单顺序无关，
# 判据只看厂商码是否落在这四个里：Beam / Space-Bunny / Conatus / 未识别(OTHER)。
# Iceman 没有前缀，走 OTHER；Conatus 有独立前缀但仍是无公司代号。
ANONYMOUS_VENDORS = ("BEAM", "SPB", "CONATUS", "OTHER")


def config_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("ZCODE_PERSONAL_PROVIDER_CONFIG_FILE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".zcode" / "v2" / "provider_config.json"


def alias_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("UNIFIED_MODEL_MAP")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".zcode" / "v2" / "model-alias-map.json"


def arena_main_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("ARENA_MAIN_FILE")
    if env:
        return Path(env).expanduser()
    return DEFAULT_ARENA


def load_arena_targets(path: Path) -> dict[tuple[str, str], dict]:
    """Read `arena-main.json` into {(channel, upstream): candidate}."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        print(f"warning: 读不了榜单候选 {path}（{exc}），本次不扩充主力", file=sys.stderr)
        return {}
    targets: dict[tuple[str, str], dict] = {}
    for entry in data.get("candidates") or []:
        channel = str(entry.get("channel") or "")
        upstream = str(entry.get("upstream") or "")
        if channel and upstream:
            targets[(channel, upstream)] = entry
    return targets


def load_scores(path: Path) -> dict[str, dict]:
    """读 model-scores.json（tools/model_score.py 产出）。

    键是 CHANNEL|upstream，与 hop 一一对应 —— 不按显示名，因为显示名会随分组
    改名，按名字对会在改名当天全部失配。
    """
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except Exception as exc:  # noqa: BLE001
        print(f'warning: 读不了分数文件 {path}（{exc}），本次不参与选型', file=sys.stderr)
        return {}
    models = data.get('models') or {}
    out: dict[str, dict] = {}
    for key, row in models.items():
        if isinstance(row, dict) and row.get('intel') is not None:
            out[str(key)] = row
    return out


def score_of_entry(entry: dict, scores: dict[str, dict]) -> dict | None:
    """条目的最佳分数：取链上分数最高的一跳。"""
    best = None
    for hop in entry['chain']:
        row = scores.get(f"{hop['channel']}|{hop['upstream']}")
        if not row:
            continue
        if best is None or float(row['intel']) > float(best['intel']):
            best = row
    return best


def pick_scores_dropped(entries: list[dict], scores: dict[str, dict],
                        arena_targets: dict[tuple[str, str], dict]) -> set[int]:
    """按竞技榜分数裁掉「白名单里但明显更差」的省钱条目，返回要裁掉的 entry id。

    口径（用户 2026-11-06：以 DeepSeek-4.1 为参考，价格与性能一起看）：
      · 只动人工白名单命中的条目，主力 / 免费 / 自动补位一律不动；
      · 只降不升：分数只能用来裁，不能把没写进白名单的型号提拔进省钱组 ——
        那会绕过人工名单，也会让每日同步在分数抖动时反复改名；
      · 没有分数的条目（榜上没跑过）保持原状，不因为查不到被裁；
      · 低于门槛（智力 < SCORE_MIN_INTEL 或 性价比 < SCORE_MIN_VALUE）才裁。
    """
    dropped: set[int] = set()
    report = []
    for entry in entries:
        if entry.get('is_pool'):
            continue
        if not any(_picked(entry, hop, LOW_PICKS) for hop in entry['chain']):
            continue
        if any((hop['channel'], hop['upstream']) in arena_targets for hop in entry['chain']):
            continue
        row = score_of_entry(entry, scores)
        if not row:
            continue
        value = row.get('value')
        intel = float(row['intel'])
        weak = intel < SCORE_MIN_INTEL or (value is not None and float(value) < SCORE_MIN_VALUE)
        if not weak:
            continue
        dropped.add(id(entry))
        shown = 'free' if value is None else f'{float(value):.2f}'
        report.append(f"{entry['name']}(智力{intel:.1f}/价值{shown})")
    if report:
        print('按竞技榜分数裁剪：' + '，'.join(report), file=sys.stderr)
    return dropped

def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                out[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return out


def provider_rules(cfg: dict) -> list[dict]:
    rules = cfg["config"]["providerConfigRules"]
    if isinstance(rules, list):
        return rules
    return rules.setdefault("providerRules", [])


# ---- 推理档位继承（客户端可用档位，不是上游声明） ------------------------
#
# 档位（optionSpecs.reasoningLevel.values）是模型选择器下拉的全部来源。它跟
# 上游声明的 efforts 是两件事：上游不声明不代表网关不支持 —— 实测 mimo-v2.6-pro
# / iceman / gemini 系的 supported_efforts 为空，但发非法值会被网关按真实枚举打回，
# 档位全可用。所以继承链只认「配置里上次写下的值」，上游声明只给新增模型当初值，
# 绝不能反过来清空已有档位。
#
# 各渠道能力不同，档位格式不能跨渠道搬：
#   WB / QD 走统一路由（zgate），认 reasoning_effort；
#   OC 直连 opencode.ai/zen/go，只认 reasoning_effort；
#   QN 直连七牛；
#   其余（hjm: 哈基米、gem: AIS）档位是装饰项，不回写。
EFFORT_CHANNELS = ("WB", "QD", "OC", "QN")


def _effort_values(rule_config) -> list:
    """规则里的档位列表；没有就是空表。"""
    if not isinstance(rule_config, dict):
        return []
    spec = ((rule_config.get("optionSpecs") or {}).get("reasoningLevel") or {})
    values = spec.get("values")
    return [str(v) for v in values] if isinstance(values, list) else []


def _blank_effort_global(cfg: dict) -> bool:
    """整份配置一条档位都没有 = 上一轮被上游冲空过（读取侧自愈）。

    正常情况下档位清单只增不减；全空只可能出现在上游把 optionSpecs 冲掉、本地
    又没有可继承源的极端情形（2026-11-10 之前 map:"{}" + deep_merge 就是这样把
    20 条全冲成空的）。这种状态下允许新增模型重新采用上游声明的初值。
    """
    return not any(_effort_values(entry.get("config")) for entry in model_rules(cfg))


# 允许长期无档位的模型：上游确实没有多档（只有单一思考档或全是非 chat 网关模型），
# 用户选择器里给个空下拉反而误导。加进来要在注释里写明原因。
EMPTY_ALLOWED: set = {
    # 两家谷歌中转（GM: catiecli / HJ: gemai）的 /v1/models 只有 id，不回 reasoning
    # 能力位，本脚本也无从继承 —— 这两条注定是空档位。2026-11-11 之前它一直被报成
    # 「本轮同步补不回来」的漂移，每天让 sync-models.ps1 的漂移复查判失败一次，
    # 用户看到的是「复查仍有漂移，需要人工看」，实际什么都没坏。
    "Gemini-AIS",
    "Gemini-3.8-Flash",
}

def drifted_efforts(cfg: dict) -> list:
    """上一轮有档位、这一轮算出来却没有的模型 —— 每日同步的回归守门。

    `--check` 与 `dsh_sync.py --check` 都调它：只在内存里重算一遍继承链，不写盘。
    有漂移就说明某次同步会静默抹掉档位（用户看到的是「模型选择器里的推理等级
    突然没了」），必须当失败处理，而不是等下一轮手补。
    """
    try:
        alias_file = alias_path(None)
        existing = json.loads(alias_file.read_text(encoding="utf-8")) if alias_file.exists() else {}
        work = copy.deepcopy(cfg)
        items = inventory(work, existing.get("models") or {},
                          dict(existing.get("legacy") or {}))
        # 槽位固定 auto：守门要和每日同步（sync-models.ps1 不带 --slot，默认 auto）
        # 用同一个口径，否则守门算的是另一条价格链，报出来的漂移是假的。
        entries = family_entries(items, wb_prices(), qd_prices(), "auto")
        entries.extend(pool_entries(load_pools(POOLS_FILE), "auto"))
        # 快照必须在 pick_rule_config 之前做，而且要和它手上的 work 分属不同内存：
        # pick_rule_config 会把继承结果写回给自己的那份 config，若 old_rules 指向
        # 同一份对象，比出来永远「没变」，守门就成了哑的（2026-11-10 实测事故
        # 配置一条都不报）。
        landed: dict = {}
        for rule in model_rules(work):
            landed.setdefault(str(rule.get("modelId")), _effort_values(rule.get("config")))
        old_rules: dict = {}
        for rule in model_rules(work):
            old_rules.setdefault(str(rule.get("modelId")), copy.deepcopy(rule.get("config") or {}))
        picked = pick_rule_config(entries, work, old_rules)
        out: list = []
        for key, before in landed.items():
            after = _effort_values(picked.get(key))
            if before and not after:
                out.append("%s（%s → 无档位）" % (key, "/".join(before)))
            elif not before and not after and key not in EMPTY_ALLOWED:
                # 已经是空的：同步写盘后还是空的，等于这一轮同步「什么也没补回来」。
                # 上游不声明 efforts 的型号（mimo-v2.6-pro / iceman / gemini 系）本来就
                # 该由本脚本兜住，长期空着就是没人兜 —— 报出来，别等用户发现下拉没了。
                out.append("%s（无档位，且本轮同步补不回来）" % key)
        return out
    except (OSError, ValueError, KeyError, TypeError) as exc:  # 守门自己不能崩
        print("WARN: 档位漂移检查未执行：%s" % (exc if str(exc) else type(exc).__name__),
              file=sys.stderr)
        return []


def pick_rule_config(entries: list, cfg: dict, old_rules: dict) -> dict:
    """为每个条目算出写配置时用的 config（含档位继承），不落盘。

    独立成函数是因为两处必须共用同一套逻辑：真正写盘的那一轮，和 --check 的
    漂移守门。两边各写一份，守门迟早和实际行为对不上。
    """
    out: dict = {}
    blank_global = _blank_effort_global(cfg)
    by_name = {str(entry.get("name") or ""): entry for entry in entries}
    for name, entry in by_name.items():
        keys = [entry.get("raw"), entry.get("original"), entry.get("upstream"),
                entry.get("channel"), entry.get("name")]
        original_config = {}
        for key in keys:
            if key and str(key) in old_rules:
                original_config = old_rules[str(key)]
                break
        config = copy.deepcopy(original_config) if original_config else {}
        _inherit_efforts(config, entry, old_rules, entries, blank_global)
        out[name] = config
    return out


def _inherit_efforts(config: dict, entry: dict, old_rules: dict, entries: list,
                     blank_global: bool) -> None:
    """给条目 config 补齐档位：先用自己的，再用同 base_model 的兄弟型号。

    只补不清。上游这次没给档位时：能从兄弟型号（同名上游、不同版本）继承到
    就继承；全局不是「被冲空」状态就保留上一轮的写法；只有落在档位装饰渠
    道的条目才去掉，免得 GUI 给出根本发不出去的下拉。
    """
    specs = config.get("optionSpecs")
    if not isinstance(specs, dict):
        specs = config["optionSpecs"] = {}
    current = specs.get("reasoningLevel")
    own = _effort_values({"optionSpecs": {"reasoningLevel": current}})
    if own and (_effort_is_live(entry, current) or blank_global):
        return  # 自己已有能生效的档位：一个字都不动
    source = None
    if not own:
        source = _sibling_effort(entry, old_rules, entries)
    if not source and own and not blank_global and not _effort_is_live(entry, current):
        # 档位落在发不出这个字段的渠道上（哈基米福利档 / AIS）：留着只会让 GUI
        # 给出无效下拉，但这种「清空」只允许在全局仍有档位时做 —— 否则一次配置
        # 全员为空的事故就会被这段代码焊死成真正的空。
        specs.pop("reasoningLevel", None)
        source = _sibling_effort(entry, old_rules, entries)
    if source:
        specs["reasoningLevel"] = copy.deepcopy(source)


def _effort_is_live(entry: dict, reasoning) -> bool:
    """这条档位是否真能发出去（不是 GUI 上的装饰）。

    判据只看有没有可求值的 map 表达式：
      · 渠道在自己的能力表里（WB/QD/OC/QN）→ 网关或上游自己吃档位；
      · 或者 map 里写了字段（Gemini 的 thinking_budget、reasoning_effort 之类）
        → 客户端按表达式拼 body，跟渠道无关，实测同样生效
        （AIS 的 thinking_budget 0/1024/4096/16384 → reasoning_tokens 0/0/34/164）。
    只有「既不在能力表、又没有 map 表达式」的组合才是空头下拉，该去掉。
    """
    if entry.get("channel") in EFFORT_CHANNELS:
        return True
    if not isinstance(reasoning, dict):
        return False
    expr = str(reasoning.get("map") or "").strip()
    return bool(expr) and expr != "{}"


def _enforce_non_chat_effort(config: dict, entry: dict) -> None:
    """非 chat 协议（messages / responses）的档位处置。

    原先是无条件把 map 写成 "{}" —— 理由是非 chat 上游不吃 reasoning_effort 字段。
    但 2026-11-10 实测：opencode-go 的 messages 桥（claude-haiku-5-5 / gpt-6-luna /
    muse-spark-1.3 / beam-free）自己认档位，网关会把它翻成各家的 thinking 字段，
    照旧写 "{}" 等于每天同步一次就把 6 档清成「关/开」。现在按渠道分流：
      · 档位渠道（WB/QD/OC/QN）：保留档位，只在上游确实没有 reasoning_effort 写法
        时把 map 留原样；带 reasoning_effort 的一律不动；
      · 装饰渠道（hjm: / gem: 之类）：去掉 values，map 归 "{}"，免得 GUI 给假下拉。
    """
    specs = config.setdefault("optionSpecs", {})
    reasoning = specs.get("reasoningLevel")
    if not isinstance(reasoning, dict) or not reasoning.get("values"):
        specs.setdefault("reasoningLevel", {})["map"] = "{}"
        return
    if _effort_is_live(entry, reasoning):
        return  # 有可求值表达式：非 chat 协议照样把档位翻成上游字段
    reasoning.pop("values", None)
    reasoning["map"] = "{}"


def _same_family(base: str, other: str) -> bool:
    """上游型号是否同族：全等，或去掉版本尾段后相同（pro / flash 这类同代兄弟）。"""
    if not base or not other:
        return False
    if base == other:
        return True
    family = lambda name: name.rsplit("-", 1)[0] if "-" in name else name
    return family(base) == family(other)


def _sibling_effort(entry: dict, old_rules: dict, entries: list):
    """同一 base_model 的兄弟条目里已经落盘的档位。"""
    base = str(entry.get("base_model") or "")
    if not base:
        return None
    for other in entries:
        # 同族判定按上游型号前缀（mimo-v2.6-pro / mimo-v2.6-flash -> mimo-v2.6）：
        # 网关对同代型号开放同一套枚举，档位可以互借；不同代不互借，免得把
        # 高版本才有的档位套到老模型上发出非法值。
        if other is entry or not _same_family(base, str(other.get("base_model") or "")):
            continue
        if other.get("is_pool"):
            continue
        for key in (other.get("raw"), other.get("original"), other.get("upstream"),
                    other.get("name")):
            if not key:
                continue
            rule = old_rules.get(str(key))
            if _effort_values(rule):
                return (rule.get("optionSpecs") or {}).get("reasoningLevel")
    return None


def model_rules(cfg: dict) -> list[dict]:
    return cfg["config"].setdefault("modelConfigRules", {}).setdefault("providerModelRules", [])


_PRICE_WARNED: set[str] = set()
# 缺价统计：整渠道无价时 --apply 会把该渠道的模型整批从配置里剔除。
_UNPRICED: dict[str, int] = {}
# 逐跳明细：只报渠道计数时，「名单点名的某一跳查不到价」和「价格源整体缺失」
# 长得一模一样，2026-11-06 的 Qwen-3.8-Max 就是这样丢掉 OC 兜底跳的 —— 名单写着
# chat:Qwen3.8-Max，OC_PRICES 里没有它的价，跳被静默剔除，链只剩 QD 一跳。
_UNPRICED_HOPS: list[str] = []
_CHANNEL_ITEMS: dict[str, int] = {}


def _warn_price_once(channel: str, detail: str, fallback: str = "") -> None:
    """价格源不可用必须留痕：静默返回空表会把整个渠道的模型从配置里剔除。

    `fallback` 非空时说明已经回落到快照/硬编码表，告警只提示「价格不是实时」，
    不再说成「无法定价」—— 否则每轮都会误导成故障。
    """
    if channel in _PRICE_WARNED:
        return
    _PRICE_WARNED.add(channel)
    tail = fallback or "该渠道模型将无法定价"
    print(f"WARN: {channel} 价格源不可用（{detail}），{tail}", file=sys.stderr)


def _warn_stale_cache(path: Path, label: str, refresh_hint: str,
                      max_age_hours: float = 48.0) -> None:
    """价格表是活数据：过期了还照用，分档就会停在旧价上（限免到期尤其如此）。"""
    try:
        age_hours = (time.time() - path.stat().st_mtime) / 3600.0
    except OSError:
        return
    if age_hours <= max_age_hours:
        return
    print(
        f"WARN: {label} 已 {age_hours:.0f} 小时未刷新（> {max_age_hours:.0f}h），"
        f"分档可能已过期；先跑 {refresh_hint}",
        file=sys.stderr,
    )


def _fresh_probe(probe: dict, max_age_hours: float) -> tuple[dict, list[str]]:
    """丢掉过期的探测结论。

    过期的 ok 会留住已经下架的模型，过期的 blocked/unavailable 会删掉还能用的
    模型 —— 两个方向都错，所以过期条目一律按「未知」处理（未知不删除）。
    """
    if max_age_hours <= 0:
        return probe, []
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    fresh: dict = {}
    stale: list[str] = []
    for model_id, record in probe.items():
        raw = str((record or {}).get("checked_at") or "")
        try:
            checked = datetime.fromisoformat(raw)
        except ValueError:
            stale.append(model_id)
            continue
        if checked.tzinfo is not None:
            checked = checked.astimezone().replace(tzinfo=None)
        if checked >= cutoff:
            fresh[model_id] = record
        else:
            stale.append(model_id)
    return fresh, stale


def wb_family_key(model: str) -> str:
    """同一型号变体的归并键：抹掉 `-f` / `-ctrl` / `-exp<N>` 这类同族后缀。

    `cn:hy4-preview` / `-f` / `-ctrl` / `-exp1..3` 是同一上游的多个入口，
    挂牌价相同；用它给缺 credits 的变体回填价格（见 wb_prices）。
    """
    return re.sub(r"(?i)(-(ctrl|exp\d*|f))+$", "", model)


def wb_prices() -> dict[str, dict]:
    try:
        rows = json.loads(WB_PRICING.read_text(encoding="utf-8"))
    except Exception as exc:
        _warn_price_once("WB", f"{WB_PRICING}: {exc}")
        return {}
    _warn_stale_cache(WB_PRICING, "WB 价格表", "providers/workbuddy/workbuddy_fetch_pricing.py")
    # 上游偶发漏填 credits —— 2026-11-06 实测 cn:hy4-preview-f：credits 是空串、
    # list_rate 与 eff_rate 同时为 0。旧逻辑据此把它判成「免费」放进免费组，
    # 而它在 usage.json 里累计 2420 次请求扣了 6601 积分（均值 2.73/次）。
    # 判据改成「credits 字段权威」：
    #   · credits 有值（x0.29 / x0.00）→ 以它为准，这是上游自己的挂牌价
    #   · credits 空但 list_rate > 0 → 用 list_rate（老字段兜底）
    #   · 两者都缺 → 用「同族已知价」回填（同族 = 去掉 -f / -ctrl / -exp<N> 后缀）
    # 宁可高估也不能让付费型号冒充免费：冒充免费会进免费组被当无限兜底烧掉。
    # 本函数把 WB 上游行统一折算为 WorkBuddy 积分：credits 字段权威 / list_rate 兜底 /
    # 同族挂牌价回填（口径见上方 2026-11-06 注释与模块 docstring）。
    # 注意两遍解析语义不同、不可合并成一次循环：第一遍仅为 family_rate 建索引
    # （list_rate 缺失时回退 eff_rate），第二遍才产出结果（list_rate<=0 才回填）；
    # 合并会改变如 list_rate=None / eff_rate=0.5 这类行的取值，故保持现状。
    claims: dict[str, float] = {}
    family_rate: dict[str, float] = {}
    parsed: list[tuple[str, dict, float | None]] = []
    for row in rows:
        model = str(row.get("id") or "")
        if not model:
            continue
        try:
            list_rate = float(row.get("list_rate") if row.get("list_rate") is not None else row.get("eff_rate"))
            eff_rate = float(row.get("eff_rate") if row.get("eff_rate") is not None else list_rate)
        except (TypeError, ValueError):
            continue
        raw_credits = str(row.get("credits") or "").strip()
        claim = None
        if raw_credits:
            match = re.match(r"[x×]?\s*([0-9]*\.?[0-9]+)", raw_credits)
            if match:
                claim = float(match.group(1))
        parsed.append((model, row, claim))
        rate = claim if claim is not None else (list_rate if list_rate > 0 else None)
        if rate is not None and rate > 0:
            key = wb_family_key(model)
            if rate > family_rate.get(key, 0.0):
                family_rate[key] = rate
    out = {}
    for model, row, claim in parsed:
        list_rate = float(row.get("list_rate") or 0.0)
        eff_rate = float(row.get("eff_rate") or 0.0)
        if claim is not None:
            list_rate = claim
            eff_rate = claim if eff_rate <= 0 else eff_rate
        elif list_rate <= 0:
            backfill = family_rate.get(wb_family_key(model), 0.0)
            if backfill > 0:
                list_rate = backfill
                eff_rate = backfill
                print(
                    f"WARN: {model} 的 credits/list_rate 都缺失，按同族挂牌价 {backfill:g} 计费"
                    "（不当作免费；见 tools/model_alias.py wb_prices）",
                    file=sys.stderr,
                )
            else:
                eff_rate = eff_rate if eff_rate > 0 else 0.0
        out[model] = {
            "list": list_rate,
            "eff": eff_rate,
            "promo": str(row.get("promo") or ""),
            "label": str(row.get("promo_label") or ""),
            "credits": claim,
        }
    return out


def qd_prices() -> dict[str, dict]:
    """Qoder 实时倍率；8790 不在线时依次回落「上次成功的快照」→ 硬编码表。

    qoder 是 zgate 的 ondemand 子进程，绝大多数时间 8790 是停着的 —— 只靠下面那张
    硬编码表会让新型号永远定不了价（新模型→无价→被 drop）。所以每次成功读到实时倍率
    就落一份快照，下次 8790 没起时优先用它。
    """
    env = read_env(QD_ENV)
    key = os.environ.get("QD_API_KEY") or env.get("QD_API_KEY") or ""
    if key:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8790/v1/models",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            out = {}
            for model in payload.get("data") or []:
                name = str(model.get("id") or "")
                price = model.get("price_factor")
                if not name or price is None:
                    continue
                out[name] = {
                    "price": float(price),
                    "peak": float(model.get("price_factor_peak") if model.get("price_factor_peak") is not None else price),
                    "valley": float(model.get("price_factor_valley") if model.get("price_factor_valley") is not None else price),
                    "off_peak": model.get("off_peak") or {},
                }
            if out:
                _cache_qd_prices(out)
                return out
        except Exception as exc:
            _warn_price_once(
                "QD", f"127.0.0.1:8790: {exc}",
                "已回落到上次成功的倍率快照" if QD_CACHE.exists() else "已回落到硬编码倍率表",
            )
    cached = _read_qd_cache()
    if cached:
        return cached
    return {
        name: {"price": price, "peak": price, "valley": price, "off_peak": {}}
        for name, price in QD_PRICES.items()
    }


QD_CACHE = REPO / "providers" / "qoder" / "cache" / "qd_prices.json"


def _cache_qd_prices(prices: dict[str, dict]) -> None:
    """落一份实时倍率快照（写失败不影响主流程）。"""
    try:
        QD_CACHE.parent.mkdir(parents=True, exist_ok=True)
        QD_CACHE.write_text(json.dumps(prices, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _read_qd_cache() -> dict[str, dict]:
    try:
        data = json.loads(QD_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def in_off_peak(record: dict) -> bool:
    off = record.get("off_peak") or {}
    start = str(off.get("window_start") or "22:00")
    end = str(off.get("window_end") or "08:00")
    now = datetime.now(timezone(timedelta(hours=8)))
    hm = now.strftime("%H:%M")
    if start <= end:
        return start <= hm < end
    return hm >= start or hm < end


def in_oc_peak() -> bool:
    """OpenCode-Go peak: UTC Mon-Fri 01:00-04:00 and 06:00-10:00."""
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return (60 <= minutes < 240) or (360 <= minutes < 600)


def qw_credit_active() -> bool:
    return datetime.now().strftime("%Y-%m-%d") <= QW_CREDIT_UNTIL


def price_of(channel: str, upstream: str, wb: dict[str, dict],
             qd: dict[str, dict], slot: str) -> float | None:
    if channel == "GM":
        # 中转站没有公开价目表：只认 GM_PRICES 的显式价，未收录即 None（该跳被丢）。
        return GM_PRICES.get(upstream)
    if channel == "HJ":
        # 哈基米同为转售站，口径同 GM：只认 HJ_PRICES 的显式价，未收录即 None。
        return HJ_PRICES.get(upstream)
    if channel == "QW":
        return 0.0 if qw_credit_active() else None
    if channel == "QN":
        # 七牛限免只覆盖带 -free 后缀的模型（2026-11-30 前）。渠道级一律返 0
        # 会把将来播种的付费模型也误标成免费，所以必须按上游 id 判定。
        if not str(upstream).endswith("-free"):
            return None
        return 0.0 if datetime.now().strftime("%Y-%m-%d") <= QN_FREE_UNTIL else None
    if channel == "WB":
        record = wb.get(upstream)
        if not record:
            return None
        if slot == "peak":
            return record["list"] if record["list"] > 0 else record["eff"]
        if slot == "offpeak":
            label = record.get("label", "").lower()
            time_based = any(key in label for key in ("夜间", "错峰", "night", "off-peak", "off peak"))
            if time_based and record["eff"] < record["list"]:
                return record["eff"]
        return record["eff"]
    # QD：price_factor 是相对倍率，乘 QD_FACTOR 才统一折算为 WorkBuddy 积分
    # （见 QD_FACTOR 注释与 docstring「Credit conversion」）。这是唯一运行时折算。
    if channel == "QD":
        record = qd.get(upstream)
        if not record:
            return None
        if slot == "peak":
            factor = record["peak"]
        elif slot == "offpeak":
            factor = record["valley"]
        else:
            factor = record["valley"] if in_off_peak(record) else record["peak"]
        return factor * QD_FACTOR
    record = OC_PRICES.get(upstream)
    if record is None:
        return None
    if "flat" in record:
        return float(record["flat"])
    if slot == "peak":
        return float(record.get("peak", record.get("off")))
    if slot == "offpeak":
        return float(record.get("off", record.get("peak")))
    return float(record["peak"] if in_oc_peak() else record["off"])


def abbreviate(model: str) -> str:
    key = model.lower()
    if key in ABBR:
        return ABBR[key]
    # 兜底再比一次「去掉渠道档位前缀」的形式：ABBR 的键按小写存，
    # 而 `[满血A]gemini-3.8-flash` 这种 id 里的大写 A 在 .lower() 之后
    # 会变成 `[满血a]…`，键根本对不上。只靠键名精确匹配会静默漏掉整族。
    stripped_key = re.sub(r"^\[[^\]]*\]", "", key)
    if stripped_key != key and stripped_key in ABBR:
        return ABBR[stripped_key]
    # hy4-preview 的多个入口（-f / -ctrl / -exp1..3 / -x）是同一上游的不同档位，
    # 回包 model 都是 hy4-preview。同一型号只给一个显示名，档位尾缀一律不带
    # （用户 2026-11-06 口径：没有真正不同的模型就不要尾缀）。
    if re.match(r"hy4-preview(-|$)", key):
        return "HY4-Preview"
    # 厂商前缀（`qiniu/` `moonshotai/`）与 `-free` / `-f` 标记都不进显示名：
    # 「免费」由分组表达，只有同型号同时存在免费与付费档时才加 `-Free`。
    # 哈基米售卖站的档位前缀（[满血A] / [官逆B] …）是渠道标，不属于型号：
    # 不去掉的话显示名会变成 "A-gemini-3.8-Flash"，同一型号被拆成一堆名字。
    text = re.sub(r"^\[[^\]]*\]", "", model)
    text = re.sub(r"^[a-z0-9_-]+/", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)[-_]free$", "", text)
    text = re.sub(r"^[Vv](?=\d)", "", text)
    # 不缩写：-Fs / -Pre 这类尾缀读者分不清是档位还是版本，一律写全。
    text = re.sub(r"(?i)flash\b", "Flash", text)
    text = re.sub(r"(?i)preview\b", "Preview", text)
    text = re.sub(r"[^A-Za-z0-9.-]+", "-", text).strip("-")
    return text or "MODEL"


VENDOR_PREFIXES = (
    ("DeepSeek", "DSP"), ("Qwen", "QW"), ("QwQ", "QW"), ("GLM", "GLM"), ("MiniMax", "MM"),
    ("Kimi", "KIMI"), ("HY", "HY"), ("MiMo", "MIMO"), ("LongCat", "LONG"),
    ("Beam", "BEAM"), ("Claude", "CL"), ("GPT", "GPT"), ("Muse", "MUSE"),
    ("Step", "STEP"), ("Space", "SPB"), ("Conatus", "CONATUS"), ("Gemini", "GEM"),
)


def vendor_of(abbr: str) -> str:
    for prefix, vendor in VENDOR_PREFIXES:
        if abbr.startswith(prefix):
            return vendor
    return "OTHER"


def anonymous_rank(abbr: str) -> int:
    """0 = 有公司可识别，1 = 匿名/无公司代号（排序时整组沉底）。

    DSH GUI 侧不做二次排序（orderModelProviders 只把 account/official 提前，
    组内保持 catalog 原序），所以「匿名置底」必须在这里生效，写进
    personalModelIds/modelOrder 的最终顺序里。
    """
    return 1 if vendor_of(abbr) in ANONYMOUS_VENDORS else 0


_PROTOCOL_HINTS: dict | None = None


def protocol_hints() -> dict:
    """go 同步写下的新模型协议提示（chat/messages/responses），供 classify 兜底。"""
    global _PROTOCOL_HINTS
    if _PROTOCOL_HINTS is None:
        path = (Path(__file__).resolve().parent.parent
                / "providers" / "opencode-go" / "cache" / "go_protocols.json")
        try:
            _PROTOCOL_HINTS = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _PROTOCOL_HINTS = {}
    return _PROTOCOL_HINTS


PREFIXES = ("qwen:", "qoder:", "cn:", "global:", "gem:", "hjm:")


def _bare(model_id: str) -> str:
    """去掉渠道前缀后的裸 id，用于比较 legacy 映射是否还指得对。"""
    text = str(model_id)
    for prefix in PREFIXES:
        if text.lower().startswith(prefix):
            return text[len(prefix):].lower()
    return text.lower()


def classify(model: str, protocol: str, alias_models: dict, legacy: dict) -> dict | None:
    """Map any config model id (old or already-renamed) to its inventory fields."""
    if model in alias_models:
        entry = alias_models[model]
        # 集合体只由 pools.json 生成：不能让它进 inventory 被 expand_hops 按跳拆开，
        # 否则每一跳都会变成一条独立模型，下一轮再翻倍。
        if entry.get("kind") == "pool":
            return None
        channel = str(entry.get("channel") or "")
        upstream = str(entry.get("upstream") or "")
        base_model = str(entry.get("base_model") or (
            upstream.split(":", 1)[1] if channel == "WB" and ":" in upstream else upstream
        ))
        region = str(entry.get("region") or (
            "CN" if channel == "WB" and upstream.startswith("cn:") else
            "GB" if channel == "WB" else "CN" if channel == "QD" else ""
        ))
        return {
            "raw": model,
            "original": str(entry.get("original") or model),
            "channel": channel,
            "region": region,
            "upstream": upstream,
            "base_model": base_model,
            "protocol": str(entry.get("protocol") or protocol),
            "fallbacks": list(entry.get("fallbacks") or []),
            "chain": list(entry.get("chain") or []),
            "legacy_ids": list(entry.get("legacy_ids") or [entry.get("original") or model, upstream]),
        }
    legacy_target = legacy.get(model)
    if legacy_target in alias_models and ":" in model:
        # 带渠道前缀的 key 必须真能对上目标条目的某一跳：否则这是上一轮
        # 改名/展开留下的陈旧映射，会把这个 id 静默指到完全无关的模型上。
        target = alias_models[legacy_target]
        hops = target.get("chain") or [target]
        upstreams = {_bare(h.get("upstream") or "") for h in hops}
        if _bare(model) not in upstreams:
            legacy_target = None
    if legacy_target in alias_models:
        result = classify(legacy_target, protocol, alias_models, {})
        if result is None:
            return None
        result = dict(result)
        result["raw"] = model
        legacy_ids = result.get("legacy_ids") or []
        if model not in legacy_ids:
            legacy_ids = [model] + legacy_ids
        result["legacy_ids"] = legacy_ids
        return result
    if model.startswith(("cn:", "global:")):
        return {
            "raw": model,
            "original": model,
            "channel": "WB",
            "region": "CN" if model.startswith("cn:") else "GB",
            "upstream": model,
            "base_model": model.split(":", 1)[1],
            "protocol": protocol,
            "fallbacks": [],
            "legacy_ids": [model],
        }
    if model.startswith("oc:"):
        # 显式 OC 渠道：白名单里同名型号可能在别的渠道也有（qwen3.8-max 同时在 QD），
        # 不写前缀就只会走末尾兜底，upstream 还会带着 "oc:" 一起被当成型号名。
        upstream = model[len("oc:"):]
        return {
            "raw": model,
            "original": model,
            "channel": "OC",
            "region": "",
            "upstream": upstream,
            "base_model": upstream,
            "protocol": protocol,
            "fallbacks": [],
            "legacy_ids": [model],
        }
    if model.startswith("qoder:"):
        upstream = model[len("qoder:"):]
        return {
            "raw": model,
            "original": model,
            "channel": "QD",
            "region": "CN",
            "upstream": upstream,
            "base_model": upstream,
            "protocol": protocol,
            "fallbacks": [],
            "legacy_ids": [model],
        }
    if model.startswith("qwen:"):
        upstream = model[len("qwen:"):]
        return {
            "raw": model,
            "original": model,
            "channel": "QW",
            "region": "CN",
            "upstream": upstream,
            "base_model": upstream,
            # 千问平台只提供 Anthropic Messages 端点：协议必须钉成 messages，
            # 否则 zgate 会按 chat 直转，上游直接 404。
            "protocol": "messages",
            "fallbacks": [],
            "legacy_ids": [model],
        }
    if model.startswith("qn:"):
        upstream = model[len("qn:"):]
        return {
            "raw": model,
            "original": model,
            "channel": "QN",
            "region": "CN",
            "upstream": upstream,
            "base_model": upstream,
            # 七牛云 AI 网关同样只有 Anthropic Messages 端点。
            "protocol": "messages",
            "fallbacks": [],
            "legacy_ids": [model],
        }
    if model.startswith("gem:"):
        # 显式 GM 渠道：白名单写 chat:gem:ais-gemini-3.8-flash 走到这里；
        # 不写前缀会落到末尾 OC 兜底，那条会把 ais- 前缀当成型号名。
        upstream = model[len("gem:"):]
        return {
            "raw": model,
            "original": model,
            "channel": "GM",
            "region": "GB",
            "upstream": upstream,
            "base_model": upstream,
            "protocol": protocol,
            "fallbacks": [],
            "legacy_ids": [model],
        }
    if model.startswith("hjm:"):
        # 显式 HJ 渠道（哈基米 gemai.cc）：白名单写
        # chat:hjm:[满血A]gemini-3.8-flash 走到这里。不写前缀会落到末尾 OC 兜底，
        # 那条会把 [福利] 前缀当成型号名发给 opencode.
        upstream = model[len("hjm:"):]
        return {
            "raw": model,
            "original": model,
            "channel": "HJ",
            "region": "GB",
            "upstream": upstream,
            "base_model": upstream,
            "protocol": protocol,
            "fallbacks": [],
            "legacy_ids": [model],
        }
    if model.startswith(("WB:", "OC:", "QD:")):
        # A renamed id that is not in the alias map: refuse to guess.
        return None
    # 4 组制：messages / responses 模型也进成本档，协议由 go 同步写的提示缓存兜底，
    # 写进 alias map 后 zgate 才能按 protocol 桥接。
    hint = protocol_hints().get(model)
    if hint:
        protocol = hint
    return {
        "raw": model,
        "original": model,
        "channel": "OC",
        "region": "",
        "upstream": model,
        "base_model": model,
        "protocol": protocol,
        "fallbacks": [],
        "legacy_ids": [model],
    }


def whitelist_items(order: list[str]) -> list[dict]:
    """把白名单里点名、但当前配置里已经没有的型号补成候选条目。

    为什么需要：条目列表只来自 provider_config 的 personalModelIds（见 inventory）
    与池子文件，所以某型号一旦因为价格闸被裁出配置，第二天就再也不会被考虑 ——
    白名单写了等于没写。2026-11-06 的 cn:hy4std（竞技榜建模 #8、0.29 积分）就是
    这样被静默丢掉的：名单里加了它，dry run 却一条都生成不出来。
    """
    out: list[dict] = []
    for spec in order:
        protocol, _, model = str(spec).partition(":")
        model = model.strip()
        if not model:
            continue
        item = classify(model, protocol or "chat", {}, {})
        if item is None:
            print(f"WARN: 白名单条目 {spec} 认不出渠道，已忽略", file=sys.stderr)
            continue
        item["whitelisted"] = True
        # 白名单是否显式写了渠道前缀（qoder: / qwen: / cn: / global: / WB: …）。
        # 只有显式的才按 (渠道, 裸名) 去重，否则 classify 猜出来的渠道会把
        # 「同一个 upstream 名在另一个渠道的跳」误判成重复（见 main 里的补建过滤）。
        item["explicit_channel"] = str(model).lower().startswith(
            ("qoder:", "qwen:", "cn:", "global:", "wb:", "oc:", "qd:", "gem:", "hjm:")
        )
        out.append(item)
    return out


def inventory(cfg: dict, alias_models: dict, legacy: dict) -> list[dict]:
    """Collect unique models from the current provider config."""
    seen: dict[tuple[str, str, str], dict] = {}
    for rule in provider_rules(cfg):
        provider_id = str(rule.get("providerId") or "")
        config = rule.get("config") or {}
        api = config.get("api") or {}
        api_type = str(api.get("type") or "openai-chat-completions")
        protocol = {
            "openai-chat-completions": "chat",
            "anthropic-messages": "messages",
            "openai-responses": "responses",
        }.get(api_type, "chat")
        for raw in config.get("personalModelIds") or []:
            model = str(raw).strip()
            if not model:
                continue
            item = classify(model, protocol, alias_models, legacy)
            if item is None:
                continue
            item["provider_id"] = provider_id
            for hop in expand_hops(item):
                # proxy 也进键：同一个 upstream 的「直连跳」和「机场孪生跳」
                # 必须各自留下，否则去重时后者被前者吃掉，兜底就没了。
                key = (hop["channel"], hop["upstream"], hop["protocol"], str(hop.get("proxy") or ""))
                if key in seen:
                    previous = seen[key]
                    values = previous.setdefault("legacy_ids", [])
                    for value in hop.get("legacy_ids") or []:
                        if value not in values:
                            values.append(value)
                    continue
                seen[key] = hop
    return list(seen.values())


# 千问平台只有 Anthropic Messages 端点，任何 QW 跳的协议都必须是 messages。
# 这是渠道属性，不依赖 alias map 里存了什么（上一版存错时会被这里纠正）。
CHANNEL_PROTOCOL = {"QW": "messages"}


def expand_hops(item: dict) -> list[dict]:
    """One item per upstream: v2 chain, v1 fallbacks, or the item itself."""
    chain = item.get("chain") or []
    if chain:
        out = []
        for hop in chain:
            sub = dict(item)
            sub.update({
                "channel": hop.get("channel") or item["channel"],
                "upstream": hop.get("upstream") or item["upstream"],
                "base_model": hop.get("base_model") or item["base_model"],
                "original": hop.get("original") or hop.get("upstream") or item["upstream"],
                # 每跳保留自己的协议：跨协议合并的条目（主力的 DeepSeek 链）
                # 条目级是 chat，尾跳是 messages，覆盖成条目级会让路由按 chat
                # 直转 messages 上游，直接 404。
                "protocol": CHANNEL_PROTOCOL.get(
                    hop.get("channel") or item["channel"],
                    hop.get("protocol") or item["protocol"],
                ),
                # 价格一律由 price_of() 从当轮价格源重算：继承上一版 alias map
                # 里的 price 会把上游改价/限免到期永久冻结在旧值上
                # （2026-10-28 Step-5-Pre 限免结束仍显示 0.00 即此因）。
                "price": None,
                "fallbacks": [],
            })
            # 机场孪生跳的出口要跟着跳走，否则下一轮它会被当成普通直连跳。
            sub["proxy"] = str(hop.get("proxy") or "")
            out.append(sub)
        return out
    out = [dict(item)]
    for fallback in item.get("fallbacks") or []:
        if fallback == item["upstream"]:
            continue
        sub = dict(item)
        sub.update({
            "upstream": fallback,
            "base_model": re.sub(r"^(cn|global):", "", fallback),
            "original": fallback,
            "price": None,
            "fallbacks": [],
        })
        out.append(sub)
    return out


def raw_models(cfg: dict, alias_models: dict, legacy: dict) -> list[dict]:
    out: list[dict] = []
    for rule in provider_rules(cfg):
        config = rule.get("config") or {}
        api = config.get("api") or {}
        api_type = str(api.get("type") or "openai-chat-completions")
        protocol = {
            "openai-chat-completions": "chat",
            "anthropic-messages": "messages",
            "openai-responses": "responses",
        }.get(api_type, "chat")
        for raw in config.get("personalModelIds") or []:
            model = str(raw).strip()
            if not model:
                continue
            item = classify(model, protocol, alias_models, legacy)
            if item is not None:
                out.append(item)
    return out


QN_BASE = "https://api.qnaigc.com/v1"
CHANNEL_BASE = {"WB": WB_BASE, "QD": QD_BASE, "OC": OC_BASE, "QW": QW_BASE,
                "QN": QN_BASE, "GM": GM_BASE, "HJ": HJ_BASE}


def base_of(channel: str) -> str:
    return CHANNEL_BASE.get(channel, OC_BASE)


def family_entries(items: list[dict], wb: dict, qd: dict, slot: str) -> list[dict]:
    """Collapse one entry per (model, protocol), merging channels by price.

    The display name is just the model name (no channel, no price). Hops are
    ordered cheapest-first across channels, and each hop carries its own base so
    the router can switch upstreams without a shared host.

    A free tier stays a separate entry (suffixed -F) when the same model also has
    a paid tier, except for MERGE_FREE_GB families where the free hop is folded
    into the paid entry and tried first.
    """
    families: dict[tuple[str, str], dict[str, dict]] = {}
    for item in items:
        _CHANNEL_ITEMS[item["channel"]] = _CHANNEL_ITEMS.get(item["channel"], 0) + 1
        price = item.get("price")
        if price is None:
            price = price_of(item["channel"], item["upstream"], wb, qd, slot)
        if price is None:
            _UNPRICED[item["channel"]] = _UNPRICED.get(item["channel"], 0) + 1
            _UNPRICED_HOPS.append(f'{item["channel"]}:{item["upstream"]}')
            continue
        hop = dict(item)
        hop["price"] = round(float(price), 2)
        abbr = abbreviate(item["base_model"])
        if str(item["base_model"]).lower() in MERGE_ACROSS_PROTOCOL:
            key = (abbr, "merged")
        else:
            key = (abbr, item["protocol"])
        families.setdefault(key, {})[(item["channel"], item["upstream"], str(item.get("proxy") or ""))] = hop

    entries: list[dict] = []
    # 同一型号若同时存在 chat 与桥接协议（messages / responses），原型名必须留给
    # chat 那条：否则桥接条目会先占名，聊天条目被挤成 `-2`，老会话里选中的
    # `GLM-5.3` 会悄悄指到另一个渠道上去。
    abbr_protocols: dict[str, set[str]] = {}
    for (abbr, protocol) in families:
        abbr_protocols.setdefault(abbr, set()).add(protocol)
    for (abbr, protocol), hop_map in families.items():
        hops = sorted(hop_map.values(), key=lambda h: (h["price"], h["upstream"]))
        if not hops:
            continue
        free = [h for h in hops if h["price"] <= 0]
        paid = [h for h in hops if h["price"] > 0]
        base_model = hops[0]["base_model"]
        family_key = re.sub(r"(-sg|-f)$", "", base_model.lower())

        if family_key in MERGE_FREE_GB or not (free and paid):
            groups = [hops]
        else:
            groups = [paid, free]

        for group in groups:
            # 第一键：渠道消费优先级（CHANNEL_RANK）—— WB 链首、OC/QD 其次、
            # QW 预付额度垫后、QN 限免兜底。原「WB 布尔特判 + TAIL_HOPS 布尔特判」
            # 两段并列逻辑已并入这张表，行为等价性见 CHANNEL_RANK 的注释。
            # 其后按价格、GB/CN 前缀、渠道、名称稳定排序。
            # 第二键：跳级优先级（HOP_PRIORITY）。同渠道同价时要靠它压住顺序 ——
            # GM 的 7 个 Gemini Flash 跳同价，纯按 (price, upstream) 排会把 3.5
            # 排到 3.8 前面（字符串比较）。不在表里的 upstream 取默认 99，
            # 因为 99 大于所有显式值，所以其它渠道同价时的相对顺序不变。
            group = sorted(group, key=lambda h: (
                CHANNEL_RANK.get(h["channel"], CHANNEL_RANK_DEFAULT),
                HOP_PRIORITY.get(h["upstream"], HOP_PRIORITY_DEFAULT),
                h["price"],
                0 if h["upstream"].startswith("global:") else 1 if h["upstream"].startswith("cn:") else 2,
                # 同 rank 内的渠道先后保持历史顺序（QD 先于 OC）：CHANNEL_RANK 只
                # 决定「哪个渠道先烧」，同一 rank 的平价付费档仍按 QD→OC 的旧口径，
                # 避免这次重构顺手改了已有链序。
                0 if h["channel"] == "WB" else 1 if h["channel"] == "QD" else 2,
                h["upstream"],
            ))
            # 机场兜底排在链尾（见 with_airport_fallback 的注释）。
            group = with_airport_fallback(group)
            # 链长上限：只收窄真正会去打的 chain/fallbacks，legacy_ids 仍按
            # 全量 group 收（见 CHAIN_CAP 注释）。
            cap = CHAIN_CAP.get(abbr)
            chain_group = group[:cap] if cap and len(group) > cap else group
            # 被 CHAIN_CAP 裁掉的跳：仍要登记进 legacy_ids，否则老会话点名这些
            # upstream 会变成 404。dropped_hops 只在真有截断时写进 alias map。
            dropped = [h["upstream"] for h in group[len(chain_group):]]
            is_free_entry = all(h["price"] <= 0 for h in group)
            base_name = abbr
            if protocol != "chat" and "chat" in abbr_protocols.get(abbr, ()):
                base_name = abbr + ("-Msg" if protocol == "messages" else "-Resp")
            name = base_name + ("-Free" if is_free_entry and len(groups) > 1 else "")
            chain = []
            for h in chain_group:
                hop = {
                    "upstream": h["upstream"],
                    "base": base_of(h["channel"]),
                    "channel": h["channel"],
                    "protocol": h["protocol"],
                    "price": h["price"],
                    "original": h["original"],
                    "base_model": h["base_model"],
                }
                # 只有机场孪生跳带 proxy；直连跳不写这个键，存量 alias map 里的
                # 条目因此看起来和以前一模一样。
                if h.get("proxy"):
                    hop["proxy"] = h["proxy"]
                chain.append(hop)
            legacy_ids: list[str] = []
            for h in group:
                for lid in h.get("legacy_ids") or [h["original"], h["upstream"]]:
                    if lid not in legacy_ids:
                        legacy_ids.append(lid)
            entry = dict(group[0])
            entry.update({
                "name": name,
                "abbr": abbr,
                "protocol": "chat" if protocol == "merged" else protocol,
                "channel": chain[0]["channel"],
                "upstream": chain[0]["upstream"],
                "base": chain[0]["base"],
                "base_model": base_model,
                "price": chain[0]["price"],
                "chain": chain,
                "fallbacks": [c["upstream"] for c in chain[1:]],
                "legacy_ids": legacy_ids,
                "is_free_entry": is_free_entry,
            })
            if dropped:
                entry["dropped_hops"] = dropped
            entries.append(entry)
    return entries


def load_pools(path: Path) -> list[dict]:
    """集合体定义：每个池子是一条按顺序试的长链路。文件不存在就跳过。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except Exception as exc:
        print(f"warning: 读不了集合体定义 {path}（{exc}），本次不生成池子", file=sys.stderr)
        return []
    return [pool for pool in (data.get("pools") or []) if pool.get("name") and pool.get("hops")]


def pool_entries(pools: list[dict], slot: str) -> list[dict]:
    """把池子变成合成条目：一条显示名，chain 是整串上游。

    池内每一跳都是千问渠道（QW），价格取 `price_of`；试用窗口外整池无价 -> 不生成。
    """
    entries: list[dict] = []
    for pool in pools:
        hops: list[dict] = []
        for upstream in pool["hops"]:
            price = price_of("QW", upstream, {}, {}, slot)
            if price is None:
                continue
            hops.append({
                "upstream": upstream,
                "base": QW_BASE,
                "channel": "QW",
                "price": round(float(price), 2),
                "original": "qwen:" + upstream,
                "base_model": upstream,
            })
        if not hops:
            continue
        entries.append({
            "name": str(pool["name"]),
            "abbr": str(pool["name"]),
            "protocol": "messages",
            "channel": "QW",
            "upstream": hops[0]["upstream"],
            "original": hops[0]["original"],
            "base": QW_BASE,
            "base_model": hops[0]["base_model"],
            "price": hops[0]["price"],
            "chain": hops,
            "fallbacks": [hop["upstream"] for hop in hops[1:]],
            "legacy_ids": [str(pool["name"])],
            "is_free_entry": all(hop["price"] <= 0 for hop in hops),
            "is_pool": True,
            "label": str(pool.get("label") or ""),
        })
    return entries


CHANNEL_PREFIX = {"CN": "cn:", "GB": "global:", "QD": "qoder:", "OC": "oc:",
                  "QW": "qwen:", "QN": "qn:", "GM": "gem:", "HJ": "hjm:"}


def hop_specs(protocol: str, hop: dict) -> list[str]:
    """一个跳能被名单命中的写法：裸名 + 带渠道前缀的显式写法。

    名单允许写显式渠道（`chat:qoder:Qwen3.8-Max` / `chat:oc:qwen3.8-max`），因为同一
    upstream 名在不同渠道是不同的跳（qwen3.8-max 同时在 Qoder 与 OC）。只比裸名的话，
    显式条目的跳永远命中不了名单 —— 既不判主力，也排不到名单名额。
    """
    prefix = CHANNEL_PREFIX.get(str(hop.get("channel") or ""), "")
    out: list[str] = []
    for value in (hop.get("upstream"), hop.get("base_model")):
        if not value:
            continue
        bare = f"{protocol}:{value}"
        if bare not in out:
            out.append(bare)
        if prefix and f"{protocol}:{prefix}{value}" not in out:
            out.append(f"{protocol}:{prefix}{value}")
    return out


def _picked(entry: dict, hop: dict, wanted: set[str]) -> bool:
    """按 `<协议>:<上游>` 命中：协议是必需的，同型号的 chat / 桥接版名字一样。"""
    protocol = str(entry.get("protocol") or "chat")
    return any(spec in wanted for spec in hop_specs(protocol, hop))


def _version_of(entry: dict) -> tuple[int, ...]:
    """上游 id 里的第一个版本号（`muse-spark-1.3-contributor` → (1, 3)）。

    用于判断「这是不是这家公司更新的一代」。只取第一段数字：`hy3-x` 与 `hy3`
    都是 (3,)，同代；`mimo-v2.6-pro` (2, 6) 新于 `mimo-v2.5` (2, 5)。
    """
    for hop in entry["chain"]:
        for value in (hop.get("base_model"), hop.get("upstream")):
            m = re.search(r"(\d+(?:\.\d+)*)", str(value or ""))
            if m:
                return tuple(int(x) for x in m.group(1).split("."))
    return ()


def _vendor_of_entry(entry: dict) -> str | None:
    """条目的厂商标记；认不出来的（OTHER）不参与自动收录，免得把杂项堆进省钱组。"""
    vendor = vendor_of(str(entry.get("abbr") or ""))
    return None if vendor == "OTHER" else vendor


def pick_auto_low(entries: list[dict], arena_targets: dict[tuple[str, str], dict]) -> set[int]:
    """按厂商自动补「这家公司的代表型号」，返回要自动收录的条目 id 集合。

    口径（用户 2026-11-02）：省钱组是「每家公司一个特色型号」的人工名单，但
    **新冒出来的一家公司**、或**这家公司更新的一代**，不该因为没写进名单就丢掉。
    规则：
      · 只考虑 0 < 价格 ≤ LOW_MAX 的条目（省钱档）；
      · 每个厂商最多自动补 1 条，取版本号最高者（同版本取便宜的）；
      · 该厂商还没有任何代表（主力或省钱里都没有）→ 收录；
        已有代表但新条目版本更高（这家出了新一代）→ 也收录；
      · 人工点名的条目永远优先，自动条目排在组尾。
    """
    represented: dict[str, list[tuple[int, ...]]] = {}
    for entry in entries:
        if entry.get("is_pool"):
            continue
        manual = (
            any(_picked(entry, hop, MAIN_IDS) for hop in entry["chain"])
            or any(_picked(entry, hop, LOW_PICKS) for hop in entry["chain"])
            or any((hop["channel"], hop["upstream"]) in arena_targets for hop in entry["chain"])
        )
        if not manual:
            continue
        vendor = _vendor_of_entry(entry)
        if vendor:
            represented.setdefault(vendor, []).append(_version_of(entry))

    best: dict[str, tuple[tuple[int, ...], float, dict]] = {}
    for entry in entries:
        if entry.get("is_pool"):
            continue
        price = float(entry["price"])
        if price <= 0 or price > LOW_MAX:
            continue
        if any(_picked(entry, hop, MAIN_IDS) for hop in entry["chain"]):
            continue
        if any(_picked(entry, hop, LOW_PICKS) for hop in entry["chain"]):
            continue
        if any((hop["channel"], hop["upstream"]) in arena_targets for hop in entry["chain"]):
            continue
        vendor = _vendor_of_entry(entry)
        if not vendor:
            continue
        version = _version_of(entry)
        current = best.get(vendor)
        # 版本高者胜；同版本取便宜的（价格取负号排进元组）。
        if current is None or (version, -price) > (current[0], -current[1]):
            best[vendor] = (version, price, entry)

    picked: set[int] = set()
    for vendor, (version, _, entry) in best.items():
        have = represented.get(vendor) or []
        if have and not any(version > v for v in have):
            continue
        picked.add(id(entry))
    return picked


def pick_quota_dropped(entries: list[dict], arena_targets: dict[tuple[str, str], dict],
                       auto_ids: set[int] | None = None) -> set[int]:
    """每厂商最多留 VENDOR_QUOTA 个省钱组代表，返回要裁掉的那批 entry id。

    只针对「人工白名单命中」的条目（主力与自动补位不动）：白名单是严格有序的
    LOW_ORDER，历史上按「先想到谁写谁」随手加，腾讯一口气占了 4 个
    （cn:hy3-x / cn:hy3 / cn:hy4free / cn:hy4-preview-f）。用户口径是每家 1–2 个
    特色型号，所以超出的必须裁。裁谁：版本号高者优先，同版本贵者优先 ——
    贵的那个通常是这家旗舰，能在组里代表厂商。
    """
    buckets: dict[str, list[tuple[tuple[int, ...], float, int]]] = {}
    for entry in entries:
        if entry.get("is_pool"):
            continue
        if not any(_picked(entry, hop, LOW_PICKS) for hop in entry["chain"]):
            continue
        if float(entry["price"]) <= 0:
            # 免费组不占配額：那里的多家型号是额度体系的产物，不是「特色型号」。
            continue
        vendor = _vendor_of_entry(entry)
        if not vendor:
            continue
        buckets.setdefault(vendor, []).append(
            (_version_of(entry), float(entry["price"]), id(entry))
        )

    dropped: set[int] = set()
    report = []
    for vendor, rows in buckets.items():
        if len(rows) <= VENDOR_QUOTA:
            continue
        rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
        for _, _, entry_id in rows[VENDOR_QUOTA:]:
            dropped.add(entry_id)
        report.append(f"{vendor} {len(rows)}→{VENDOR_QUOTA}")
    if report:
        print("配额裁剪：" + "，".join(report), file=sys.stderr)
    return dropped


def entry_group(entry: dict, arena_targets: dict[tuple[str, str], dict],
                auto_ids: set[int] | None = None,
                quota_dropped: set[int] | None = None) -> tuple[str, str]:
    """Return (group, reason) for a merged entry. `drop` = 不收录。"""
    # 集合体是「一整串上游」的人造条目：它的跳会包含很多被单型号名单点名的 id，
    # 按跳匹配会把它误吸进主力（91 跳的快速池命中 deepseek-v4.1-flash 的桥接版）。
    # 池子只按价格归组 —— 0 积分就是免费。
    if entry.get("is_pool"):
        return ("free", "") if entry["price"] <= 0 else ("drop", "")
    for hop in entry["chain"]:
        if _picked(entry, hop, MAIN_IDS):
            return "main", "manual"
    for hop in entry["chain"]:
        if (hop["channel"], hop["upstream"]) not in arena_targets:
            continue
        if any(hint in str(hop["upstream"]).lower() for hint in MAIN_UPSTREAM_HINTS):
            return "main", "arena"
    price = entry["price"]
    if price <= 0:
        return "free", ""
    if any(_picked(entry, hop, LOW_PICKS) for hop in entry["chain"]):
        # 严格白名单命中即进省钱组，不受 LOW_MAX 价格上限约束
        # （小米 MiMo-2.6-Pro 0.19 也借此留在组里当厂商旗舰）。
        # 但每厂商最多 VENDOR_QUOTA 个：腾讯在白名单里堆了 4 个（cn:hy3-x / hy3 /
        # hy4free / hy4-preview-f），超出部分降级为 drop，名单交给 _quota_dropped 裁定。
        if quota_dropped and id(entry) in quota_dropped:
            return "drop", "quota"
        return "low", ""
    if auto_ids and id(entry) in auto_ids:
        # 名单外但价格在省钱档、且是该厂商的新公司/新一代 —— 见 pick_auto_low。
        return "low", "auto"
    # 「超价不收」落点：价格 > 0、又未命中 MAIN_IDS / LOW_PICKS 白名单或 auto_ids
    # 的条目在此丢弃。省钱档上限 LOW_MAX = DEEPSEEK_BASELINE_CREDITS（DeepSeek 标准，
    # 0.11）由 pick_auto_low 判定；LOW_PICKS 命中可豁免该上限（见上方白名单分支），
    # 因此 docstring 里「> 0.11 即丢」只是简化描述，实际以本函数分支为准。
    return "drop", ""


# "high"（高耗）已不产出，但保留标签：迁移期的旧 alias map 里还有这一组，
# 漂移检测要能读得懂它，才不会在收缩当天报 KeyError。
_GROUP_LABELS = {"main": "主力", "free": "免费", "low": "省钱", "drop": "不收录", "high": "高耗"}


def _hop_label(hop: dict) -> str:
    return f"{hop.get('channel')}:{hop.get('upstream')}@{hop.get('price')}"


def _entry_signature(entry: dict) -> dict:
    chain = entry.get("chain") or []
    hops = [_hop_label(h) for h in chain] if chain else [_hop_label(entry)]
    return {
        "group": str(entry.get("group") or ""),
        "price": round(float(entry.get("price") or 0.0), 2),
        "chain": hops,
    }


def proposed_signature(grouped: dict[str, list[dict]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for group, rows in grouped.items():
        for row in rows:
            entry = dict(row)
            entry["group"] = _GROUP_LABELS[group]
            out[row["new_id"]] = _entry_signature(entry)
    return out


def drift_report(grouped: dict[str, list[dict]], existing_models: dict) -> dict[str, list]:
    """重算结果与现有 alias map 的差异。

    `sync_report.py` 比的是「上一版 alias map」和「这一版」——两边都来自同一份
    缓存时，一个稳定存在的偏差永远不会显示成变化。这里比的是「现有产物」和
    「按当前价格源重算的结果」，是唯一能抓到价格冻结这类 bug 的检查。
    """
    # `main` 里的盘前收窄 / 摘要模式（--only-summary 之类）在 grouped 不外泄时
    # 直接返空：差集算法在空新表上会把整张表判成「消失」，那是最贵的一种误报。
    if not grouped:
        print("WARN: 重算结果为空，漂移检查跳过（不代表没有漂移）", file=sys.stderr)
        return {"added": [], "removed": [], "group_changed": [], "price_changed": [], "chain_changed": []}
    proposed = proposed_signature(grouped)
    current = {name: _entry_signature(entry) for name, entry in (existing_models or {}).items()}
    added = sorted(set(proposed) - set(current))
    removed = sorted(set(current) - set(proposed))
    group_changed, price_changed, chain_changed = [], [], []
    for name in sorted(set(proposed) & set(current)):
        old, new = current[name], proposed[name]
        if old["group"] != new["group"]:
            group_changed.append((name, old["group"], new["group"]))
        if old["price"] != new["price"]:
            price_changed.append((name, old["price"], new["price"]))
        if old["chain"] != new["chain"]:
            chain_changed.append((name, old["chain"], new["chain"]))
    return {
        "added": added,
        "removed": removed,
        "group_changed": group_changed,
        "price_changed": price_changed,
        "chain_changed": chain_changed,
    }


def print_drift(drift: dict[str, list]) -> None:
    total = sum(len(v) for v in drift.values())
    if total == 0:
        print("\n无漂移：现有 alias map 与按当前价格源重算的结果一致")
        return
    print(f"\n发现漂移 {total} 处（现有 alias map vs 当前价格源重算）：")
    if drift["added"]:
        print("  新增：", ", ".join(drift["added"]))
    if drift["removed"]:
        print("  消失：", ", ".join(drift["removed"]))
    for name, old, new in drift["price_changed"]:
        print(f"  价格：{name}  {old:g} -> {new:g}")
    for name, old, new in drift["group_changed"]:
        print(f"  分组：{name}  {old or '-'} -> {new}")
    for name, old, new in drift["chain_changed"]:
        print(f"  链路：{name}")
        print(f"    旧：{' -> '.join(old)}")
        print(f"    新：{' -> '.join(new)}")


QUOTA_WINDOWS = Path.home() / ".zcode" / "v2" / "quota-windows.json"


def write_quota_windows(path: Path = QUOTA_WINDOWS) -> None:
    """把渠道额度窗口落成独立文件，供 sync_report.py 与客户端只读消费。

    为什么单独落一份：这两个日期不影响今天的分组，不该参与选模计算（否则每天
    都报漂移）；但也不能只躺在代码常量里 —— 2026-11-06 之前 QN 限免只剩 24 天、
    QW 试用池只剩 39 天，全仓没有任何地方提醒过。
    """
    today = datetime.now().date()
    rows = [
        ("QN", QN_FREE_UNTIL,
         "七牛限免（conatus-free / kimi-k3-free），到期后这两条直接从配置消失"),
        ("QW", QW_TRIAL_UNTIL,
         "千问每模型 1M tokens 试用池，到期后边际成本从 0 变真钱"),
        ("QW", QW_CREDIT_UNTIL,
         "千问 ¥300 预付额度，到期作废、用不完不退"),
    ]
    windows = []
    for channel, until, note in rows:
        try:
            end = datetime.strptime(until, "%Y-%m-%d").date()
        except ValueError:
            continue
        windows.append({
            "channel": channel,
            "until": until,
            "days_left": (end - today).days,
            "note": note,
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "windows": windows},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
    for item in windows:
        if item["days_left"] <= 30:
            mark = "已过期" if item["days_left"] < 0 else f"剩 {item['days_left']} 天"
            print(
                f"WARN: {item['channel']} 额度窗口 {item['until']}（{mark}）—— {item['note']}",
                file=sys.stderr,
            )


def sync_deepseek_harness(config_path: Path) -> None:
    """Project the just-written ZCode config into a local DeepSeekRuntime install.

    This is deliberately best-effort: DSH is an optional client on this machine,
    and a bad DSH profile must never turn a successful ZCode sync into a failed
    cron run. The standalone ``tools/dsh_sync.py --check`` remains the strict
    drift check.
    """
    dsh_home = Path(os.environ.get("DSH_HOME", str(Path.home() / ".dsh")))
    profile = os.environ.get("DSH_PROFILE", "desktop")
    patch = dsh_home / "profiles" / profile / "cordis.patch.yml"
    script = REPO / "tools" / "dsh_sync.py"
    if not patch.exists() or not script.exists():
        return
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--apply", "--config", str(config_path)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"WARN: DeepSeekHarness 同步未执行：{exc}", file=sys.stderr)
        return
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        print(
            "WARN: DeepSeekHarness 同步失败（ZCode 配置已写入）："
            + (detail[-1] if detail else f"exit {proc.returncode}"),
            file=sys.stderr,
        )
        return
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    print("DeepSeekHarness: " + (lines[-1] if lines else "已同步"))


def _probe_entry(row: dict, probe: dict, legacy: dict) -> dict:
    """按 display id / 上游 id / legacy id 找出该条目对应的探测记录。

    顺序与 --probe-file 过滤块一致：新 ID → raw → 每一跳的 upstream/original →
    反查 legacy。返回空 dict 表示这一轮没探到它。
    """
    candidates = [row.get("new_id"), row.get("raw")]
    for hop in row.get("chain") or []:
        candidates += [hop.get("upstream"), hop.get("original")]
    reverse: list[str] = []
    for old_id, new_id in (legacy or {}).items():
        if new_id == row.get("new_id"):
            reverse.append(old_id)
    candidates += reverse
    return next((probe[c] for c in candidates if c in probe), {})


def apply_probe_filter(grouped: dict[str, list[dict]], probe: dict,
                       existing_models: dict, legacy: dict,
                       skipped: list[str]) -> tuple[list[str], list[str]]:
    """按探测结果摘掉确认死掉的型号，主力组只报不删。

    只有「上游明确说没有这个型号」（unavailable，404）才摘。其余非 ok 状态
    都是这一次请求的运气问题，不是型号死活的证据：
      · queued / rate_limited / timeout —— 本来就该留；
      · blocked —— 地区/权限拒绝，通常是这条出口进不去（机场孪生跳就是为它存在的）；
      · error —— 连 HTTP 码都没拿到（WinError 10054 / 连接重置），最没有资格判定型号。
    2026-11-10 12:00 的部署重启 (zgate.exe.bak-deploy-20261110-120031) 打断了在途
    探测：beam-free / qiniu/conatus-free 记成 error，claude-haiku-5-5 的 403 地区
    拒绝被写成 unavailable，三条 ever_ok=true 的型号就这样从配置里消失，
    用户侧看到的是「Beam 直连连不上」。

    2026-11-11 再补一条：**主力组成员不许当场删**。主力是用户在模型选择器里
    点名的对象，DSH 侧 zcode-main 的清单由这份配置投影而来，缺了型号不会降级
    而是硬失败（pi-ai: provider "zcode-main" has no configured model
    "Gemini-AIS"）。那天 AIS 一次 45s 超时 + ever_ok 为空就被摘掉，用户整场
    会话卡死在报错上。主力组改为「保留 + 记一条待核实」，真下架的型号上游会
    回 unavailable/404，那条分支仍然照删。

    返回 (transient_kept, suspect_main)。
    """
    transient = {"queued", "timeout", "rate_limited", "blocked"}
    transient_kept: list[str] = []
    suspect_main: list[str] = []
    for group, rows in grouped.items():
        kept = []
        for row in rows:
            entry = _probe_entry(row, probe, legacy)
            status = entry.get("status")
            # 旧版探活把 403 写成 unavailable（2026-11-10 12:02 的账本正是如此：
            # claude-haiku-5-5 http=403 status=unavailable），历史账本不能拿
            # 来判型号死刑，按地区/权限拒绝处理。
            if status == "unavailable" and entry.get("http") == 403:
                status = "blocked"
            # error 不看 ever_ok：网络层失败连响应都没有，不能当「型号不存在」用。
            if status in ("ok", "error") or (status in transient and entry.get("ever_ok")):
                kept.append(row)
            elif group == "main":
                # 主力组只报不删，理由见 docstring。
                kept.append(row)
                if entry:
                    suspect_main.append(f"{row.get('new_id')} (probe {status or 'not probed'})")
                else:
                    transient_kept.append(
                        f"{row.get('new_id')} (no probe entry, kept: existing model)")
            elif not entry and row.get("new_id") in existing_models:
                # Renamed since the last probe: the model was already in
                # the working config, so keep it until the next probe.
                kept.append(row)
                transient_kept.append(
                    f"{row.get('new_id')} (no probe entry, kept: existing model)")
            else:
                skipped.append(f"{row.get('new_id')} (probe {status or 'not probed'})")
        grouped[group] = kept
    return transient_kept, suspect_main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="写入 provider_config.json 与 alias map")
    parser.add_argument("--check", action="store_true",
                        help="只做漂移检测：把重算结果与现有 alias map 比对，有差异退出码 1，不写盘")
    parser.add_argument("--probe-max-age-hours", type=float, default=72.0,
                        help="探测结果超过该小时数视为未知（默认 72；0 = 不设限）")
    parser.add_argument("--config", help="provider_config.json 路径")
    parser.add_argument("--alias-map", help="alias map 路径")
    parser.add_argument("--max-price", type=float, default=0.0,
                        help="高耗组的价格上限（默认 0 = 不设上限）")
    parser.add_argument("--slot", choices=("auto", "peak", "offpeak"), default="auto",
                        help="取价时段：auto 按当前时间、peak 峰价、offpeak 谷价")
    parser.add_argument("--probe-file",
                        help="model_probe.py 的结果；只保留 ok（或曾 ok 的瞬时限流）")
    parser.add_argument("--arena-main",
                        help=f"榜单候选文件（默认 {DEFAULT_ARENA}）")
    parser.add_argument("--arena", action="store_true",
                        help="允许榜单自动扩主力（默认关闭：它会把主力越塞越肿）")

    parser.add_argument("--scores", nargs="?", const=str(DEFAULT_SCORES),
                        help="读竞技榜分数文件（默认 ~/.zcode/v2/model-scores.json）；低于门槛的白名单条目降级为不收录，只降不升")
    parser.add_argument("--no-scores", action="store_true", help="忽略分数文件")
    parser.add_argument("--no-arena", action="store_true",
                        help="兼容旧参数：榜单本来就是默认关闭的")
    parser.add_argument("--pools",
                        help=f"集合体定义（默认 {POOLS_FILE.name}；一条显示名对应一串上游）")
    parser.add_argument("--no-pools", action="store_true",
                        help="忽略集合体定义，只生成单型号条目")
    parser.add_argument("--force-unpriced", action="store_true",
                        help="允许在某个渠道全部无价时仍然 --apply（默认拒绝，避免整批剔除）")
    parser.add_argument("--no-dsh", action="store_true",
                        help="--apply 时不把最终三组投影到本机 DeepSeekRuntime")
    args = parser.parse_args()

    path = config_path(args.config)
    if not path.exists():
        raise SystemExit(f"找不到 ZCode 配置：{path}")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    alias_file = alias_path(args.alias_map)
    existing = {}
    if alias_file.exists():
        try:
            existing = json.loads(alias_file.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing_models = existing.get("models") or {}
    legacy = dict(existing.get("legacy") or {})
    wb, qd = wb_prices(), qd_prices()
    items = inventory(cfg, existing_models, legacy)
    # 白名单是权威：名单点名但当前配置里没有的型号，从价格源补一条候选。
    # 不补的话「把 hy4std 提进主力」这类改动永远只改名单、不产条目。
    # 比对口径分两种：
    #   · 白名单显式写了渠道（`chat:qoder:Qwen3.8-Flash`、`chat:cn:hy3`）→ 按
    #     (渠道, 裸名) 比。同一 upstream 名在不同渠道是不同的跳，只按裸名比会把新
    #     渠道的跳当重复丢掉 —— 2026-11-06 Qoder 免费 qwen3.8-flash 就是这样被吞的。
    #   · 没写渠道（`chat:Qwen3.8-Max`）→ 仍按裸名比：classify 只能猜 OC，会和
    #     已在 QD 下的同一条重复。
    have = {_bare(str(item.get("upstream") or "")) for item in items}
    have |= {str(item.get("base_model") or "") for item in items}
    have_ch = {
        (str(item.get("channel") or ""), _bare(str(item.get("upstream") or "")))
        for item in items
    }
    extra = []
    for item in whitelist_items(MAIN_ORDER + LOW_ORDER):
        bare = _bare(str(item.get("upstream") or ""))
        base = str(item.get("base_model") or "")
        if item.get("explicit_channel"):
            if (str(item.get("channel") or ""), bare) in have_ch:
                continue
        elif bare in have or base in have:
            continue
        extra.append(item)
    if extra:
        print(
            "白名单补入未配置型号：" + "、".join(str(item.get("raw")) for item in extra),
            file=sys.stderr,
        )
        items.extend(extra)
    entries = family_entries(items, wb, qd, args.slot)
    pool_file = Path(args.pools).expanduser() if args.pools else POOLS_FILE
    pool_rows = [] if args.no_pools else pool_entries(load_pools(pool_file), args.slot)
    entries.extend(pool_rows)
    raw = raw_models(cfg, existing_models, legacy)
    arena_file = arena_main_path(args.arena_main)
    arena_targets = load_arena_targets(arena_file) if (args.arena and not args.no_arena) else {}

    # Copy the original model rule (optionSpecs / properties) before removing
    # the old rules. A renamed id no longer matches ZCode's builtin patterns,
    # so models that need an empty thinking map must carry it explicitly.
    old_rules = {}
    for entry in model_rules(cfg):
        old_rules.setdefault(str(entry.get("modelId")), entry.get("config") or {})

    grouped: dict[str, list[dict]] = {key: [] for key in GROUPS}
    skipped: list[str] = []
    used: set[str] = set()
    # 上一版的名字按 (渠道, 上游, 协议) 记下来：同一个 hop 继续用旧名，
    # 否则配置里混进原始 id 时同名模型的命名会按出现顺序翻转，
    # 用户会话里选的 "MiniMax-M2.7" 会悄悄换到另一个上去游。
    prev_names: dict[tuple[str, str, str], str] = {}
    for prev_name, prev_entry in existing_models.items():
        for hop in prev_entry.get("chain") or [prev_entry]:
            key = (
                str(hop.get("channel") or prev_entry.get("channel") or ""),
                str(hop.get("upstream") or prev_entry.get("upstream") or ""),
                str(prev_entry.get("protocol") or ""),
            )
            prev_names.setdefault(key, prev_name)
    # 省钱组的自动补位：新公司/新一代型号即使没写进 LOW_ORDER 也收录一条。
    auto_low = pick_auto_low(entries, arena_targets)
    # 每厂商配额：先裁定要裁谁，再交给 entry_group 分组（同一份名单只算一次）
    quota_dropped = pick_quota_dropped(entries, arena_targets, auto_low)
    # 竞技榜分数：只降不升，把明显落后于锚定型号的白名单条目也裁掉
    if args.scores and not args.no_scores:
        quota_dropped |= pick_scores_dropped(
            entries, load_scores(Path(args.scores).expanduser()), arena_targets)
    for entry in entries:
        group, main_reason = entry_group(entry, arena_targets, auto_low, quota_dropped)
        if group == "drop":
            if float(entry["price"]) <= LOW_MAX:
                skipped.append(
                    f"{entry['name']} (price {entry['price']:g}，同厂商已有同代/更高代代表)"
                )
            else:
                skipped.append(
                    f"{entry['name']} (price {entry['price']:g} > 省钱档 {LOW_MAX:g})"
                )
            continue
        if args.max_price > 0 and entry["price"] > args.max_price and group != "main":
            skipped.append(f"{entry['name']} (price {entry['price']:g} > {args.max_price:g})")
            continue
        new_id = entry["name"]
        for hop in entry["chain"]:
            prev = prev_names.get((hop["channel"], hop["upstream"], entry["protocol"]))
            if not prev or prev in used:
                continue
            # 只继承「同名去冲突」后缀（-Msg / -Resp / -2）；-Free 是状态后缀，
            # 跟着价格走，不能从上一版继承。
            if prev == entry["name"] or re.fullmatch(
                re.escape(entry["name"]) + r"-\d+(?:-\d+)?", prev
            ):
                new_id = prev
                break
        if new_id in used:
            # Same name, different protocol (e.g. a bridged variant).
            suffix = "-Msg" if entry["protocol"] == "messages" else "-Resp" if entry["protocol"] == "responses" else "-2"
            candidate = entry["abbr"] + suffix
            counter = 2
            while candidate in used:
                candidate = f"{entry['abbr']}{suffix}-{counter}"
                counter += 1
            new_id = candidate
        used.add(new_id)
        entry = dict(entry)
        entry.update({"group": group, "new_id": new_id, "main_reason": main_reason})
        grouped[group].append(entry)

    # 组内顺序由人工白名单决定，不按"厂商最低价"排 —— 否则便宜厂商会顶到前面
    # 把列表打乱（HY 0.05 / MiMo 0.06 会抢在 DeepSeek 之前，正是用户看到 mimo
    # 排到最后的反例：那时 raw id 没归并进厂商块）。主力按 MAIN_ORDER、省钱按
    # LOW_ORDER；不在名单里的模型（理论上不会进组）排末尾。
    def _pick_rank(row: dict, order: list[str]) -> int:
        """条目命中的名单序号；没命中的排末尾。组内顺序由人工名单决定。"""
        protocol = str(row.get("protocol") or "chat")
        for hop in row["chain"]:
            specs = hop_specs(protocol, hop)
            for j, name in enumerate(order):
                if name in specs:
                    return j
        return len(order)

    # 匿名/无公司代号的模型（Beam / Space-Bunny / Conatus / Iceman）一律沉到
    # 本组最下面 —— 这是用户 2026-11-09 反复强调的硬规则，且优先于人工名单：
    # 光靠 LOW_ORDER 的位置不够，因为名单外的自动补位条目会插到名单条目之后、
    # 匿名条目之前，于是"无 logo 的夹在中间"。anonymous_rank 排在最外层就堵死这条路。
    # DSH GUI 侧不做二次排序（orderModelProviders 只提前 account/official），
    # 这里排成什么顺序，界面就是什么顺序。
    for group, rows in grouped.items():
        if group == "main":
            rows.sort(key=lambda r: (anonymous_rank(r["abbr"]),
                                     _pick_rank(r, MAIN_ORDER), r["new_id"]))
        elif group == "low":
            rows.sort(key=lambda r: (anonymous_rank(r["abbr"]),
                                     _pick_rank(r, LOW_ORDER), r["price"], r["new_id"]))
        else:
            # 免费组：公司型号优先（HY3 > HY4-Free），匿名代号垫底，再按价格
            rows.sort(key=lambda r: (0 if r["new_id"].startswith("HY") else 1,
                                     anonymous_rank(r["abbr"]),
                                     r["price"], r["new_id"]))

    transient_kept: list[str] = []
    if args.probe_file:
        probe_path = Path(args.probe_file).expanduser()
        if not probe_path.exists():
            raise SystemExit(f"找不到探测结果：{probe_path}")
        probe = json.loads(probe_path.read_text(encoding="utf-8"))
        probe, stale_probe = _fresh_probe(probe, args.probe_max_age_hours)
        if stale_probe:
            print(
                f"WARN: {len(stale_probe)} 条探测结果超过 "
                f"{args.probe_max_age_hours:g} 小时，按「未知」处理"
                f"（不会据此删除模型）：{', '.join(sorted(stale_probe)[:5])}"
                + (" …" if len(stale_probe) > 5 else ""),
                file=sys.stderr,
            )
        transient_kept, suspect_main = apply_probe_filter(
            grouped, probe, existing_models, legacy, skipped)
        if transient_kept:
            print(
                "INFO: 无探测记录但上一版配置已有，保留待下轮复探："
                + "；".join(transient_kept),
                file=sys.stderr,
            )
        if suspect_main:
            # 主力组只降不删：写盘时仍保留，但每日日志必须点名，否则用户永远
            # 不知道选择器里那条「还能点但总超时」的模型正在被上游拖死。
            print(
                "WARN: 主力组成员本轮探测不健康，已按「只报不删」保留，"
                "若下一轮仍非 ok 请人工核实上游：" + "；".join(suspect_main),
                file=sys.stderr,
            )

    print("分组 / 新 ID / 原模型 / 协议 / 积分")
    for group in GROUPS:
        print(f"\n## {PROVIDER_NAMES[{'main':PROVIDER_MAIN,'free':PROVIDER_FREE,'low':PROVIDER_LOW}[group]]} ({len(grouped[group])})")
        for item in grouped[group]:
            print(f"  {item['new_id']:<34} {item['original']:<34} {item['protocol']:<10} {item['price']:.2f}")
            chain = item.get("chain") or []
            if chain:
                hops = " -> ".join(f"{h['channel']}:{h['upstream']}" for h in chain)
                print(f"  {'':<34} chain: {hops}")
    if pool_rows:
        print("## 集合体（%s）" % pool_file.name)
        for pool in pool_rows:
            head = " -> ".join(hop["upstream"] for hop in pool["chain"][:3])
            print(f"  {pool['name']:<16} {len(pool['chain'])} 跳  {head} …")
    arena_rows = [row for row in grouped["main"] if row.get("main_reason") == "arena"]
    if arena_rows:
        print(f"\n## 主力扩充来源（{arena_file.name}）")
        for row in arena_rows:
            hop = next((h for h in row["chain"]
                        if (h["channel"], h["upstream"]) in arena_targets), None)
            if hop is None:
                continue
            entry = arena_targets[(hop["channel"], hop["upstream"])]
            ratio = float(entry.get("ratio") or 0) * 100
            print(f"  {row['new_id']:<34} 分数 {entry.get('score')}（基准 {ratio:.1f}%）"
                  f" #{entry.get('rank')}  {entry.get('model')}")
    if skipped:
        print("\n跳过：")
        for line in skipped:
            print(f"  {line}")
    if transient_kept:
        print("\n保留（无探测记录，但已在上一版配置里）：")
        for line in transient_kept:
            print(f"  {line}")

    if _UNPRICED:
        detail = "、".join(f"{ch} {n} 个" for ch, n in sorted(_UNPRICED.items()))
        print(f"\nWARN: 因缺价未收录：{detail}（价格源不可用时先修复再 --apply）", file=sys.stderr)
        # 明细必须打出来：少了这一行，白名单点名的跳消失与「整渠道无价」不可区分。
        shown = _UNPRICED_HOPS[:12]
        if shown:
            print("  具体跳：" + "、".join(shown) +
                  (f"（共 {len(_UNPRICED_HOPS)} 条）" if len(_UNPRICED_HOPS) > len(shown) else ""),
                  file=sys.stderr)
    dead = [ch for ch, n in _CHANNEL_ITEMS.items() if n and _UNPRICED.get(ch, 0) == n]
    if dead and args.apply and not args.force_unpriced:
        print(
            f"ERROR: 渠道 {'、'.join(dead)} 的全部模型都没有价格，拒绝写入 —— "
            "这会把该渠道的模型整批从配置里剔除。修好价格源后重跑，或加 --force-unpriced。",
            file=sys.stderr,
        )
        return 1

    if args.check:
        drift = drift_report(grouped, existing_models)
        print_drift(drift)
        # 档位守门：这一轮算出来的继承链会抹掉已落盘档位就判失败。模型表本身
        # 漂移时上面的 drift 已经报 1；这里独立判定，两种漂移原因分开说清。
        lost_efforts = drifted_efforts(cfg)
        if lost_efforts:
            print("\n推理档位漂移（本轮同步会把已落盘的档位清空）：", file=sys.stderr)
            for line in lost_efforts:
                print("  - " + line, file=sys.stderr)
            print("  修复：tools/model_alias.py --apply 前先看 _inherit_efforts 的"
                  "继承链；不要靠手改 provider_config.json。", file=sys.stderr)
        return 1 if (any(drift.values()) or lost_efforts) else 0

    if not args.apply:
        print("\ndry run；加 --apply 写入 provider_config.json 与 alias map")
        return 0

    new_id_by_key = {}
    for rows in grouped.values():
        for item in rows:
            for hop in item["chain"]:
                new_id_by_key[(hop["channel"], hop["upstream"], item["protocol"])] = item["new_id"]
    for item in raw:
        key = (item["channel"], item["upstream"], item["protocol"])
        if key in new_id_by_key:
            legacy[item["raw"]] = new_id_by_key[key]
            legacy[item["original"]] = new_id_by_key[key]

    # Build the new config.
    template = next((r for r in provider_rules(cfg) if r.get("providerId") == PROVIDER_MAIN), None)
    if template is None:
        raise SystemExit(f"缺少模板 provider：{PROVIDER_MAIN}")
    access = copy.deepcopy((template.get("config") or {}).get("access") or {})
    group_name = (template.get("config") or {}).get("group") or "standard-personal"
    def _consistent_legacy_ids(row: dict) -> list[str]:
        """只留「这条记录真对得上」的 legacy id。

        带渠道前缀的 id（gem:ais-… / hjm:[福利]…）必须能对上该模型某一跳的
        upstream，对不上就是改名 / 拆族留下的陈旧映射：2026-11-10 把哈基米从
        Gemini-AIS 链里拆成独立模型时，AIS 的 legacy_ids 里还留着 hjm:[福利]…
        （上一轮它确实是 AIS 的一跳），不过滤会把这条 id 又指回 AIS，新模型同时
        继承了 7 个 gem:ais-… 的脏映射。不带前缀的 id（上游原名、旧显示名）不动：
        历史条目本来就允许跨名字解析。
        """
        chain = row.get("chain") or [{"upstream": row.get("upstream")}]
        upstreams = {_bare(h.get("upstream") or "") for h in chain}
        upstreams |= {_bare(row.get("upstream") or ""), _bare(row.get("original") or "")}
        # CHAIN_CAP 裁掉的跳也要认：老会话点名 ais-gemini-3.5-flash 时仍解析到
        # 本模型（只是链不会再打它），不能变成 404。
        upstreams |= {_bare(u) for u in row.get("dropped_hops") or []}
        out: list[str] = []
        for lid in row.get("legacy_ids") or [row["original"], row["upstream"]]:
            key = str(lid)
            if ":" in key and _bare(key) not in upstreams:
                continue
            if key not in out:
                out.append(key)
        return out

    new_providers = []
    new_model_rules = []
    alias_models = {}
    # 档位继承走 pick_rule_config：写盘与 --check 的漂移守门必须共用同一套逻辑，
    # 各写一份的话守门迟早和实际行为对不上（守门绿着、配置照样被清空）。
    all_rows = [row for group in ("main", "free", "low") for row in grouped[group]]
    inherited_configs = pick_rule_config(all_rows, cfg, old_rules)
    for group, provider_id in (("main", PROVIDER_MAIN), ("free", PROVIDER_FREE),
                               ("low", PROVIDER_LOW)):
        rows = grouped[group]
        ids = [row["new_id"] for row in rows]
        new_providers.append({
            "providerId": provider_id,
            "providerName": PROVIDER_NAMES[provider_id],
            "config": {
                "group": group_name,
                "access": copy.deepcopy(access),
                "api": {"type": "openai-chat-completions", "baseUrl": ROUTER_BASE},
                "personalModelIds": ids,
                "modelOrder": ids,
            },
        })
        for row in rows:
            # 继承源顺序与 family_entries 生成的名字对齐（raw 是显示名），再用显式
            # 上游名兜底；档位补齐在 pick_rule_config / _inherit_efforts 里做。
            config = copy.deepcopy(inherited_configs.get(str(row["new_id"])) or {})
            config["enabled"] = True
            meta = MODEL_META.get(str(row.get("upstream") or "").lower())
            if meta:
                if not config.get("properties"):
                    config["properties"] = copy.deepcopy(meta["properties"])
                specs = config.setdefault("optionSpecs", {})
                for key, value in copy.deepcopy(meta["optionSpecs"]).items():
                    specs.setdefault(key, value)
            if row["protocol"] != "chat":
                _enforce_non_chat_effort(config, row)
            new_model_rules.append({
                "modelId": row["new_id"],
                "config": config,
                "providerId": provider_id,
            })
            base = base_of(row["channel"])
            alias_models[row["new_id"]] = {
                "channel": row["channel"],
                "region": "",
                "upstream": row["upstream"],
                "base_model": row["base_model"],
                "base": base,
                "protocol": row["protocol"],
                "original": row["original"],
                "price": row["price"],
                "group": PROVIDER_NAMES[provider_id],
                "fallbacks": list(row.get("fallbacks") or []),
                "chain": list(row.get("chain") or []),
                "legacy_ids": _consistent_legacy_ids(row),
            }
            if row.get("dropped_hops"):
                alias_models[row["new_id"]]["dropped_hops"] = list(row["dropped_hops"])
            if row.get("is_pool"):
                alias_models[row["new_id"]]["kind"] = "pool"
                alias_models[row["new_id"]]["label"] = row.get("label") or ""
            if row.get("main_reason"):
                alias_models[row["new_id"]]["main_reason"] = row["main_reason"]
            for legacy_id in _consistent_legacy_ids(row):
                legacy[legacy_id] = row["new_id"]

    # 存量脏映射清理：磁盘上可能留着「带渠道前缀、却对不上目标任何一跳」的 legacy
    # 条目（拆族前的 hjm:[福利]… -> Gemini-AIS 就是），逐条对照 live 模型的跳表删掉。
    # 只处理带前缀的 key：裸名（上游原名、旧显示名）允许跨名字解析，不动。
    for _key, _target in list(legacy.items()):
        if ":" not in _key:
            continue
        _model = alias_models.get(_target)
        if not _model:
            continue
        _hops = {_bare(h.get("upstream") or "") for h in (_model.get("chain") or [_model])}
        _hops |= {_bare(u) for u in _model.get("dropped_hops") or []}
        if _bare(_key) not in _hops:
            legacy.pop(_key, None)
    valid_ids = set(alias_models)
    # 命名卫生：legacy 里可能残留「与 live 模型同名」的映射（改名后又把这个名字
    # 给了一个新模型，例如 2026-11-10 拆出来的 Gemini-3.8-Flash）。Resolve 先查
    # models，路由不受影响；但 legacy 留一条指向别人的同名记录会误导排查，一律丢掉。
    for _shadowed in [k for k in legacy if k in valid_ids]:
        legacy.pop(_shadowed, None)
    # 显示名改名兼容（NAME_RENAMES）：旧名的自指条目（"Gemini-3.8-Flash" ->
    # "Gemini-3.8-Flash"）在改名后 target 已不是任何 live id，下面那条
    # resolved_legacy 过滤会把整条丢掉，老会话选中的模型就解析不到。
    # 先补一条旧名 → 新名的映射，让过滤能顺着链走到 live id。
    # 用 setdefault：万一哪天旧名又变成某个 live 模型，真实条目优先。
    # setdefault 在这里不够用：legacy 里旧名的存量形态是自指
    # （"Gemini-3.8-Flash" -> "Gemini-3.8-Flash"），key 已存在时 setdefault
    # 什么都不做，自指条目照样在下面的过滤里被当死链丢掉 —— 两轮 --apply
    # 的对照实测过：只 setdefault 时旧名整条消失，老会话解析不到模型。
    # 所以只覆盖两种「没有可用出口」的情况，已经指向 live id 的映射一律不动：
    #   · 缺失（None）：改名后第一次落盘，直接补一条；
    #   · 自指（old -> old）：改名残留，改写成新名让链能走到 live id。
    for old_name, new_name in NAME_RENAMES.items():
        current = legacy.get(old_name)
        if current is None or current == old_name:
            legacy[old_name] = new_name

    # Follow rename chains (W/0.00/X -> W/0.03/X -> ...) so an id that has been
    # renamed twice still resolves to a live model instead of being dropped.
    resolved_legacy: dict[str, str] = {}
    for key, value in legacy.items():
        target = value
        seen: set[str] = set()
        while target not in valid_ids and target in legacy and target not in seen:
            seen.add(target)
            target = legacy[target]
        if target in valid_ids:
            resolved_legacy[key] = target
    legacy = resolved_legacy

    # 读取路径兼容 list/dict 两种形态（见 provider_rules），写入也必须归一化，
    # 否则 list 形态会在这里抛 TypeError，整轮 --apply 白跑。
    pcr = cfg["config"]["providerConfigRules"]
    if isinstance(pcr, list):
        pcr[:] = new_providers
    else:
        pcr["providerRules"] = new_providers
    cfg["config"]["providerOrder"] = PROVIDER_IDS
    cfg["config"]["modelConfigRules"]["providerModelRules"] = new_model_rules
    cfg["config"]["modelConfigRules"]["manualProviderModelRules"] = []

    stamp = time.strftime("%Y%m%d-%H%M%S") + "-" + f"{time.time_ns() % 1_000_000:06d}"
    backup = path.with_name(path.name + ".bak-alias-" + stamp)
    shutil.copy2(path, backup)
    tmp = path.with_name(path.name + ".tmp-alias")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)

    alias_file = alias_path(args.alias_map)
    alias_file.parent.mkdir(parents=True, exist_ok=True)
    alias_tmp = alias_file.with_name(alias_file.name + ".tmp")
    alias_tmp.write_text(json.dumps({
        "version": 1,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "slot": args.slot,
        "models": alias_models,
        "legacy": legacy,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(alias_tmp, alias_file)
    write_quota_windows()
    print(f"\n已写入 {path.name}（备份：{backup.name}）")
    print(f"已写入 {alias_file}")
    # Only project the real ZCode config by default. A caller using --config for
    # a fixture/sandbox must not overwrite the local DSH profile.
    if not args.no_dsh and args.config is None:
        sync_deepseek_harness(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
