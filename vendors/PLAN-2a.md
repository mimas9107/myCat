# PLAN-2a.md

## Background

### TASK-2a:
- Reminder 氣泡 (`BubbleWindow`) 在 Wayland（GNOME / Sway）上定位失效。
- `BubbleWindow` 使用 `mapToGlobal()` + `move()` 定位獨立 QWidget，但 Wayland 下 `mapToGlobal()` 回傳 `(0,0)`，氣泡固定出現在螢幕中央，無法追蹤貓位置。
- 語音氣泡已有解法：`SpeechBubble`（QPainter 畫在 cat paintEvent 裡）在所有 Wayland 上正常運作。
- 需要將此解法延伸至 Reminder 公告系統，且不污染 `announcer.py` 的原有架構。

---

# AI Agent 分析與實作計畫 (by AI Agent on 2026-08-20)

## 現狀摘要
- TASK-1d 已完成：語音氣泡在 GNOME Wayland 上透過 `SpeechBubble` in-window QPainter 正常運作
- TASK-1c 已完成：`BubblePopup` 在 Sway 上透過 `Qt.ToolTip` → xdg_popup 正常運作
- Reminder 氣泡 (`BubbleWindow`) 在 Wayland 上完全失效（`mapToGlobal()` 回傳 (0,0)）
- 本分支已有 `wayland_drag.py`（跨 compositor Wayland 拖曳）和 tray 跳過邏輯，Wayland 策略應統一

---

## [TASK-2a] Wayland 公告氣泡相容性修復

**目標**：讓 Reminder 公告氣泡在所有 Wayland compositor（GNOME / Sway / Hyprland / KDE）上正確顯示，不影響 X11 現有行為。

### 問題分析

#### 三套氣泡系統現狀

| 類別 | 檔案 | 用途 | 窗口類型 | Wayland 狀態 |
|------|------|------|----------|-------------|
| `BubbleWindow` | `speech_bubble.py` | 公告（Reminder/GitHub/行事曆） | 獨立 QWidget | ❌ 壞（mapToGlobal 失效） |
| `SpeechBubble` | `speech_bubble.py` | 語音（Ollama 回覆） | 無窗口 QPainter | ✅ 正常 |
| `BubblePopup` | `bubble_popup.py` | 語音（非 GNOME） | 獨立 QWidget | ⚠️ Sway 可用 / GNOME cursor 定位 |

#### 資料流比較

**Reminder 路徑**（目前壞的）：
```
ReminderController.tick() (1s)
  → fire() → show_flyby()
    → [bubble_mode_enabled] → BubbleWindow(cat_window, text)
      → mapToGlobal() → (0,0) → 氣泡在螢幕中央
```

**語音路徑**（已修正）：
```
VoiceWorker → intent_detected_signal → VoiceBridge._on_intent()
  → _voice_chat() → Ollama QThread → _on_chat_done()
    → [Wayland] → _gnome_bubble_show()
      → resize window + SpeechBubble.show()
        → paintEvent → QPainter 畫在 cat 裡
```

**Announcer 路徑**（也壞）：
```
announcer.announce("text")
  → pump() → launch_flyby()
    → [bubble_mode_enabled] → launch_bubble()
      → BubbleWindow(...) → 同樣 mapToGlobal 失效
```

### Wayland 策略一致性

本分支已有的 Wayland 處理策略：

| 模組 | 策略 | 判斷條件 |
|------|------|----------|
| `wayland_drag.py` | `QWindow.startSystemMove()` | 所有 Wayland |
| `main.py` tray | 跳過 system tray | `WAYLAND_DISPLAY` 存在 |
| `voice_bridge.py` | SpeechBubble in-window | 僅 GNOME（需修正） |

**結論**：應統一為 `_is_wayland`（與 `wayland_drag.py` 一致），不只限 GNOME。

### 解法：Factory Pattern + Wayland 統一判斷

#### 核心設計

1. **`announcer.py`**：新增 `_bubble_factory` 屬性，預設 `None`（走原 `BubbleWindow` 路徑）。由外部注入替代實作。
2. **`voice_bridge.py`**：`_is_gnome_bubble` 重命名為 `_is_wayland_bubble`，判斷改為 `_is_wayland`。新增 `show_announcement_bubble()` 方法供 announcer 使用。
3. **`main.py`**：初始化時偵測 Wayland，注入 factory 到 `announcer._bubble_factory`。

#### 為什麼不直接改 `announcer.py` 的邏輯 **!important**

- `announcer.py` 是主線作者的模組，本分支尚未涉足
- Factory pattern 讓 `announcer.py` 完全不知道 Wayland/GNOME 的存在
- 向下相容：`_bubble_factory = None` 時走原路徑，X11 不受影響
- 未來主線更新 `announcer.py` 時合併衝突最小化

#### 為什麼判斷 `_is_wayland` 而非 `_is_gnome and _is_wayland`

- Sway 上 `mapToGlobal()` 同樣回傳 (0,0)，`BubbleWindow` 同樣會壞
- `BubblePopup` 在 Sway 上能用是因為走了 `Qt.ToolTip` → `xdg_popup`（parent-relative），但 `BubbleWindow` 沒有這條路
- 統一走 in-window `SpeechBubble` 最可靠，不依賴各 compositor 對 xdg_popup 的實作差異

### 分類摘要

| 檔案 | 改動類型 | 說明 |
|------|----------|------|
| `announcer.py` | +factory 屬性 +factory 檢查 | 7 行新增，0 刪改 |
| `reminder.py` | +factory 屬性 +factory 檢查 | 8 行新增，0 刪改 |
| `voice_bridge.py` | 重命名 + 判斷修正 + 新增方法 | ~92 行新增，~25 行重命名 |
| `main.py` | 注入 factory（announcer + reminder_controller） | 19 行新增 |
| `speech_bubble.py` | 不動 | — |
| `bubble_popup.py` | 不動 | — |
| `wayland_drag.py` | 不動 | — |

### 風險評估

| 風險 | 影響 | 緩解 |
|------|------|------|
| Announcer 和語音氣泡同時觸發 | 兩者都 resize window，可能衝突 | `show_announcement_bubble()` 檢查 `_wayland_extra_h > 0` 先還原 |
| `_bubble_factory` 未注入（voice_bridge 未初始化） | 公告走原 BubbleWindow，在 Wayland 上壞 | 不影響 X11；Wayland 下 voice_bridge 必定初始化（`__init__` 中建立） |
| 重命名 `_is_gnome_bubble` 影響範圍 | 全域搜尋確認 5 處引用 | 純機械式替換，邏輯不變 |

### 建議執行順序

1. `voice_bridge.py` 重命名：`_is_gnome_bubble` → `_is_wayland_bubble`，`_gnome_*` → `_wayland_*`
2. `voice_bridge.py` 判斷修正：`_is_gnome and _is_wayland` → `_is_wayland`
3. `voice_bridge.py` 新增 `show_announcement_bubble()` + `AnnouncementBubbleHandle`
4. `announcer.py` 新增 `_bubble_factory` + `launch_bubble()` factory 檢查
5. `reminder.py` 新增 `_bubble_factory` + `show_flyby()` factory 檢查
6. `main.py` 注入 factory（announcer + reminder_controller）
7. 語法檢查 (`py_compile`)
8. 啟動測試（Wayland + X11）
9. `MEMOIR.md` 更新

### 踩坑紀錄
- **Reminder 路徑不經過 Announcer**：`ReminderController.show_flyby()` 直接建立 `BubbleWindow`，Announcer factory 僅覆蓋 GitHub/行事曆/摘要路徑。需在 `reminder.py` 也加入 factory 機制。
