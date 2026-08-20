# TASK-1d.md

## 總體目標
修復語音氣泡在 GNOME Wayland (mutter) 下的顯示問題，同時確保 Sway/X11 不受影響。

---

## [TASK-1d] GNOME Wayland 氣泡相容性修復

### 研究歷程
1. **Qt.ToolTip (xdg_popup)** → Sway 正常，GNOME 不渲染（氣泡存在於 log 但螢幕看不到）
2. **Qt.Window + parent** → `show()` hang 死（Wayland 協定 deadlock）
3. **Qt.Window + parent=None** → 無 hang、有渲染，但 `move()` 被 GNOME mutter 忽略 → 氣泡出現在螢幕正中央
4. **最終方案：in-window QPainter** → 利用既有的 `SpeechBubble` 類別，在貓咪視窗的 `paintEvent` 中畫氣泡，完全避開視窗定位問題

### 實作項目
- [x] `speech_bubble.py`: `paint()` 新增 `pos=(bx, by)` 參數支援 GNOME 模式手動定位
- [x] `speech_bubble.py`: 新增 `bubble_size()` 方法供外部計算氣泡範圍
- [x] `voice_bridge.py`: `_init_bubble()` 新增 GNOME Wayland 偵測，使用 `SpeechBubble` 而非 `BubblePopup`
- [x] `voice_bridge.py`: `apply_paint()` GNOME 分支呼叫 `SpeechBubble.paint()` 定位在視窗右上角
- [x] `voice_bridge.py`: `_on_chat_done()` GNOME 分支使用 `_gnome_bubble_show()` 純文字展示（無 resize、無 move）
- [x] 語法檢查：`py_compile` 成功
- [x] 啟動測試：GNOME Wayland 下 bubble 正常顯示於貓旁（右上角）、無 hang、無錯誤 log
- [x] Sway 完全不受影響（`_init_bubble` 非 GNOME 分支走原有 `BubblePopup`）

---

## 驗收標準
- [x] 氣泡在 GNOME Wayland 下成功顯示（透過 in-window QPainter）
- [x] Sway Wayland 不受影響（維持既有 `BubblePopup` + `Qt.ToolTip` 行為）
- [x] 啟動後無 hang 或 crash
- [x] `MEMOIR.md` 更新完畢
