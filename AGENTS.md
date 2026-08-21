# AI Agent 協作指南 (AGENTS.md)

本文件定義了參與 `myCat` 語音助理增強專案的 AI Agents 協作規範與任務守則。

## 1. 專案文件組
* README.md: 專案說明文件, 為了減少合併衝突, **frontmatter 必須位於檔案中段, 嚴禁移至檔案開頭**; 保持 frontmatter以上為原作者分支的增量更新內容, frontmatter以下為本分支增量更新內容. 豁免 version-sync-check腳本檢查, 需由 AI Agent檢查 frontmatter對齊版本號.

* CHANGELOG.md: 變更說明文件, 為了減少合併衝突, **frontmatter 必須位於檔案中段, 嚴禁移至檔案開頭**; 保持 frontmatter以上為原作者分支的增量更新內容, frontmatter以下為本分支增量更新內容. 豁免 version-sync-check腳本檢查, 需由 AI Agent檢查 frontmatter對齊版本號.

* SPEC.md: 專案規格文件, 保持原規則, 受 version-sync-check腳本檢查.

* MEMOIR.md: 專案記憶點紀錄文件, 保持原規則, 受 version-sync-check腳本檢查.

### 1.1 文件版號遞增規則 (document_version)

`version-sync-check` skill 與 `project_version` 專門對付硬性的專案程式版本; 文件本身 (`document_version`) 採軟性規範, 但 ISO 精神: **文件內容一有改動, 無論專案程式碼與 `project_version` 是否異動, 都必須更新該文件 frontmatter 的 `modified_date`, 並依下列規則遞增 `document_version`**:

**PATCH +1** (計數範圍: 自上次 `document_version` 異動後的累積 diff):
- 新增圖片/多媒體/附錄連結 — 累計 <10
- 修改 `####` 層級章節 — 累計 <3
- 修改清單項目 (`*`|`-`) — 累計 <5
- 錯字修正 — 累計 <10
- 觸發的類別數合計 <4
- frontmatter 自身異動 (`modified_date`/`document_version`) 不計入

**MINOR +1**: 任一 PATCH 門檻到達, 或出現未列出的變更類型 (新增/改寫/刪除段落、`##`/`###` 標題、表格、程式碼區塊).

**MAJOR +1**: 整份重構或語意不相容調整.

純文件變更不需要在 `CHANGELOG.md` 建立新條目; `project_version` 僅由程式碼/功能變更驅動 (以 `CHANGELOG.md` 為單一事實來源).

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
