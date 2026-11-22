# 从存档导出角色档案（profile.json）

目标：拿到一个槽位的 **外观（FaceData 0x12F）+ 装备 22 槽 + 属性/等级**，转成 `bridge/profile_reader.py` 能校验的 JSON。

> 前置：先备份 `%APPDATA%\EldenRing\<SteamID>\ER0000.sl2`。任何写档工具都要先备份。

---

## 方案 1（推荐）：现成工具导出，再转 JSON

1. 下载 [ER Save Manager (Soar Qin)](https://www.nexusmods.com/eldenring/mods/9571)（明确支持 1.17.1/1.17.2，slot version 261/262）。
2. 打开存档 → 选中目标槽 → 导出角色（`.erc` 或含 face 的 JSON）。
   - 同类替代：[Elden Ring Appearance Copier](https://www.nexusmods.com/eldenring/mods/11076)（只导外观 + `eldenblingsliders` JSON）。
3. 把导出的字段填进下面的模板（`face_hex` 必须是 **0x12F 字节**、以 `ffffffff46414345`（`\xff\xff\xff\xffFACE`）开头）。
4. 校验：
   ```powershell
   python bridge/profile_reader.py profiles/target.json
   ```
   看到 `face bytes : 303` 即通过。

模板见 `tools/profile.example.json`。

### 字段对照
| profile.json | 来源 |
|---|---|
| `name` | 存档 PGD+0x94（32B UTF-16LE） |
| `level` | PGD+0x60（= 8 属性之和 − 79） |
| `stats.*` | PGD+0x34..0x50（u32 ×8） |
| `equipment_param_ids[22]` | PGD+0x58 三份平行表里的 **item id** 表（顺序见 design.md §4.1） |
| `face_hex` | PGD 链尾 `face_data`，0x12F 字节原样 |
| `body_type` | PGD+0xB6 |
| `summon_spirit_level` | PGD+0xBF |
| `scadutree_blessing` | PGD+0xF4 |

---

## 方案 2：自己写最小 walker（Python）

**不要硬编码绝对偏移**：`gaitem_map`（5118/5120 条变长记录）之后所有偏移都是动态的。
最小步骤：

```python
# 1) 定位槽：0x310 + slot * 0x280010（0x10 = MD5，其后 0x280000 = 数据）
# 2) 顺序 walk：跳过 gaitem_map → 落在 player_game_data
# 3) 按固定相对链走到 face_data
#    参考实现：https://github.com/ClayAmore/ER-Save-Lib （Rust）
#              https://github.com/Hapfel1/er-save-manager （Python）
#    规格：https://elden-ring-save-manager.readthedocs.io/en/main/technical/save-file-structure/
```

要点：
- `.sl2` 在 PC 上是**明文 BND4**（只有每槽 MD5 校验），不需要 AES。
- 改完必须**重算该槽 MD5**；改脸**不**需要重算 `PlayerGameDataHash`（它只吃属性/装备/卢恩）。
- 写入用 tmp + rename，别直接覆盖原档。

---

## 方案 3（不推荐，但最快验证）：游戏内直接捏一个同外观角色

如果只是验证「AI 同伴」链路，不必先做存档解析：
1. 在游戏里用目标外观新建/读取一个角色；
2. 用 `profile_reader.py` 只填 `equipment_param_ids` 和一个占位 face（或直接跑 DLL 的 `DEBUG_APPLY`）；
3. 先验证召唤/跟随/权重，再做外观导入。

---

## 注意
- `.co2`（Seamless）与 `.sl2` 用同一套解析器，但**不要把 Seamless 专属物品写回 `.sl2`**。
- 外观数据是个人信息：分发 mod 时不要打包别人的脸。
- 写档失败可能导致「无限加载」：`hp==0 && state==13` 的 Torrent、DLC flag 是常见坑，改前备份。
