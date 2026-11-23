# 署名、许可与 AI 披露（发布用素材）

## 1. 页面 Credits 区（直接贴）

```
fromsoftware-rs (Vincent Swarte / vswarte) - Rust bindings for FromSoftware games, including the
offset tables and structures this mod is built on. Licensed MIT-NON-AI / Apache-2.0-NON-AI;
full text is included in THIRD-PARTY-LICENSES.txt and the LICENSES folder.

Paramdex and the wider Elden Ring modding community - parameter names and structure documentation.

ESDLang (thefifthmatt) - esdtool, used to build the optional root-menu ESD fallback.

Mod Engine 2 (Soulsmods) - the loader this mod is developed and tested against.

me3 (garyttierney) - the alternative loader supported by the installer for vanilla + me3 and for
The Convergence 3.x.
```

## 2. 代码许可

本项目代码：**MIT OR Apache-2.0**。

注意：发布的是**二进制**，链接了 `fromsoftware-rs`，所以压缩包里必须带它的许可全文
（MIT-NON-AI / Apache-2.0-NON-AI）。这两份不是普通 MIT/Apache：多了一条
「不得用于训练机器学习模型」的限制。打包脚本会把它们放进 `LICENSES\`。

## 3. AI 披露（必填）

Nexus 自 2026-11-03 起强制披露生成式 AI 的使用（缓冲期到 2027-01-02）。三档：

| 档位 | 什么时候用 |
|---|---|
| **AI-Generated Content** | 代码/UI/语音/文本的**大部分**由 AI 生成 |
| **AI Media** | 页面用的图/视频/描述是 AI 生成的（不是游戏内截图） |
| **AI Assisted** | 人工主导，AI 只做辅助；**必须**在页面给出开发历史/代码理解证据 |

本项目的情况：代码大量由 AI 编程助手在人工设计、实测、调试下完成 → 诚实做法是
**AI-Generated Content**；如果走 **AI Assisted**，页面必须能拿出开发历史证据
（`docs/implementation-log.md` 那种逐日记录、以及作者能解释代码），否则会被审核改档。

**页面描述如果是 AI 代写的**，严格说属于 `AI Media`。建议：自己改写一遍，或如实勾选。

不要为了「看起来更手作」而漏报——被举报是 Trust & Safety 处理，不是社区自治。

## 4. 权限建议

- 代码 MIT/Apache：允许他人复用/修改（页面写「with credit」，并给出 GitHub 源码地址）。
- 发布物（本压缩包）：不允许转到其他站点，链接回本页。
- 资产：本 mod 不含原创美术资产。**主包和安装器 payload 里都有** talk ESD（赐福菜单挂载点，
  改过的游戏数据），fallback 包是同一文件的根菜单变体；两者都只随本 mod 分发，不单独授权再分发。
- 参数表：`tables\convergence\*.json` 是我们自己的 DLL 从运行中的 regulation dump 出来的**纯数值 ID 表**，
  不含 The Convergence 的文件/代码/美术；页面写明来源即可。
- Nexus 表单里对应选：
  - Upload: **not allowed to upload to other sites**
  - Modification: **must get permission**
  - Conversion: **not allowed**
  - Asset use: **must get permission**
  - AI training / fork：默认 `Ask me`

> Nexus 的权限字段约束的是**本页发布物（压缩包）**，不是代码许可。代码是 MIT/Apache（可复用、
> 可改，署名即可），压缩包不经允许不转传——两句话同时成立，页面里已经分开写。
> 如果审核或用户问起，就按这个口径回答，不用改许可。

## 5. 需要向第三方「申请」吗（结论表）

| 对象 | 要申请吗 | 依据 / 动作 |
|---|---|---|
| `fromsoftware-rs`（MIT-NON-AI / Apache-NON-AI） | **不用** | 许可允许分发二进制，只要随包附全文（`THIRD-PARTY-LICENSES.txt` + `LICENSES\`）；额外限制只是「不得用于训练 ML 模型」，我们没有 |
| ESDLang / esdtool | **不用** | 只在本机用来生成 ESD，工具本身不随包分发；页面署名即可 |
| Mod Engine 2 / me3 | **不用** | 安装器只写配置引用，不分发它们的文件；页面署名 + 官方链接 |
| Paramdex | **不用** | 参数名/结构文档，社区公开；署名 |
| The Convergence 3.x | **不用（可选知会）** | 没有使用它的文件/代码/美术；`tables\convergence\*.json` 是运行时 dump 的数值 ID 表。想更稳妥可以给作者发个 PM 说一声，但不是必须 |
| FromSoftware / Bandai Namco（改版 talk ESD） | **无法申请** | 没有任何授权渠道。按 Nexus 规则处理：页面写明「主包含一份改过的 vanilla ESD，仅为赐福菜单挂载」，不单独提供该文件；这属于披露义务，不是申请流程 |
| 你的内置角色 Sanvenir | **不用** | 从你自己的存档离线导出、已脱敏（`steam_id` 为空） |

## 6. 需要写进页面的「联网行为」说明（Nexus 规则要求）

```
The DLL opens a local-only TCP listener on 127.0.0.1:7811 for the bundled tools. It makes no
outbound connections. The optional Python "battle director" only talks to an endpoint you
configure yourself (OpenAI / Ollama / or the offline mock); nothing is sent anywhere unless you
run it. The mod works fully offline without it.
```

## 7. 需要写进页面的「多人环境」说明

```
Offline only. Launch through a mod loader (Mod Engine 2 or me3) with EAC disabled. Never use a
modded save online - that is a soft-ban. This mod modifies runtime memory only; it does not write
to your .sl2.
```
