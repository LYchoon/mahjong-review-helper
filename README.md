# Mahjong Review Helper

日本麻將 (Riichi) 復盤系統，靈感來自 chess.com 的對局回顧 — 不只給你一個 AI 分數，
而是針對每個關鍵決策告訴你：

- 你的選擇有什麼問題
- 更好的選擇是什麼
- 為什麼那樣更好

## 範圍

第一版聚焦在**防守判斷**：當對手立直 / 默聽嫌疑 / 一向聽嫌疑時，分析該押牌還是 betaori。

每個防守決策都會輸出 chess.com 風格的五級評分：

| 標籤 | 顏色 | 含意 |
| --- | --- | --- |
| best | 綠 | 期望值最高，幾乎沒有更好選擇 |
| good | 淺綠 | 微小差距，仍是合理選擇 |
| inaccuracy | 黃 | 危險度過高或期望值損失明顯 |
| mistake | 橘 | 該全防卻押了高危險牌 |
| blunder | 紅 | 嚴重失誤 — 對 EV / 危險度差距巨大 |

## 引擎特色

### 危險度評估 (danger.py)

每張牌的危險度 0-100，並列出具體因素：

- **現物 (genbutsu)** — 對手立直後切過的牌，0 危險
- **振聽前現物** — 對手立直前已切過的牌，立直者不能榮和
- **筋 (suji)** — 1-4-7 / 2-5-8 / 3-6-9 鏈，安全僅針對兩面聽
- **雙筋 / 半筋** — 中張的兩條筋是否都已切
- **壁 (kabe)** — 內側搭子牌已全見，特定兩面搭不可能
- **no-chance / one-chance** — 形成搭子的牌全見 / 只剩 1 枚
- **字牌可見數** — 3 枚見的字牌幾乎安全
- **染手嫌疑 (honitsu)** — 對手某花色幾乎不切時，該花色變熱
- **多家威脅合計** — 多家立直時，合併放銃機率: 1 − ∏(1 − pᵢ)

### 押牌可行性 (analyzer.py + ev.py)

每個切牌候選都會計算：

- **切後向聽數** + **有效進張** (考慮已見牌)
- **押牌期望值** = 和率 × 估計打點 − 放銃率 × 估計失點
- **殘餘安全牌數** — 切了之後手中還剩幾張安全牌

### 打點估算 (hand_value.py)

把確定 yaku 與機率 yaku 都納入考量：

- 立直 / 役牌三 / 斷么 / 寶牌 → 整數翻
- 自摸期望 (門前 ~25%) / 役牌候補對子 → 分數翻
- 最後向上取整給整數翻數

### 失點估算 (ev.py)

- Riichi 基準 6500、Dama 5200、Iishanten 3500
- 對手已副露三元牌 (白/發/中) → 每組 +1500
- 寶牌指示牌每多一張 → +800

### 多家威脅

多家同時威脅時，自動把每個對手的危險度合併 (獨立放銃模型)，並在 UI 上分別標出每個因素來自哪一家。

## 牌譜支援

- **天鳳 JSON (tenhou.net/6/)** — 完整支援，包含鳴牌中斷、立直、暗槓/加槓
- **雀魂牌譜** — 請用 `majsoul-paipu-tools` 等工具先轉成天鳳格式

## 使用方式

### 啟動後端

```bash
cd backend
uv sync
uv run pytest                                       # 38 tests, 全綠
uv run uvicorn mahjong_review.api.main:app --reload  # http://localhost:8000
```

### 啟動前端

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

### 兩種模式

1. **手動單局輸入** — 填入手牌、要打的牌、對手立直巡目與河，點「分析」
2. **天鳳牌譜上傳** — 貼上整局 JSON，自動跑完整局；可直接點「載入範例牌譜」試玩

天鳳牌譜分析結果頁面：

- 頂部：**整局摘要** (防守準確率%、五級標籤分佈、累積期望失分、跳到最大失誤)
- 中段：**決策導覽** (← → 鍵切換)，每個決策都附完整盤面 (4 家河 + 寶牌指示 + 立直/默聽/役牌徽章)
- 下段：**逐手點評** (你的選擇 vs 建議 + 雙條 bar 視覺化危險度與押 EV)
- 底部：**手牌安全分佈** — 手中每張牌依危險度排序，外圈顏色從綠到紅一目了然

## 架構

```
backend/
  mahjong_review/
    tiles.py         # 牌的內部表示與解析
    shanten.py       # 向聽數計算 + effective_tiles
    hand_value.py    # 役判定 + 翻數估算
    danger.py        # 危險度評分
    ev.py            # 押牌期望值 / 放銃成本
    analyzer.py      # 決策整合 + chess.com 評級
    parsers/
      tenhou.py      # 天鳳 JSON 解析 (含鳴牌處理)
      majsoul.py     # 雀魂 (stub — 需 protobuf)
    api/main.py      # FastAPI 端點

frontend/
  app/
    page.tsx                # 主頁 (手動表單 + 天鳳上傳)
    components/
      Tile.tsx              # 麻將牌 (可點擊)
      DangerBar.tsx         # 危險度 / EV 橫條
      ReviewCard.tsx        # 單一決策卡片
      ChoicePanel           # 你的選擇 vs 建議
      AlternativeRow        # 候選排行
      HandSafety.tsx        # 手牌安全分佈
      BoardState.tsx        # 4 家盤面 (含役牌徽章)
      GameSummary.tsx       # 整局統計
      DecisionNavigator.tsx # 決策步進 (← →)
      LabelBadge.tsx        # best/good/.../blunder 徽章
  lib/api.ts                # 後端介面

sample_logs/
  riichi_defense_demo.json  # 合成範例對局 (下家 T4 立直，hero 連續押 5 張)
```

## API 端點

- `POST /review/manual` — 單一決策分析 (手動輸入)
- `POST /review/tenhou` — 整局牌譜分析 (回傳 summary + decisions[])
- `GET  /health` — 健康檢查

## 未來方向

- 整合 Mortal 等真正麻將 AI 做交叉驗證
- 切牌效率分析 (非防守決策)
- 鳴牌判斷
- 立直判斷 (時機 / 默聽 vs 立直)
- Majsoul protobuf parser
- 跨多局統計儀表板
