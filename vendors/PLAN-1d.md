# PLAN-1d.md

## Background

### TASK-1d:
- BubblePopup (Qt.ToolTip → xdg_popup) 在 Sway Wayland 上正常運作，但在 **GNOME Wayland** 下無氣泡顯示。
- 先前在 `bubble_popup.py` 加入 compositor 偵測與 `Qt.Window` fallback，經實測：
  1. `mapToGlobal()` 在 GNOME Wayland 回傳 `(0,0)` → 座標定位機制需針對 Wayland 修正
  2. `Qt.Window | FramelessWindowHint | WA_TranslucentBackground` 導致 `show()` 阻塞 ≥73秒 → fallback 策略錯誤
- 需要修正 BubblePopup 使其在 Sway 與 GNOME 下均可正確顯示。

---

# AI Agent 分析與實作計畫 (by AI Agent on 2026-07-27)

## 現狀摘要
- TASK-1c 已完成
- `BubblePopup` 使用 `Qt.ToolTip`，在 Sway (xdg_popup) 正常，GNOME (mutter) 無顯示
- 診斷 log 確立兩大根因：
  - **mapToGlobal 失效**：`self.parent().mapToGlobal(QPoint(0,0))` 在 GNOME Wayland 回傳 (0,0)，導致定位錯誤
  - **Qt.Window fallback 阻塞**：GNOME 不接受 `Qt.Window | FramelessWindowHint | WA_TranslucentBackground`，`show()` 永不返回

---

## [TASK-1d] GNOME Wayland BubblePopup 相容性修復

**目標**：讓 BubblePopup 在 GNOME Wayland 下正常顯示浮動氣泡，不影響 Sway 現有行為。

### 分析摘要

| 項目 | Sway (已知正常) | GNOME (需修正) |
|------|----------------|----------------|
| `mapToGlobal()` | 回近似值 (可運作) | 回傳 `(0,0)` |
| `Qt.ToolTip` → xdg_popup | 正常浮動 + 透明背景 | 需驗證透明背景支援度 |
| `move()` 座標系統 | 能接受 screen coords | 須為 parent-relative coords |

### 解法

1. **移除 `Qt.Window` fallback**：統一使用 `Qt.ToolTip | Qt.FramelessWindowHint`
2. **座標定位分流**：
   - Wayland：xdg_popup 座標為 parent-relative，直接 `move(bx, by)`
   - X11：需要絕對螢幕座標，保留 `mapToGlobal()` + offset
3. **保留 compositor 偵測**：供 `_position_near_cat` 分流判斷用，並於 `__init__` 印一行 info
4. **清理診斷 log**：移除 `showEvent`、`paintEvent`、pre/post-show 等 verbose log，僅保留 `_position_near_cat` 的 `VOICE_BRIDGE_DEBUG=1` 層級

### 分類摘要

| 檔案 | 改動 |
|------|------|
| `mycat/bubble_popup.py` | 移除 Qt.Window 分支、新增定位分流、清理診斷 log、保留 compositor 偵測 |
| `vendors/PLAN-1d.md` | 本計畫文件 |
| `vendors/TASK-1d.md` | 實作任務追蹤 |

### 建議執行順序

1. `bubble_popup.py` 修正：flags 統一、定位分流、log 清理
2. `bubble_popup.py` 重構確認：確認無 dead code
3. 語法檢查 (`ruff`)
4. 啟動測試（GNOME Wayland）：確認 bubble 正常繪出、無 hang
5. `MEMOIR.md` 更新踩坑紀錄
