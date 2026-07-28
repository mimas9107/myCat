# AI Agent 協作指南 (AGENTS.md)

本文件定義了參與 `myCat` 語音助理增強專案的 AI Agents 協作規範與任務守則。

## 1. 專案文件組
* README.md: 專案說明文件, 為了減少合併衝突, frontmatter位於中間中段, 保持 frontmatter以上為原作者分支的增量更新內容, frontmatter以下為本分支增量更新內容. 豁免 version-sync-check腳本檢查, 需由 AI Agent檢查 frontmatter對齊版本號.

* CHANGELOG.md: 變更說明文件, 為了減少合併衝突, frontmatter位於中間中段, 保持 frontmatter以上為原作者分支的增量更新內容, frontmatter以下為本分支增量更新內容. 豁免 version-sync-check腳本檢查, 需由 AI Agent檢查 frontmatter對齊版本號.

* SPEC.md: 專案規格文件, 保持原規則, 受 version-sync-check腳本檢查.

* MEMOIR.md: 專案記憶點紀錄文件, 保持原規則, 受 version-sync-check腳本檢查.

## 2. 開發原則與守則
* **先讀文件**：每次啟動任務前，Agent 必須先閱讀 `vendors/PLAN-[1-9][a-zA-Z].md` 與 `SPEC.md`，確保架構認知同步。
* **嚴守邊界**：負責 `core/` 模組的 Agent 絕對禁止引入 `PySide6` 或任何 Qt 元件。
* **增量更新**：每次完成任務後，若有遇到技術卡點與解法，Agent 有責任更新 `MEMOIR.md`。

## 3. 任務分工藍圖
本專案的開發可分為以下幾個主要 Agent 角色 (或任務類型)：

* **Voice Core Agent (語音核心工程師)**
  * 職責：實作 Task 1 到 Task 6。
  * 專注領域：純 Python 開發，熟悉 `pyaudio`, `faster-whisper`, `numpy` 效能最佳化。
  * 守則：撰寫單元測試以驗證音訊緩衝與 VAD 是否正確運作。
  * 各 Task內部細項運作以[]未完成,[x]以完成拆分細項實作任務.

* **Qt Integration Agent (Qt 整合工程師)**
  * 職責：實作 Task 7 到 Task 8。
  * 專注領域：`PySide6`, `QThread`, `Signal/Slot` 機制。
  * 守則：確保所有的 UI 更新都只在 Main Thread 執行，嚴格防範 Thread Crash。
  * 各 Task內部細項運作以[]未完成,[x]以完成拆分細項實作任務.

## 4. 協作流程
1. 由使用者指定當前要執行的 Task (參考 `vendors/TASK-[1-9][a-zA-Z].md must according to PLAN-[1-9][a-zA-Z]`)。
2. Agent 進行程式碼撰寫與修改。
3. Agent 執行基本的語法或流程檢查。
4. Agent 執行實作任務檢查 [],[x], 需要做寫一致, 一有[]未完成代表 Task未完成不得進入下一個 Task.
5. 提示使用者進行測試與驗收。
