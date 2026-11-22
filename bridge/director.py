#!/usr/bin/env python3
"""ER Echo — 战斗导演 sidecar（仅标准库）。

职责：
  1) 连接游戏内 DLL（NDJSON/TCP），收发状态与权重；
  2) 每 1–3 秒（或事件触发）调用一次 LLM，输出 10 维权重；
  3) 护栏：schema 校验、clamp、变化率、迟滞、策略冷却、超时兜底；
  4) 可选工具调用：换装 / 加点（白名单）。

用法：
  python director.py --mock                 # 不连游戏，打印假数据，自测
  python director.py --llm mock             # 连游戏，用规则假 LLM
  python director.py --llm openai --model gpt-4o-mini --api-key %OPENAI_API_KEY%
  python director.py --llm ollama --model qwen2.5:7b
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
import urllib.error
import urllib.request

from protocol import clamp, dumps, listen, LineReader, recv_json

WEIGHTS = [
    "aggression", "dodge_rate", "guard_rate", "combo_rate", "heal_priority",
    "spell_rate", "item_rate", "spacing", "target_switch",
]
STRATEGIES = {"hold_line", "pressure", "kite", "burst", "protect", "retreat", "observe"}

SYSTEM_PROMPT = """你是《艾尔登法环》里一名褪色者同伴的"战斗导演"。
你不能直接操控角色，只能调整它的行为权重（0~1 浮点），动作由游戏原生 AI 执行。
输入是当前战斗状态和你上一轮的权重；输出必须是一个 JSON 对象，不要任何解释文字。

输入状态（每 0.5~2 秒一条）：
  player: {{hp, fp, stam, level, runes}}   # 都是 0~1 的比例，level/runes 是数值
  clones: [{{npc, name, level, hp, dist}}] # 场上的同伴（你正在导演的就是它们）
  enemy:  {{npc, team, dist}} | null       # 距离玩家最近的敌对单位
  events: ["player_low_hp"|"player_dead"|"revive"|"enemy_engaged"|"enemy_dead"|
           "clone_summoned"|"clone_gone"]
  weights: 上一轮生效的权重

输出字段：
  weights: 对象，键为 {weights}，值 0~1。未给出的键保持不变。
  strategy: 可选，枚举 {strategies}。
  say: 可选，一句不超过 20 字的中文台词。
  reason: 可选，一句不超过 40 字的理由。
  confidence: 可选，0~1。
  loadout: 可选，换装（会被白名单+存在性检查，失败则整包丢弃）：
            {{"head":630000,"body":630100,"weapon_right":30080000}}，
            槽位名 = weapon_left/weapon_right/left2/right2/left3/right3/arrow*/bolt*/
            head/body/hands/legs/talisman1..4/covenant。
  upgrade: 可选，配合 loadout 里的武器槽使用（+N），游戏内会按 id+N 查表校验。
  stats: 可选，加点 {{"vigor":20,"mind":18}}，单向变化上限 ±20%。
  level: 可选，整数，同样限制 ±20%。
  rollback: 可选，true 表示撤销上一次换装。

原则：
  - 玩家血量低 → 提高 heal_priority / guard_rate / spacing，降低 aggression。
  - 敌人体型大/削韧高 → 提高 dodge_rate，降低 combo_rate。
  - 玩家被围攻 → 提高 aggression 吸引仇恨，或提高 dodge_rate 拉扯。
  - 变化要平滑，单次调整幅度不超过 0.15。
  - 换装/加点要克制：只在有明确理由时用，且一次只改一两件。
""".format(weights=WEIGHTS, strategies=sorted(STRATEGIES))


def default_weights() -> dict[str, float]:
    return {k: 0.5 for k in WEIGHTS}


class Guard:
    """把 LLM 的原始输出变成安全、平滑、可写入的权重。"""

    def __init__(self, max_delta: float = 0.15, hysteresis: float = 0.03,
                 strategy_cooldown: int = 3):
        self.max_delta = max_delta
        self.hysteresis = hysteresis
        self.strategy_cooldown = strategy_cooldown
        self.last_strategy = "observe"
        self.strategy_age = 99

    def apply(self, raw: dict, prev: dict[str, float]) -> tuple[dict[str, float], str]:
        out = dict(prev)
        for key, value in (raw.get("weights") or {}).items():
            if key not in WEIGHTS:
                continue
            try:
                target = clamp(float(value))
            except (TypeError, ValueError):
                continue
            delta = max(-self.max_delta, min(self.max_delta, target - prev[key]))
            candidate = clamp(prev[key] + delta)
            if abs(candidate - prev[key]) >= self.hysteresis:
                out[key] = round(candidate, 3)
        strategy = raw.get("strategy")
        if strategy not in STRATEGIES:
            strategy = self.last_strategy
        self.strategy_age += 1
        if strategy != self.last_strategy:
            if self.strategy_age >= self.strategy_cooldown:
                self.last_strategy = strategy
                self.strategy_age = 0
            else:
                strategy = self.last_strategy
        return out, strategy


class LLMClient:
    def __init__(self, mode: str, model: str, base_url: str, api_key: str, timeout: float = 8.0):
        self.mode = mode
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._phase = random.random() * math.tau

    # ---- 三个后端 ----
    def decide(self, state: dict, prev: dict[str, float]) -> dict:
        if self.mode == "mock":
            return self._mock(state, prev)
        prompt = self._user_prompt(state, prev)
        try:
            text = self._chat(prompt)
            return self._parse(text)
        except Exception as exc:  # 网络/解析失败一律兜底
            print(f"[warn] LLM failed: {exc}", file=sys.stderr)
            return {"weights": self._rule_based(state, prev), "strategy": "observe"}

    def _mock(self, state: dict, prev: dict[str, float]) -> dict:
        # 缓慢正弦 + 对玩家血量做一点反应，用来验证管线
        self._phase += 0.35
        hp = float(state.get("player", {}).get("hp", 1.0))
        weights = {
            "aggression": clamp(0.5 + 0.3 * math.sin(self._phase)),
            "dodge_rate": clamp(0.5 - 0.2 * math.sin(self._phase)),
            "guard_rate": clamp(0.4 + 0.2 * math.cos(self._phase)),
            "combo_rate": clamp(0.5 + 0.1 * math.cos(self._phase * 0.7)),
            "heal_priority": clamp(1.0 - hp),
            "spell_rate": clamp(0.3 + 0.2 * math.sin(self._phase * 0.5)),
            "item_rate": 0.4,
            "spacing": clamp(0.6 - 0.2 * hp),
            "target_switch": 0.5,
        }
        return {"weights": weights, "strategy": "pressure" if hp > 0.5 else "protect",
                "reason": "mock", "confidence": 0.5}

    def _rule_based(self, state: dict, prev: dict[str, float]) -> dict[str, float]:
        player = state.get("player", {})
        enemy = state.get("enemy", {})
        hp = float(player.get("hp", 1.0))
        dist = float(enemy.get("dist", 5.0))
        out = dict(prev)
        out["heal_priority"] = clamp(0.9 - hp)
        out["guard_rate"] = clamp(0.4 + (0.5 - hp))
        out["dodge_rate"] = clamp(0.4 + (0.3 if dist < 3 else 0.0))
        out["aggression"] = clamp(0.4 + (0.3 if hp > 0.6 else -0.1))
        out["spacing"] = clamp(0.5 + (0.2 if hp < 0.4 else 0.0))
        return out

    # ---- OpenAI 兼容 HTTP ----
    def _chat(self, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "temperature": 0.3,
            "max_tokens": 220,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
        url = self.base_url + "/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    @staticmethod
    def _user_prompt(state: dict, prev: dict[str, float]) -> str:
        payload = {
            "state": state,
            "last_weights": {k: round(v, 3) for k, v in prev.items()},
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _parse(text: str) -> dict:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("no json object in response")
        obj = json.loads(text[start:end + 1])
        if not isinstance(obj, dict):
            raise ValueError("response is not an object")
        return obj


class Director:
    def __init__(self, args):
        self.args = args
        self.llm = LLMClient(args.llm, args.model, args.base_url, args.api_key)
        self.guard = Guard(args.max_delta, args.hysteresis, args.strategy_cooldown)
        self.prev = default_weights()
        self.last_decision = 0.0
        self.sock = None
        self.reader: LineReader | None = None

    # ---- 连接（可重试） ----
    def ensure_connected(self) -> bool:
        if self.sock is not None:
            return True
        try:
            self.sock, self.reader = listen(self.args.host, self.args.port, self.args.token, timeout=5.0)
            print(f"[ok] game DLL connected on {self.args.host}:{self.args.port}")
            return True
        except Exception as exc:
            print(f"[warn] waiting for game DLL: {exc}", file=sys.stderr)
            return False

    def run(self) -> None:
        print("[i] director started; waiting for game…")
        while True:
            if not self.ensure_connected():
                time.sleep(2.0)
                continue
            try:
                self.loop()
            except Exception as exc:
                print(f"[warn] loop error: {exc}", file=sys.stderr)
                self.close()
                time.sleep(1.0)

    def close(self) -> None:
        try:
            if self.sock:
                self.sock.close()
        finally:
            self.sock = None
            self.reader = None

    # ---- 主循环 ----
    def loop(self) -> None:
        assert self.reader is not None
        while True:
            try:
                msg = recv_json(self.reader, timeout=0.5)
            except TimeoutError:
                continue
            mtype = msg.get("type")
            if mtype == "state":
                self.on_state(msg)
            elif mtype == "ack":
                print(f"[ack] {msg.get('cmd')}: ok={msg.get('ok')}")
            elif mtype == "ping":
                self.send({"type": "pong"})

    def on_state(self, msg: dict) -> None:
        now = time.monotonic()
        urgent = any(
            e in msg.get("events", [])
            for e in ("player_low_hp", "player_dead", "enemy_dead", "revive", "enemy_engaged")
        )
        if not urgent and now - self.last_decision < self.args.interval:
            return
        self.last_decision = now

        raw = self.llm.decide(msg, self.prev)
        weights, strategy = self.guard.apply(raw, self.prev)
        self.prev = weights

        out = {
            "type": "weights",
            "seq": msg.get("seq", 0),
            "weights": weights,
            "strategy": strategy,
        }
        if isinstance(raw.get("say"), str):
            out["say"] = raw["say"][:40]
        self.send(out)
        print(f"[weights] {strategy:10s} " + " ".join(f"{k}={v:.2f}" for k, v in weights.items()))

        self.apply_tools(raw)

    def apply_tools(self, raw: dict) -> None:
        """工具调用（白名单）。默认关闭，`--allow-tools` 打开。

        DLL 侧还有一层护栏：槽位白名单、参数存在性、±20% clamp、回滚点。
        这里只负责收拾 LLM 的字段形状。
        """
        if not self.args.allow_tools:
            return

        if raw.get("rollback") is True:
            self.send({"type": "command", "cmd": "rollback_equipment", "args": {}})
            print("[tool] rollback_equipment")

        loadout = raw.get("loadout")
        if isinstance(loadout, dict) and loadout:
            clean = {}
            for key, value in loadout.items():
                if isinstance(value, bool):
                    continue
                try:
                    clean[str(key)] = int(value)
                except (TypeError, ValueError):
                    continue
            if clean:
                args = {"who": "all", "loadout": clean}
                upgrade = raw.get("upgrade")
                if isinstance(upgrade, int) and not isinstance(upgrade, bool) and upgrade:
                    args["upgrade"] = upgrade
                self.send({"type": "command", "cmd": "set_equipment", "args": args})
                print(f"[tool] set_equipment {clean} upgrade={args.get('upgrade', 0)}")

        stats = raw.get("stats")
        level = raw.get("level")
        if isinstance(stats, dict) or isinstance(level, int):
            args = {"who": "all"}
            if isinstance(stats, dict):
                for key, value in stats.items():
                    try:
                        args[key] = int(value)
                    except (TypeError, ValueError):
                        continue
            if isinstance(level, int) and not isinstance(level, bool):
                args["level"] = level
            if len(args) > 1:
                self.send({"type": "command", "cmd": "set_stats", "args": args})
                print(f"[tool] set_stats {args}")

    def send(self, msg: dict) -> None:
        if not self.sock:
            return
        msg["token"] = self.args.token
        self.sock.sendall(dumps(msg))


def simulate(args) -> None:
    """不连游戏，喂假状态，验证 LLM→护栏→输出 这条链路（不连游戏也就不发工具调用）。"""
    llm = LLMClient(args.llm, args.model, args.base_url, args.api_key)
    guard = Guard(args.max_delta, args.hysteresis, args.strategy_cooldown)
    prev = default_weights()
    for i in range(30):
        hp = max(0.05, 1.0 - i * 0.03)
        # 形状与 DLL 的 report_state 一致，避免「仿真通过、实机字段对不上」
        state = {
            "v": 1, "type": "state", "seq": i, "frame": i * 60,
            "player": {"hp": round(hp, 3), "fp": 0.6, "stam": 0.4, "level": 6, "runes": 0},
            "clones": [
                {"npc": 100000010, "name": "May", "level": 6, "hp": 0.9, "dist": round(3 + i * 0.1, 1)},
            ],
            "enemy": {"npc": 4090000, "team": 1, "dist": round(2 + i * 0.2, 1)},
            "events": ["player_low_hp"] if i == 20 else [],
        }
        raw = llm.decide(state, prev)
        weights, strategy = guard.apply(raw, prev)
        prev = weights
        print(f"[sim {i:02d}] hp={hp:.2f} {strategy:10s} " +
              " ".join(f"{k}={v:.2f}" for k, v in weights.items()))
        time.sleep(0.05 if args.llm != "mock" else 0.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", action="store_true", help="不连游戏，跑假状态")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7811)
    ap.add_argument("--token", default="change-me")
    ap.add_argument("--llm", choices=["mock", "openai", "ollama"], default="mock")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--base-url", default="https://api.openai.com/v1")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--allow-tools", action="store_true",
                    help="允许 LLM 触发换装/加点（DLL 侧仍会做白名单+存在性+±20%% clamp）")
    ap.add_argument("--max-delta", type=float, default=0.15)
    ap.add_argument("--hysteresis", type=float, default=0.03)
    ap.add_argument("--strategy-cooldown", type=int, default=3)
    args = ap.parse_args()

    if args.llm == "ollama":
        args.base_url = args.base_url if args.base_url != "https://api.openai.com/v1" else "http://127.0.0.1:11434/v1"
        args.api_key = args.api_key or "ollama"

    if args.llm == "openai" and not args.api_key:
        print("error: --api-key required for openai", file=sys.stderr)
        raise SystemExit(2)

    if args.simulate:
        simulate(args)
        return

    Director(args).run()


if __name__ == "__main__":
    main()
