# TASK-3a.md

## 總體目標
還原上游檔案 `mycat/speech_bubble.py` 至 origin/main 原版，將本分支的 `SpeechBubble` 類別搬遷至自有新檔 `mycat/voice_bubble.py`，使該檔案的 rebase 衝突面歸零；並將「上游檔案唯讀」所有權規則固化進 AGENTS.md。

依據：`vendors/PLAN-3a.md`

---

## [TASK-3a] speech_bubble.py 所有權還原與 SpeechBubble 搬遷

### 實作項目

#### Phase 1: 建立 mycat/voice_bubble.py
- [x] 自 `mycat/speech_bubble.py` 原封取出 `SpeechBubble` 類別全文（含所有方法與 docstring）
- [x] 新檔模組 docstring 標註：本檔為本分支自有資產、類別來源（TASK-1b/1d）、搬遷原因（TASK-3a 所有權還原）
- [x] 搬移後與原檔 diff 比對：僅允許 import 區與模組 docstring 差異，類別本體零差異（程式化驗證 IDENTICAL）

#### Phase 2: voice_bridge.py 改指向
- [x] L60 附近：`from mycat.speech_bubble import SpeechBubble` → `from mycat.voice_bubble import SpeechBubble`
- [x] L240 附近：同上
- [x] 全域 grep `SpeechBubble` 確認無其他殘留引用（排除 voice_bubble.py 本身）

#### Phase 3: speech_bubble.py 還原
- [x] `git restore --source=origin/main -- mycat/speech_bubble.py`
- [x] 驗證 `git diff origin/main...HEAD -- mycat/speech_bubble.py` 輸出為空（commit `f2ddab5` 後驗證通過）
- [x] 確認被誤刪的上游註解/docstring 已回魂（BubbleWindow 錨定策略、成長方向圖解、X11 workaround）

#### Phase 4: 文件與版號
- [x] `AGENTS.md` §2 新增「上游檔案所有權」守則（唯讀、subclass/vendor、禁清註解、判定基準）
- [x] `MEMOIR.md` 新增 TASK-3a 記錄（含教訓：agent 編輯上游檔案時的註解清理禁令）
- [x] `CHANGELOG.md` 新增 refactor 條目
- [x] 版號遞增：`project_version` 0.2.4 → 0.2.5（PATCH，CHANGELOG 為單一事實來源）；各文件 frontmatter 對齊

#### Phase 5: 驗證
- [x] `python3 -m py_compile mycat/voice_bubble.py mycat/voice_bridge.py mycat/speech_bubble.py`
- [x] `python3 -m pytest tests/test_speech_bubble.py`（4 passed，上游 BubbleWindow 行為不變）
- [x] 啟動測試：語音氣泡正常顯示（Wayland in-window 路徑）（✅ 使用者 Sway 實測通過）
- [x] 啟動測試：公告氣泡（Reminder bubble mode）不受影響（✅ 使用者 Sway 實測通過，且語音氣泡正確接續顯示）
- [x] `MEMOIR.md` 更新執行結果

---

## 驗收標準
- [x] `git diff origin/main...HEAD -- mycat/speech_bubble.py` 為空（最高優先驗收，commit 後驗證通過）
- [x] `mycat/voice_bubble.py` 存在且 SpeechBubble 類別本體與搬移前逐字一致
- [x] `py_compile` 全數通過
- [x] `tests/test_speech_bubble.py` 全綠（4 passed）
- [x] 語音氣泡功能正常（✅ Sway 實測）
- [x] 公告氣泡功能正常（✅ Sway 實測）
- [x] AGENTS.md 所有權規則已固化
- [x] CHANGELOG/MEMOIR/版號完成更新（0.2.5）

---

## 實際改動量

| 檔案 | 新增 | 刪改 | 說明 |
|------|------|------|------|
| `mycat/voice_bubble.py` | +140 | 0 | 新檔：SpeechBubble 原封搬入（類別本體 IDENTICAL） |
| `mycat/speech_bubble.py` | 還原 | 還原 | 回到 origin/main 原版（vs 分支舊狀態 −159/+43 全數抵銷） |
| `mycat/voice_bridge.py` | 2 | 2 | 兩處 import 改指向 voice_bubble |
| `AGENTS.md` | +1 | 0 | §2 上游檔案所有權守則 |
| `MEMOIR.md` | +16 | 0 | TASK-3a 記錄 + 教訓 |
| `CHANGELOG.md` | +13 | 0 | [0.2.5] 條目 |
| `pyproject.toml` / `README.md` / `SPEC.md` | 版號 | 版號 | 0.2.4 → 0.2.5 |
| `vendors/PLAN-3a.md` / `TASK-3a.md` | 新檔 | — | 計畫與實作文件 |

---

## 踩坑紀錄
- **三點 diff 的時機陷阱**：`git restore --source=origin/main` 只改工作區，`git diff origin/main...HEAD`（比對 commit）在 commit 前仍顯示舊差異 260 行，勿誤判還原失敗；commit 後歸零。
- **無頭環境的 Qt 冒煙測試**：`SpeechBubble.__init__` 建立 QFont/QFontMetrics 需要 QGuiApplication，裸 import 會 hang/警告；須 `QT_QPA_PLATFORM=offscreen` + 先建 `QApplication`。
- **上游實際未動此檔**：merge-base 與 origin/main 的 speech_bubble.py 完全一致（先前認知的「上游活躍開發」是指分岔點之前的歷史），但所有權紀律仍須固化以防未來上游演進。
