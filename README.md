# Claude Buddy 🐣

Claude Code のツール使用でペットが育つたまごっちシステムです。

## セットアップ

### 1. ファイルを配置

```bash
mkdir -p ~/.claude/buddy
curl -o ~/.claude/buddy/pet.py https://raw.githubusercontent.com/Nao-kiddie/claude-buddy/main/pet.py
curl -o ~/.claude/buddy/theme.sh https://raw.githubusercontent.com/Nao-kiddie/claude-buddy/main/theme.sh
curl -o ~/.claude/buddy/watch.sh https://raw.githubusercontent.com/Nao-kiddie/claude-buddy/main/watch.sh
chmod +x ~/.claude/buddy/theme.sh ~/.claude/buddy/watch.sh
```

### 2. Claude Code の設定に追加

`~/.claude/settings.json` を編集して以下を追加します（既存の設定とマージしてください）：

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/buddy/pet.py --oneliner 2>/dev/null",
    "refreshInterval": 30
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/buddy/pet.py --update 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

### 3. 最初の卵を生成

```bash
python3 ~/.claude/buddy/pet.py --reset
```

## コマンド一覧

| コマンド | 説明 |
|---------|------|
| `/buddy` | ペットのステータスを表示 |
| `/buddy battle <敵名>` | バトルする |
| `/buddy pick <1-4>` | 産卵後に卵を選ぶ |
| `/buddy reset` | リセットして最初からやり直す |

### バトルできる敵

`残業` / `デバッグ` / `仕様変更` / `本番障害` / `技術的負債` / `会議地獄` / `定常業務`

## 成長ステージ

```
🥚 卵 (EXP 0-14)
  ↓ 15回のツール使用で孵化
🐣 ベビー (EXP 15-59)
  ↓ 60回で子供に
🐥 子供 (EXP 60-249)  ※バトル時ステータス半減
  ↓ 250回で大人に
🐔 大人 (EXP 250-349)
  ↓ 350回で産卵 → 次世代へ
```

## ポイント

- ツールを使うたびに EXP・満腹度・体力が回復
- **業務外12時間の放置でも死にません**（最悪ケース Q=0 でも生存確認済み）
- 死亡すると次世代に引き継がれるが品質が -30 される
- 産卵まで育てると次世代は品質 +20 でスタート
- 子供ステージでは技を覚え始める（EXP 20, 80 で習得）
- 大人になるとステータスが錆びる（24時間使わないと劣化）
