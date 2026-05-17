# Mahjong Review Helper

日本麻將 (Riichi) 復盤系統，靈感來自 chess.com 的對局回顧 — 不只給你一個 AI 分數，
而是針對每個關鍵決策告訴你：

- 你的選擇有什麼問題
- 更好的選擇是什麼
- 為什麼那樣更好

## MVP 範圍

第一版聚焦在**防守判斷**：當有對手立直 (或聽牌威脅) 時，分析該押牌還是 betaori。

每個防守決策回合會輸出：

- **你的選擇** — 你打了什麼、那張牌的危險度、押牌期望值
- **建議** — 推薦動作 (push / fold / 換張安全牌切出)，附帶理由
- **替代方案** — 列出手牌中每張牌的危險度與保留價值
- **理由說明** — 引用 suji / kabe / 振聽 / 河情勢 / 自手向聽 / 打點 等具體因素

未來會擴充到切牌效率、鳴牌、立直判斷。

## 架構

```
backend/        Python (FastAPI) — 牌譜解析 + 啟發式分析引擎
frontend/       Next.js (React + TypeScript) — 互動式復盤 UI
sample_logs/    範例牌譜 (Tenhou JSON)
```

## 啟動

### Backend

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn mahjong_review.api.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

前端會在 http://localhost:3000，預設打到後端 http://localhost:8000。
