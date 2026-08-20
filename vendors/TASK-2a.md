# TASK-2a.md

## 總體目標
修復 Reminder 公告氣泡在 Wayland（GNOME / Sway / Hyprland / KDE）上的定位問題，統一 Wayland 判斷策略，不影響 X11 現有行為。

---

## [TASK-2a] Wayland 公告氣泡相容性修復

### 實作項目

#### Phase 1: voice_bridge.py 重命名 + 判斷修正
- [x] `_is_gnome_bubble` 全域重命名為 `_is_wayland_bubble`（5 處引用）
- [x] `_gnome_extra_h` 全域重命名為 `_wayland_extra_h`（4 處引用）
- [x] `_gnome_restore_size` 全域重命名為 `_wayland_restore_size`（3 處引用）
- [x] `_gnome_bubble_show()` 重命名為 `_wayland_bubble_show()`
- [x] `_gnome_restore_window()` 重命名為 `_wayland_restore_window()`
- [x] `_init_bubble()` 判斷修正：`compositor["_is_gnome"] and compositor["_is_wayland"]` → `compositor["_is_wayland"]`
- [x] 更新所有相關註解（`GNOME Wayland` → `Wayland`）

#### Phase 2: voice_bridge.py 新增公告氣泡方法
- [x] 新增 `show_announcement_bubble(text, duration, on_gone)` 方法
  - 複用 `_wayland_bubble_show` 邏輯（resize window + SpeechBubble.show）
  - 回傳 `AnnouncementBubbleHandle` 供 Announcer 追蹤生命週期
- [x] 新增 `AnnouncementBubbleHandle` 類別（QObject，destroyed signal + QTimer 過期偵測）

#### Phase 3: announcer.py + reminder.py Factory Pattern
- [x] `announcer.py` `__init__()` 新增 `self._bubble_factory = None` 屬性
- [x] `announcer.py` `launch_bubble()` 方法頂部新增 factory 檢查（5 行）
- [x] `reminder.py` `ReminderController.__init__()` 新增 `self._bubble_factory = None` 屬性
- [x] `reminder.py` `show_flyby()` 新增 factory 檢查（6 行）
- [x] 確認不動其他方法（`launch_flyby`, `pump`, `flyby_gone` 等）

#### Phase 4: main.py 注入 factory
- [x] 在 voice_bridge 初始化之後，偵測 Wayland 並注入 factory 到 `announcer._bubble_factory`
- [x] 偵測 Wayland 並注入 factory 到 `reminder_controller._bubble_factory`
- [x] factory lambda 呼叫 `voice_bridge.show_announcement_bubble()`

#### Phase 5: 驗證
- [x] `python3 -m py_compile mycat/voice_bridge.py`
- [x] `python3 -m py_compile mycat/announcer.py`
- [x] `python3 -m py_compile mycat/reminder.py`
- [x] `python3 -m py_compile mycat/main.py`
- [x] 啟動測試（GNOME Wayland）：Reminder 氣泡正確顯示在貓頭上 ✅
- [ ] 啟動測試（Sway Wayland）：Reminder 氣泡正確顯示在貓頭上
- [ ] 啟動測試（X11）：Reminder 氣泡行為不變
- [ ] 語音氣泡不受影響（Wayland + X11）
- [x] `MEMOIR.md` 更新

---

## 驗收標準
- [x] Reminder 氣泡在 GNOME Wayland 下正確顯示在貓頭上（非螢幕中央）
- [ ] Reminder 氣泡在 Sway Wayland 下正確顯示在貓頭上
- [ ] X11 環境 Reminder 氣泡行為完全不變
- [ ] 語音氣泡在所有環境下行為不變
- [ ] Announcer 排隊機制正常（一次一個，間隔 4 秒）
- [x] 啟動後無 hang 或 crash
- [x] `announcer.py` 改動量 ≤ 7 行（+1 屬性 +6 factory 檢查）

---

## 實際改動量

| 檔案 | 新增 | 刪改 | 說明 |
|------|------|------|------|
| `voice_bridge.py` | +92 | -25 | 重命名 + 新增方法 + AnnouncementBubbleHandle |
| `announcer.py` | +7 | 0 | factory 屬性 + 檢查 |
| `reminder.py` | +8 | 0 | factory 屬性 + 檢查 |
| `main.py` | +19 | 0 | 注入 factory（announcer + reminder_controller） |
| `MEMOIR.md` | +24 | -1 | 新記錄 + 日期更新 |
| **總計** | **+150** | **-26** | 淨增 ~124 行 |

---

## 踩坑紀錄
- **初始方案僅覆蓋 Announcer 路徑**：`ReminderController.show_flyby()` 直接建立 `BubbleWindow`，不經過 Announcer。需在 `reminder.py` 也加入 factory 機制。
