#!/usr/bin/env python3
"""dsh_sync 的 dry-run 产物必须给每条 zcode-* provider 带上 429 快速失败策略。

回归背景：上游额度类 6004 在重置墙钟之前一直失败，默认 llm-retry 会把一次
429 放大成 5/5 重试。手工在 cordis.patch.yml 里加的 retryPolicy 会被每天
12:00 的定时同步重新生成 providers 时冲掉，所以策略必须由生成器注入。

跑法：python -B -m unittest discover -s tests -p "test_dsh_sync_retry_policy.py" -v
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import dsh_sync as S  # noqa: E402

EXPECTED_RETRY_POLICY = {
    "mode": "normal",
    "maxRetries": 1,
    "retryableCodes": ["EMPTY_RESPONSE", "SERVER", "TIMEOUT", "TRANSPORT"],
    "backoff": {
        "initialDelayMs": 500,
        "maxDelayMs": 3000,
        "jitterRatio": 0.1,
    },
}

PROVIDER_IDS = ["opencode-go-chat", "opencode-go-chat-free", "opencode-go-chat-fast"]
DSH_IDS = ["zcode-main", "zcode-free", "zcode-saver"]

MODELS = {
    "opencode-go-chat": ["DeepSeek-4.1", "HY3"],
    "opencode-go-chat-free": ["HY3", "Step-5-Preview"],
    "opencode-go-chat-fast": ["DeepSeek-4.1-Flash"],
}


def _fixture_config() -> dict:
    rules = []
    model_rules = []
    for i, pid in enumerate(PROVIDER_IDS):
        rules.append(
            {
                "providerId": pid,
                "providerName": f"分组{i}",
                "config": {
                    "modelOrder": MODELS[pid],
                    "api": {"baseUrl": "http://127.0.0.1:7871/v1"},
                    "access": {"apiKey": "fixture-key-not-a-secret"},
                },
            }
        )
        for mid in MODELS[pid]:
            model_rules.append(
                {
                    "providerId": pid,
                    "modelId": mid,
                    "config": {
                        "properties": {
                            "contextWindow": 131072,
                            "inputFormat": {"supportsImage": mid == "HY3"},
                        },
                        "optionSpecs": {
                            "maxOutputTokens": {"max": 8192},
                            "reasoningLevel": {"values": ["off", "high"], "map": "{}"},
                        },
                    },
                }
            )
    return {
        "config": {
            "providerConfigRules": {"providerRules": rules},
            "providerOrder": PROVIDER_IDS,
            "modelConfigRules": {"providerModelRules": model_rules},
        }
    }


OLD_PATCH = """- id: other-plugin
  config:
    keep: yes
- id: llm-pi-ai
  config:
    providers:
      zcode-main:
        displayName: 旧的手工配置
        api: openai-completions
        models:
          - id: OLD-MODEL
      custom-keep:
        displayName: 手工加的非 zcode provider
        api: openai-completions
        models:
          - id: CUSTOM
    extraKey: preserve-me
"""

CREDS = """refs:
  ZCODE_GATEWAY_KEY: "fixture-key-not-a-secret"
"""

MARK_BEGIN = "--- 投影后的 providers（dry-run，不写入）---"
MARK_END = "--- end ---"

# 纯内存夹具：bash 子进程在仓内无建目录权限，改用 VFS 拦截 Path 读写。
VIRTUAL_HOME = REPO / ".work" / "virtual-dsh-sync-fixture"


def _vfs() -> dict[str, str]:
    return {
        str(VIRTUAL_HOME / "provider_config.json"): json.dumps(_fixture_config()),
        str(VIRTUAL_HOME / "profiles" / "desktop" / "cordis.patch.yml"): OLD_PATCH,
        str(VIRTUAL_HOME / ".credentials.yaml"): CREDS,
    }


def _run_dry_run() -> tuple[int, str, dict]:
    """在内存 VFS 上跑真实 _main dry-run，返回 (退出码, stdout, 解析后的 providers)。"""
    files = _vfs()
    real_exists = Path.exists
    real_read_text = Path.read_text

    def fake_exists(self: Path) -> bool:
        return str(self) in files or real_exists(self)

    def fake_read_text(self: Path, *args, **kwargs) -> str:
        if str(self) in files:
            return files[str(self)]
        return real_read_text(self, *args, **kwargs)

    def deny_write(self: Path, *args, **kwargs):
        raise AssertionError("dry-run 不得写入任何文件: " + str(self))

    buf = io.StringIO()
    with mock.patch.object(Path, "exists", fake_exists),          mock.patch.object(Path, "read_text", fake_read_text),          mock.patch.object(Path, "write_text", deny_write),          mock.patch.object(S, "_effective_metadata", return_value={}),          contextlib.redirect_stdout(buf):
        code = S._main(
            [
                "--dsh-home", str(VIRTUAL_HOME),
                "--profile", "desktop",
                "--config", str(VIRTUAL_HOME / "provider_config.json"),
            ]
        )
    out = buf.getvalue()
    start = out.index(MARK_BEGIN) + len(MARK_BEGIN)
    end = out.index(MARK_END)
    providers = yaml.safe_load(out[start:end]) or {}
    return code, out, providers


class ModuleConstantTest(unittest.TestCase):
    def test_constant_matches_spec(self):
        self.assertEqual(S.RETRY_POLICY, EXPECTED_RETRY_POLICY)
        self.assertNotIn("RATE_LIMIT", S.RETRY_POLICY["retryableCodes"])
        self.assertEqual(S.RETRY_POLICY["backoff"], EXPECTED_RETRY_POLICY["backoff"])

    def test_each_route_gets_its_own_copy(self):
        provider = {
            "providerId": "opencode-go-chat",
            "providerName": "主力",
            "baseUrl": "",
            "modelIds": ["DeepSeek-4.1"],
        }
        _, a = S._build_route(provider, {}, {})
        _, b = S._build_route(provider, {}, {})
        self.assertEqual(a["retryPolicy"], EXPECTED_RETRY_POLICY)
        a["retryPolicy"]["maxRetries"] = 9
        self.assertEqual(b["retryPolicy"]["maxRetries"], 1)
        self.assertEqual(S.RETRY_POLICY["maxRetries"], 1)


class DryRunProjectedProvidersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.out, cls.providers = _run_dry_run()

    def test_exit_code_zero(self):
        self.assertEqual(self.code, 0)

    def test_stdout_shows_optimized_values(self):
        for token in (
            "retryPolicy（模块级常量）",
            '"maxRetries": 1',
            "EMPTY_RESPONSE",
            "TRANSPORT",
            "initialDelayMs",
            "maxDelayMs",
            '"jitterRatio": 0.1',
            "maxRetries: 1",
            "dry-run：加 --apply 才会写入",
        ):
            self.assertIn(token, self.out, token)

    def test_every_zcode_provider_has_full_policy(self):
        zcode = {k: v for k, v in self.providers.items() if k.startswith("zcode-")}
        self.assertEqual(sorted(zcode), sorted(DSH_IDS))
        for dsh_id, route in zcode.items():
            self.assertEqual(route["retryPolicy"], EXPECTED_RETRY_POLICY, dsh_id)

    def test_providers_are_complete(self):
        self.assertEqual(set(self.providers), set(DSH_IDS) | {"custom-keep"})
        self.assertEqual(self.providers["custom-keep"]["displayName"], "手工加的非 zcode provider")
        self.assertEqual(
            [m["id"] for m in self.providers["custom-keep"]["models"]], ["CUSTOM"]
        )

    def test_models_are_complete(self):
        for pid, dsh_id in zip(PROVIDER_IDS, DSH_IDS):
            route = self.providers[dsh_id]
            self.assertEqual([m["id"] for m in route["models"]], MODELS[pid], dsh_id)
            for model in route["models"]:
                self.assertEqual(model["contextWindow"], 131072)
                self.assertEqual(model["maxTokens"], 8192)
                self.assertEqual(
                    model["input"],
                    ["text", "image"] if model["id"] == "HY3" else ["text"],
                )
                # reasoningLevel.map == {} 的上游不生成 reasoningEfforts
                self.assertNotIn("reasoningEfforts", model)

    def test_other_patch_entries_and_keys_preserved(self):
        routes = {
            dsh_id: S._build_route(
                {
                    "providerId": pid,
                    "providerName": pid,
                    "baseUrl": "",
                    "modelIds": MODELS[pid],
                },
                {},
                {},
            )[1]
            for pid, dsh_id in zip(PROVIDER_IDS, DSH_IDS)
        }
        new_text, changed, item = S._merge_patch(OLD_PATCH, routes)
        self.assertTrue(changed)
        self.assertIn("- id: other-plugin", new_text)
        self.assertIn("keep: yes", new_text)
        self.assertEqual(item["config"]["extraKey"], "preserve-me")
        self.assertEqual(
            [m["id"] for m in item["config"]["providers"]["custom-keep"]["models"]],
            ["CUSTOM"],
        )


if __name__ == "__main__":
    unittest.main()
