# PLAN-3a.md

## Background

### TASK-3a:
- 文件審閱時發現：本分支曾直接編輯上游檔案 `mycat/speech_bubble.py`（TASK-1b `ce975b6` 注入、TASK-1d `5207e47` 擴充），違反「上游檔案唯讀」的所有權紀律。
- 該檔案是主線 reminder/announcer 功能的活躍開發檔案，上游近期仍在演進（bubble padding、成長氣泡錨定貓身）。
- 我方在該檔案的改動含大量**誤刪上游註解/docstring**（−43 行幾乎全為註解），零功能收益卻最大化未來 rebase 衝突面。
- 上游正在做的「成長氣泡錨定」與我方加入的 `bubble_size()` 屬趨同演化，下次同步必撞。

---

# AI Agent 分析與實作計畫 (by AI Agent on 2026-08-21)

## 現狀摘要

### 全分支損害審計結果（origin/main...HEAD）

| 檔案 | 狀態 | 說明 |
|------|------|------|
| `mycat/speech_bubble.py` | ❌ **唯一受損** | +159/−43：注入 SpeechBubble 類別(~140行) + 誤刪上游註解 |
| `announcer.py` (+7) / `reminder.py` (+9) / `main.py` (+178) | ✅ 純新增 | 零刪除、零註解損害，符合 plugin 掛鉤慣例 |
| `voice_bridge.py` / `bubble_popup.py` / `wayland_drag.py` 等 | ✅ 自有檔案 | 本分支新建，無所有權問題 |

### speech_bubble.py 依賴地圖

| 消費端 | 引用符號 | 所有權 | 還原後影響 |
|--------|----------|--------|-----------|
| `announcer.py` | `BubbleWindow` | 上游 | 無（還原即回復原狀） |
| `reminder.py` | `speech_bubble` module | 上游 | 無 |
| `settings_ui.py` | `speech_bubble` module | 上游 | 無 |
| `tests/test_speech_bubble.py` | `speech_bubble` module（僅測 BubbleWindow/plane） | 上游 | 無（我方未加測試） |
| `voice_bridge.py` (L60, L240) | `SpeechBubble` | **本分支** | **僅此 2 處需改 import** |

---

## [TASK-3a] speech_bubble.py 所有權還原與 SpeechBubble 搬遷

**目標**：`git diff origin/main...HEAD -- mycat/speech_bubble.py` 歸零；語音氣泡功能不變；建立並固化上游檔案所有權規則。

### 問題分析

#### 入侵內容解剖

1. **功能性注入**：整個 `SpeechBubble` 類別（語音專用 QPainter overlay，約 140 行）被塞進上游檔案，並改寫模組 docstring 描述我方雙實作架構。
2. **破壞性清理**：`BubbleWindow` 內上游的錨定策略說明、成長方向圖解、X11 black-box workaround 註解被 AI Agent 編輯時「順手剷平」。零功能收益，卻把衝突面精確對齊上游的下刀處。

#### 為什麼是「搬移」而非「subclass」

- `SpeechBubble` 是 100% 本分支自創的獨立類別（不繼承任何上游類別），搬移 = 零行為變更。
- Subclass 適用於需要上游邏輯的場景（如繼承 `BubbleWindow`）；此處不需要。
- 純搬移後，`speech_bubble.py` 可完整 `git restore` 至 origin/main 版本，衝突面歸零。

### 所有權規則（本次任務同時固化進 AGENTS.md §2）

> **上游檔案唯讀。** 分支功能一律在自己的命名空間組合或繼承；需要上游沒有的能力，就 subclass 或 vendor 一份改名，嚴禁直接編輯上游檔案。編輯上游檔案時嚴禁順手清理註解/docstring。

判定基準：`git ls-tree origin/main` 查得到的檔案即上游檔案。

### 分類摘要

| 檔案 | 改動類型 | 說明 |
|------|----------|------|
| `mycat/voice_bubble.py` | 新建 | `SpeechBubble` 類別原封搬入（含 docstring），模組說明標註來源與所有權 |
| `mycat/speech_bubble.py` | 還原 | `git restore --source=origin/main`，回到上游原版（含被刪註解） |
| `mycat/voice_bridge.py` | 改 import | 2 處 `from mycat.speech_bubble import SpeechBubble` → `from mycat.voice_bubble import SpeechBubble` |
| `AGENTS.md` | +規則 | §2 新增上游檔案所有權守則 |
| `MEMOIR.md` | +記錄 | TASK-3a 執行紀錄與教訓 |
| `CHANGELOG.md` | +條目 | refactor 條目，驅動 `project_version` PATCH+1 |

### 風險評估

| 風險 | 影響 | 緩解 |
|------|------|------|
| 搬移時手誤造成行為差異 | 語音氣泡顯示異常 | 搬移前先存原始類別全文；搬移後 diff 比對僅允許 import 區差異 |
| 還原誤傷（上游版本非預期） | 主線公告氣泡壞 | 還原後立即跑 `tests/test_speech_bubble.py` 驗證 BubbleWindow 行為 |
| 隱藏引用未發現 | ImportError | 執行全域 grep `SpeechBubble` 確認僅 voice_bridge 2 處 + 新檔本身 |

### 建議執行順序

1. 建立 `mycat/voice_bubble.py`：自目前 `speech_bubble.py` 原封取出 `SpeechBubble` 類別
2. `voice_bridge.py` 2 處 import 改指向 `mycat.voice_bubble`
3. `speech_bubble.py` 還原 origin/main 原版
4. 全域 grep 驗證無殘留引用
5. `py_compile` 全部相關檔案 + 跑 `tests/test_speech_bubble.py`
6. 啟動冒煙測試（語音氣泡 + 公告氣泡）
7. `AGENTS.md` 固化所有權規則、`MEMOIR.md`/`CHANGELOG.md` 更新、版號遞增
