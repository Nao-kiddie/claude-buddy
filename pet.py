#!/usr/bin/env python3
"""Buddy - 世代を超えて進化するTamagotchi型ペット"""
import json, os, sys, hashlib, subprocess
from datetime import datetime, timezone

STATE_FILE = os.path.expanduser("~/.claude/buddy/state.json")

HATCH_AT     = 15    # 孵化
CHILD_AT     = 60    # 子供
ADULT_AT     = 250   # 大人
REPRODUCE_AT = 350   # 産卵（大人になってから100回）

BASE_HUNGER_DECAY      = 4.0   # /時間（業務外12時間放置で生存できる値）
BASE_HEALTH_DECAY      = 2.0
BASE_HEALTH_FAST_DECAY = 6.0   # 空腹時

STAT_RUST_GRACE    = 24.0   # バトルなしで錆び始めるまでの猶予（時間）
STAT_RUST_INTERVAL = 48.0   # 1ステータスポイント失うまでの時間

HUNGER_GAIN    = 6
HAPPINESS_GAIN = 3
HEALTH_GAIN    = 2

PET_NAMES = [
    "Pico","Mochi","Koko","Tama","Hoshi","Yuki","Kiri","Sora","Fuwa","Chibi",
    "Kumo","Hana","Riku","Nami","Tsuki","Kaze","Haru","Shio","Umi","Tsuyu",
    "Hotaru","Suzu","Kage","Mugi","Shiro","Kuro","Ao","Midori","Rin","Zen",
]

ART = {
"egg": """
    ／￣￣￣＼
   /   zZz   \\
  |  (_____)  |
  |           |
   \\＿＿＿＿／
    ～ 卵 ～""",

"baby": """
   ∩___∩
   |ﾟ ω ﾟ|   ≡≡ ！
   |      |
   |＿＿＿|
   ～孵化！～""",

"child": """
      ____
    /_ノ  ヽ_\\
   /( ・ )( ・)\\
  /   (__人__)  \\
  |   ` ⌒´   |
   \\          /""",

"adult": """
      ____
    /_ノ  ヽ_\\
   /(●)   (●)\\
  /   (__人__)  \\
  |   ` ⌒´   |  ドヤッ
   \\          /""",

"sick": """
      ____
    /_ノ  ヽ_\\
   /(x )  ( x)\\
  /   (__人__)  \\
  |    ；＿＿；  |
   \\  ぐったり /""",

"dead": """
      ____
    /_ノ  ヽ_\\
   /(×)   (×)\\
  /   (__人__)  \\
  |    + + +   |
   \\   合  掌  /""",
}

# フレーム2（アニメーション用）
ART2 = {
"egg": """
    ／￣￣￣＼
   /   ZzZ   \\
  |  (_____)  |
  |     ♪    |
   \\＿＿＿＿／
    ～ 卵 ～""",

"baby": """
   ∩___∩
   |ﾟ ▽ ﾟ|   ♪
    (    )
   |＿＿＿|
   ～孵化！～""",

"child": """
      ____
    /_ノ  ヽ_\\
   /( ・ )( ・)\\
  /   (__人__)  \\
  |   (⌒⌒)   | ﾉ
   \\          /""",

"adult": """
      ____
    /_ノ  ヽ_\\
   /(●)   (●)\\
  /   (__人__)  \\
  |   ` ⌒´   |  ♫
  /            \\""",

"sick": """
      ____
    /_ノ  ヽ_\\
   /(x )  ( x)\\
  /   (__人__)  \\
  |    ；＿；   |
   \\ ～ぐったり/""",

"dead": """
      ____
    /_ノ  ヽ_\\
   /(×)   (×)\\
  /   (__人__)  \\
  |             |
   \\   合  掌  /""",
}

# ──────────────────────────────────────────
# ステータス・技システム
# ──────────────────────────────────────────

STAT_KEYS   = ["hp", "atk", "def", "spa", "spd", "spe"]
STAT_LABELS = {"hp":"HP    ","atk":"こうげき","def":"ぼうぎょ",
               "spa":"とくこう","spd":"とくぼう","spe":"すばやさ"}
STAT_MAX    = 99
STAT_MIN    = 10

# 継承パラメータ
STAT_BASE_GAIN      = 5   # プラスプール stat の期待増加値
STAT_BASE_GAIN_EGG1 = 2   # 卵①（技継承あり）の期待増加値 ─ 技lvの恩恵と引き換えに低め
STAT_SICK_PEN       = 2   # 病気1回ごとに全 stat へ乗る期待値ペナルティ
STAT_NOISE          = 5   # ランダム幅 ±N

MOVE_POOL = [
    "バグ修正",  "リファクタ",  "コードレビュー", "テスト駆動",
    "アーキテクチャ設計", "デプロイ",  "ペアプロ",    "ドキュメント作成",
    "CI/CD整備", "API設計",    "セキュリティ監査","パフォーマンス最適化",
    "データモデリング",   "コード生成", "自動化",     "モニタリング設定",
    "アジャイルスプリント", "反復改善", "仕様書作成", "仕返し",
]
MOVE_THRESHOLDS = [20, 80, 150, 300]  # EXP で技を習得

MOVE_PROF_XP   = [0, 10, 30, 60, 100]          # v1〜v5 の習熟XP閾値
MOVE_PROF_MULT = [1.0, 1.1, 1.2, 1.35, 1.5]    # ダメージ倍率

# バトル用技データ  cat: physical=ATK/DEF, special=SPA/SPD, status=ダメージなし
MOVES = {
    "バグ修正":           {"power": 60, "acc": 95, "cat": "special",  "effect": None},
    "リファクタ":         {"power":  0, "acc":100, "cat": "status",   "effect": "def_up"},
    "コードレビュー":     {"power": 40, "acc": 90, "cat": "special",  "effect": "atk_down"},
    "テスト駆動":         {"power": 75, "acc": 85, "cat": "special",  "effect": None},
    "アーキテクチャ設計": {"power": 90, "acc": 80, "cat": "special",  "effect": None},
    "デプロイ":           {"power": 80, "acc": 90, "cat": "physical", "effect": None},
    "ペアプロ":           {"power":  0, "acc":100, "cat": "status",   "effect": "atk_up"},
    "ドキュメント作成":   {"power": 50, "acc":100, "cat": "special",  "effect": None},
    "CI/CD整備":          {"power": 55, "acc":100, "cat": "physical", "effect": None},
    "API設計":            {"power": 80, "acc": 85, "cat": "special",  "effect": None},
    "セキュリティ監査":   {"power":  0, "acc":100, "cat": "status",   "effect": "spe_down"},
    "パフォーマンス最適化":{"power": 0, "acc":100, "cat": "status",   "effect": "spe_up"},
    "データモデリング":   {"power": 85, "acc": 90, "cat": "special",  "effect": None},
    "コード生成":         {"power": 40, "acc": 95, "cat": "physical", "effect": "multi"},
    "自動化":             {"power": 70, "acc": 95, "cat": "physical", "effect": None},
    "モニタリング設定":   {"power":  0, "acc":100, "cat": "status",   "effect": "spy"},
    "アジャイルスプリント": {"power": 60, "acc":100, "cat": "swift",   "effect": None},
    "反復改善":            {"power": 35, "acc":100, "cat": "physical", "effect": "escalate"},
    "仕様書作成":          {"power":  0, "acc":100, "cat": "status",   "effect": "charge"},
    "仕返し":              {"power":  0, "acc":100, "cat": "counter",  "effect": None},
}

ENEMIES = {
    "残業": {
        "name": "残業", "emoji": "🌙",
        "hp": 60, "atk": 40, "def": 35, "spa": 30, "spd": 40, "spe": 20,
        "moves": [
            {"name": "サービス残業", "power": 55, "acc":100, "cat": "physical", "effect": None},
            {"name": "締め切り延長", "power":  0, "acc":100, "cat": "status",   "effect": "def_up"},
            {"name": "深夜作業",     "power": 70, "acc": 85, "cat": "physical", "effect": None},
            {"name": "追加タスク",   "power": 45, "acc":100, "cat": "physical", "effect": "atk_down"},
        ],
    },
    "デバッグ": {
        "name": "デバッグ", "emoji": "🐛",
        "hp": 40, "atk": 35, "def": 25, "spa": 55, "spd": 50, "spe": 70,
        "moves": [
            {"name": "再現しない",       "power": 50, "acc": 60, "cat": "special",  "effect": None},
            {"name": "環境依存",         "power": 40, "acc": 70, "cat": "special",  "effect": "spe_down"},
            {"name": "スタックトレース", "power": 65, "acc": 85, "cat": "special",  "effect": None},
            {"name": "無限ループ",       "power": 30, "acc": 90, "cat": "special",  "effect": "stun"},
        ],
    },
    "仕様変更": {
        "name": "仕様変更", "emoji": "📝",
        "hp": 45, "atk": 45, "def": 30, "spa": 60, "spd": 35, "spe": 55,
        "moves": [
            {"name": "急な変更要求",    "power": 70, "acc": 95, "cat": "physical", "effect": None},
            {"name": "認識の齟齬",      "power": 50, "acc": 85, "cat": "special",  "effect": "atk_down"},
            {"name": "スコープクリープ","power": 40, "acc":100, "cat": "status",   "effect": "buff_clear"},
            {"name": "やり直し",        "power": 80, "acc": 75, "cat": "physical", "effect": None},
        ],
    },
    "本番障害": {
        "name": "本番障害", "emoji": "🔥",
        "hp": 35, "atk": 75, "def": 20, "spa": 70, "spd": 25, "spe": 80,
        "moves": [
            {"name": "サービスダウン", "power": 90, "acc": 85, "cat": "physical", "effect": None},
            {"name": "アラート爆撃",  "power": 40, "acc":100, "cat": "special",  "effect": "spe_down"},
            {"name": "緊急対応",      "power": 70, "acc": 90, "cat": "physical", "effect": None},
            {"name": "データ消失",    "power": 85, "acc": 75, "cat": "special",  "effect": None},
        ],
    },
    "技術的負債": {
        "name": "技術的負債", "emoji": "💸",
        "hp": 75, "atk": 30, "def": 80, "spa": 35, "spd": 70, "spe": 15,
        "moves": [
            {"name": "スパゲッティコード", "power": 45, "acc":100, "cat": "physical", "effect": "spe_down"},
            {"name": "ドキュメントなし",   "power": 40, "acc": 90, "cat": "special",  "effect": "atk_down"},
            {"name": "テストなし",         "power": 60, "acc": 95, "cat": "physical", "effect": None},
            {"name": "負債増加",           "power":  0, "acc":100, "cat": "status",   "effect": "def_up"},
        ],
    },
    "会議地獄": {
        "name": "会議地獄", "emoji": "📊",
        "hp": 50, "atk": 25, "def": 45, "spa": 40, "spd": 55, "spe": 30,
        "moves": [
            {"name": "無限会議",   "power": 35, "acc":100, "cat": "special",  "effect": "spe_down"},
            {"name": "結論なし",   "power":  0, "acc":100, "cat": "status",   "effect": "atk_down"},
            {"name": "議事録なし", "power": 50, "acc": 90, "cat": "physical", "effect": None},
            {"name": "時間泥棒",   "power": 60, "acc": 85, "cat": "special",  "effect": "stun"},
        ],
    },
    "定常業務": {
        "name": "定常業務", "emoji": "📋",
        "hp": 20, "atk": 15, "def": 20, "spa": 10, "spd": 20, "spe": 25,
        "moves": [
            {"name": "日次報告",   "power": 25, "acc":100, "cat": "physical", "effect": None},
            {"name": "コピペ作業", "power": 20, "acc":100, "cat": "physical", "effect": None},
            {"name": "定型メール", "power":  0, "acc":100, "cat": "status",   "effect": "atk_down"},
            {"name": "承認待ち",   "power": 30, "acc": 90, "cat": "special",  "effect": "spe_down"},
        ],
    },
}

# カスタム敵生成用の汎用技プール
_ENEMY_MOVE_POOL = [
    {"name": "プレッシャー",       "power": 60, "acc": 90, "cat": "special",  "effect": None},
    {"name": "責任転嫁",           "power": 45, "acc": 85, "cat": "special",  "effect": "atk_down"},
    {"name": "形式主義",           "power":  0, "acc":100, "cat": "status",   "effect": "def_up"},
    {"name": "根性論",             "power": 70, "acc": 80, "cat": "physical", "effect": None},
    {"name": "パワハラ",           "power": 80, "acc": 75, "cat": "physical", "effect": "atk_down"},
    {"name": "マイクロマネジメント","power":  0, "acc":100, "cat": "status",   "effect": "spe_down"},
    {"name": "炎上案件",           "power": 85, "acc": 80, "cat": "physical", "effect": None},
    {"name": "割り込みタスク",     "power": 50, "acc": 95, "cat": "physical", "effect": "spe_down"},
    {"name": "深夜対応",           "power": 65, "acc": 90, "cat": "physical", "effect": None},
    {"name": "手戻り",             "power": 70, "acc": 85, "cat": "physical", "effect": None},
    {"name": "属人化",             "power":  0, "acc":100, "cat": "status",   "effect": "def_up"},
    {"name": "優先度混乱",         "power": 50, "acc": 90, "cat": "special",  "effect": "spe_down"},
    {"name": "暗黙のルール",       "power": 60, "acc": 85, "cat": "special",  "effect": None},
    {"name": "連絡ミス",           "power": 45, "acc": 90, "cat": "special",  "effect": "atk_down"},
    {"name": "ハリボテ報告",       "power": 40, "acc":100, "cat": "special",  "effect": "atk_down"},
    {"name": "根回し失敗",         "power": 55, "acc": 85, "cat": "special",  "effect": None},
]
_ENEMY_EMOJIS = ["👾","🤖","😈","💀","🦹","⚡","🌪️","💣","🗡️","☠️"]

def get_or_create_enemy(name, state):
    """既存の敵を返すか、類似敵を参考に新しい敵を生成してキャッシュする"""
    import difflib, random
    if name in ENEMIES:
        return ENEMIES[name], False

    custom = state.setdefault("custom_enemies", {})
    if name in custom:
        return custom[name], False

    # 既存の敵から最も似ているものをテンプレートに使う
    known = list(ENEMIES.keys())
    matches = difflib.get_close_matches(name, known, n=1, cutoff=0.3)

    seed = int(hashlib.md5(name.encode()).hexdigest(), 16)
    rng  = random.Random(seed)
    emoji = _ENEMY_EMOJIS[seed % len(_ENEMY_EMOJIS)]

    if matches:
        tmpl  = ENEMIES[matches[0]]
        hp    = max(30, min(75, tmpl["hp"]  + rng.randint(-15, 15)))
        stats = {k: max(15, min(80, tmpl[k] + rng.randint(-10, 10)))
                 for k in ("atk","def","spa","spd","spe")}
        # テンプレートの技を1〜2個汎用プールで置き換える
        base_moves = list(tmpl["moves"])
        swap_count = rng.randint(1, 2)
        for _ in range(swap_count):
            pool = [m for m in _ENEMY_MOVE_POOL if m["name"] not in {m2["name"] for m2 in base_moves}]
            if pool:
                base_moves[rng.randint(0, 3)] = rng.choice(pool)
        moves = base_moves
        ref   = matches[0]
    else:
        hp    = rng.randint(35, 65)
        stats = {k: rng.randint(20, 65) for k in ("atk","def","spa","spd","spe")}
        all_moves = list(_ENEMY_MOVE_POOL)
        for e in ENEMIES.values():
            all_moves += e["moves"]
        seen, unique = set(), []
        for m in all_moves:
            if m["name"] not in seen:
                seen.add(m["name"]); unique.append(m)
        moves = rng.sample(unique, 4)
        ref   = None

    enemy = {"name": name, "emoji": emoji, "hp": hp, **stats, "moves": moves}
    custom[name] = {"enemy": enemy, "ref": ref}
    return enemy, ref

def generate_stats(quality, user_id, generation):
    """Gen1 用：ユーザーID+世代のシードで決定論的に初期ステータスを生成"""
    seed = f"{user_id}-gen{generation}"
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    total = 150 + int(float(quality) * 0.5)   # Q=0→150, Q=100→200
    weights = [(h >> (i * 8)) & 0xFF for i in range(6)]
    total_w = sum(weights) or 1
    stats, remaining = {}, total
    for i, key in enumerate(STAT_KEYS[:-1]):
        val = max(STAT_MIN, min(50, round(total * weights[i] / total_w)))
        stats[key] = val
        remaining -= val
    stats[STAT_KEYS[-1]] = max(STAT_MIN, min(50, remaining))
    return stats

def inherit_stats(parent_stats, egg_quality, sick_count, rng, base_gain=STAT_BASE_GAIN):
    plus_count = max(1, round(float(egg_quality) / 100 * 6))
    plus_pool  = set(rng.sample(STAT_KEYS, min(plus_count, len(STAT_KEYS))))
    sick_pen   = sick_count * STAT_SICK_PEN

    stats = {}
    for key in STAT_KEYS:
        base   = parent_stats.get(key, 25)
        gain   = (base_gain if key in plus_pool else 0) - sick_pen
        change = gain + rng.randint(-STAT_NOISE, STAT_NOISE)
        stats[key] = max(STAT_MIN, min(STAT_MAX, base + change))
    return stats, plus_count

def get_move_for_slot(user_id, generation, slot, existing):
    seed = f"{user_id}-gen{generation}-slot{slot}"
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    available = [m for m in MOVE_POOL if m not in existing]
    return available[h % len(available)] if available else None

def apply_learn_moves(state):
    if state["stage"] in ("egg", "dead"):
        return state
    moves = state.setdefault("moves", [None, None, None, None])
    prof  = state.setdefault("move_proficiency", {})
    exp, uid, gen = state["experience"], state["user_id"], state["generation"]
    for slot, threshold in enumerate(MOVE_THRESHOLDS):
        if exp >= threshold and moves[slot] is None:
            existing = [m for m in moves if m]
            name = get_move_for_slot(uid, gen, slot, existing)
            moves[slot] = name
            if name and name not in prof:
                prof[name] = {"lv": 1, "xp": 0}
    state["moves"] = moves
    return state

def migrate(state):
    """旧stateに stats/moves/move_proficiency フィールドを追加"""
    if "stats" not in state:
        state["stats"] = generate_stats(state["quality"], state["user_id"], state["generation"])
    if "moves" not in state:
        em = state.get("egg_move")
        state["moves"] = [em, None, None, None] if em else [None, None, None, None]
        state = apply_learn_moves(state)
    state.setdefault("egg_move", None)
    if "move_proficiency" not in state:
        prof = {}
        for m in state.get("moves", []):
            if m:
                prof[m] = {"lv": 1, "xp": 0}
        state["move_proficiency"] = prof
    return state

# ──────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────

def get_user_id():
    try:
        r = subprocess.run(["git","config","user.email"],
                           capture_output=True, text=True, timeout=2)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return os.environ.get("USER", "unknown")

def pet_name_for(uid):
    h = int(hashlib.md5(uid.encode()).hexdigest(), 16)
    return PET_NAMES[h % len(PET_NAMES)]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def load():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE) as f:
        return json.load(f)

def save(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)  # atomic on POSIX

def quality_stars(q):
    stars = round(float(q) / 20)
    return "★" * stars + "☆" * (5 - stars)

def quality_label(q):
    q = float(q)
    if q >= 90: return "Legendary"
    if q >= 70: return "Epic"
    if q >= 50: return "Rare"
    if q >= 30: return "Common"
    return "Poor"

def decay_rate(base, quality):
    """品質が高いほど減りが遅い (quality=100 → 50%オフ)"""
    return base * (1.0 - float(quality) / 200.0)

# ──────────────────────────────────────────
# 状態生成
# ──────────────────────────────────────────

def new_egg(uid, quality, generation, lineage, egg_move=None, egg_move_lv=1):
    import random
    q = float(max(0, min(100, quality)))
    stats = generate_stats(q, uid, generation)
    hp_bonus = stats["hp"] * 0.3   # HP stat → 初期体力ボーナス
    moves = [egg_move, None, None, None] if egg_move else [None, None, None, None]
    prof  = {egg_move: {"lv": egg_move_lv, "xp": MOVE_PROF_XP[min(egg_move_lv - 1, 4)]}} if egg_move else {}
    return {
        "user_id":    uid,
        "pet_name":   random.choice(PET_NAMES),
        "stage":      "egg",
        "generation": generation,
        "quality":    q,
        "sick_count": 0,
        "was_sick":   False,
        "hunger":     60.0 + q * 0.4,
        "happiness":  60.0 + q * 0.4,
        "health":     min(100.0, 70.0 + q * 0.3 + hp_bonus * 0.1),
        "experience": 0,
        "last_updated": now_iso(),
        "born_at":    now_iso(),
        "hatched_at": None,
        "died_at":    None,
        "last_event": None,
        "lineage":          lineage,
        "stats":            stats,
        "moves":            moves,
        "egg_move":         None,
        "move_proficiency": prof,
    }

def fresh(uid):
    return new_egg(uid, 50.0, 1, [])

# ──────────────────────────────────────────
# ゲームロジック
# ──────────────────────────────────────────

def apply_decay(state):
    if state["stage"] in ("dead", "egg"):
        return state
    last  = datetime.fromisoformat(state["last_updated"])
    hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
    q     = state["quality"]

    hunger_rate  = decay_rate(BASE_HUNGER_DECAY, q)
    hunger_start = state["hunger"]
    hunger_end   = max(0.0, hunger_start - hunger_rate * hours)
    state["hunger"] = hunger_end

    FAST_THRESHOLD = 20.0
    normal_rate = decay_rate(BASE_HEALTH_DECAY, q)
    fast_rate   = decay_rate(BASE_HEALTH_FAST_DECAY, q)
    if hunger_start <= FAST_THRESHOLD:
        # 最初から空腹
        health_loss = fast_rate * hours
    elif hunger_end <= FAST_THRESHOLD and hunger_rate > 0:
        # 途中で空腹閾値を下回る
        hours_normal = (hunger_start - FAST_THRESHOLD) / hunger_rate
        hours_fast   = hours - hours_normal
        health_loss  = normal_rate * hours_normal + fast_rate * hours_fast
    else:
        health_loss = normal_rate * hours
    state["health"] = max(0.0, state["health"] - health_loss)

    # 大人がClaude Codeを使わないとステータスが錆びる（取り戻せない）
    if state["stage"] == "adult" and state.get("stats"):
        last_exp = state.get("last_exp_at")
        idle_enough = True
        if last_exp:
            idle_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last_exp)).total_seconds() / 3600
            idle_enough = idle_h > STAT_RUST_GRACE
        if idle_enough:
            state["stat_rust"] = state.get("stat_rust", 0.0) + hours / STAT_RUST_INTERVAL
            if state["stat_rust"] >= 1.0:
                pts = int(state["stat_rust"])
                state["stat_rust"] -= pts
                for key in STAT_KEYS:
                    state["stats"][key] = max(STAT_MIN, state["stats"][key] - pts)
                state["last_event"] = "rusted"

    return state

def apply_feed(state):
    """ツール使用1回分の栄養を与える"""
    if state["stage"] == "dead":
        return state
    if state.get("pending_eggs"):
        return state  # 卵を選ぶまでEXPは増えない
    state["experience"] += 1
    state["last_exp_at"] = now_iso()
    state["hunger"]     = min(100.0, state["hunger"]    + HUNGER_GAIN)
    state["happiness"]  = min(100.0, state["happiness"] + HAPPINESS_GAIN)
    if state["stage"] != "egg":
        state["health"] = min(100.0, state["health"]    + HEALTH_GAIN)
    state["last_updated"] = now_iso()
    return state

def _make_lineage_entry(state, cause):
    lineage = list(state.get("lineage", []))
    lineage.append({
        "generation":    state["generation"],
        "quality":       float(state["quality"]),
        "cause":         cause,
        "stage_reached": state["stage"],
        "sick_count":    state.get("sick_count", 0),
        "exp":           state["experience"],
    })
    return lineage

def spawn_next_gen(state, cause):
    """死亡時のみ使用。品質ペナルティを付けて次世代卵を1つ生成"""
    lineage = _make_lineage_entry(state, cause)
    new_q   = max(0, float(state["quality"]) - 30)
    egg = new_egg(state["user_id"], new_q, state["generation"] + 1, lineage)
    egg["last_event"] = cause
    return egg

def generate_eggs(state):
    """産卵：4つの卵を生成（各技スロット①②③④に対応）して pending_eggs に格納"""
    import random, time
    rng     = random.Random(time.time())
    q       = float(state["quality"])
    gen     = state["generation"]
    uid     = state["user_id"]
    lineage = _make_lineage_entry(state, "reproduced")
    base_q  = q + 20 - state.get("sick_count", 0) * 5

    parent_stats = state.get("stats", generate_stats(q, uid, gen))
    parent_moves = state.get("moves", [None, None, None, None])
    parent_prof  = state.get("move_proficiency", {})

    eggs = []
    for i in range(4):
        # 品質: ±5 のランダム変動
        egg_q = float(max(0, min(100, base_q + rng.randint(-5, 5))))

        # 対応スロットの技を引き継ぐ（未習得スロットは None）
        move = parent_moves[i] if i < len(parent_moves) else None

        # ステータス: 技を引き継ぐ場合は成長期待値が低い
        sick_count = state.get("sick_count", 0)
        gain = STAT_BASE_GAIN_EGG1 if move else STAT_BASE_GAIN
        stats, _ = inherit_stats(parent_stats, egg_q, sick_count, rng, base_gain=gain)

        # 技の習熟度を引き継ぐ
        move_lv = parent_prof.get(move, {}).get("lv", 1) if move else 1

        eggs.append({
            "index":   i + 1,
            "quality": egg_q,
            "stats":   stats,
            "move":    move,
            "move_lv": move_lv,
            "lineage": lineage,
        })

    return eggs

def apply_evolve(state):
    """ステージ遷移・死亡・産卵を処理"""
    exp, health, stage = state["experience"], state["health"], state["stage"]

    # 死亡状態 → 次世代卵を自動生成
    if stage == "dead":
        return spawn_next_gen(state, "died")

    # 体力切れ → 死亡
    if health <= 0 and stage != "egg":
        state["stage"]   = "dead"
        state["died_at"] = now_iso()
        return state

    # 病気発症（重複カウントを防ぐ was_sick フラグ）
    if health < 25 and stage not in ("egg","sick","dead"):
        if not state.get("was_sick", False):
            state["sick_count"] = state.get("sick_count", 0) + 1
            state["was_sick"]   = True
        state["stage"] = "sick"
        return state

    # 病気回復
    if stage == "sick" and health >= 60:
        state["was_sick"] = False
        state["stage"]    = "child" if exp >= CHILD_AT else "baby"
        return state

    # 技習得チェック
    state = apply_learn_moves(state)

    # 大人が産卵条件を満たした → 3つの卵を生成して選択待ち
    if stage == "adult" and exp >= REPRODUCE_AT:
        if not state.get("pending_eggs"):
            state["pending_eggs"] = generate_eggs(state)
            state["last_event"]   = "eggs_ready"

    # 通常成長
    if   stage == "egg"   and exp >= HATCH_AT:
        state["stage"] = "baby";   state["hatched_at"] = now_iso()
    elif stage == "baby"  and exp >= CHILD_AT:
        state["stage"] = "child"
    elif stage == "child" and exp >= ADULT_AT:
        state["stage"] = "adult"

    return state

# ──────────────────────────────────────────
# 表示
# ──────────────────────────────────────────

def bar(v, width=18):
    v      = max(0.0, min(100.0, float(v)))
    filled = round(v / 100 * width)
    return f"[{'█'*filled}{'░'*(width-filled)}] {int(v):3d}%"

def show(state):
    stage = state["stage"]
    q     = float(state["quality"])
    gen   = state["generation"]
    exp   = state["experience"]
    event = state.get("last_event")

    if event == "eggs_ready":
        print(f"\n  ✨ 産卵！ 4つの卵が生まれました ✨")
    elif event == "reproduced":
        print(f"\n  *** 産卵！ 第{gen}世代誕生 ***")
    elif event == "died":
        print(f"\n  ...死亡により第{gen}世代が始まりました")
        print(f"  品質は下がりましたが、また育ててください")
    state["last_event"] = None

    # 卵選択中の表示
    pending = state.get("pending_eggs")
    if pending:
        print(ART.get(stage, ART["egg"]))
        print(f"  {state['pet_name']} Gen{gen} が産卵しました！")
        print(f"  /buddy pick 1〜4 でどれを育てるか選んでください\n")
        _show_egg_choices(pending)
        return

    print(ART.get(stage, ART["egg"]))
    print(f"  Name     : {state['pet_name']}")
    print(f"  Gen      : 第{gen}世代")
    print(f"  Quality  : {quality_stars(q)}  {quality_label(q)}  (Q={int(q)})")
    print(f"  Stage    : {stage.upper()}")
    print(f"  EXP      : {exp} tool uses")
    if state.get("sick_count", 0):
        pen = state["sick_count"] * 5
        print(f"  病歴     : {state['sick_count']}回  (産卵時 Q-{pen})")

    if stage not in ("egg","dead"):
        print(f"\n  Hunger    {bar(state['hunger'])}")
        print(f"  Happiness {bar(state['happiness'])}")
        print(f"  Health    {bar(state['health'])}")

    print()
    if stage == "egg":
        print(f"  あと {max(0, HATCH_AT - exp)} 回のツール使用で孵化...")
    elif stage == "baby":
        print(f"  あと {max(0, CHILD_AT - exp)} 回で子供に成長！")
    elif stage == "child":
        print(f"  あと {max(0, ADULT_AT - exp)} 回で大人に！")
    elif stage == "adult":
        left = max(0, REPRODUCE_AT - exp)
        print(f"  あと {left} 回で次世代の卵を産みます！")
        next_q = min(100, q + 20 - state.get("sick_count",0) * 5)
        print(f"  次世代品質予測: {quality_stars(next_q)} Q={int(next_q)}")
        last_exp = state.get("last_exp_at")
        if last_exp:
            idle_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last_exp)).total_seconds() / 3600
            if idle_h > STAT_RUST_GRACE:
                rust = state.get("stat_rust", 0.0)
                print(f"  ⚠️  {int(idle_h)}h 使用なし  ステータスが錆びています！  (錆び: {rust:.2f}/1.0)")
        else:
            print(f"  ⚠️  Claude Code を使うとステータスが維持される！")
    elif stage == "sick":
        print(f"  病気中... 使い続けて回復しよう！")
    elif stage == "dead":
        print(f"  次のツール使用で第{gen+1}世代が始まります...")

    # ステータス
    stats = state.get("stats", {})
    if stats:
        print("\n  ┌── ステータス " + "─" * 25)
        for key in STAT_KEYS:
            val = stats.get(key, 0)
            filled = round(val / STAT_MAX * 12)
            b = "█" * filled + "░" * (12 - filled)
            print(f"  │ {STAT_LABELS[key]}  [{b}]  {val:2d}")
        print("  └" + "─" * 38)

    # 技
    moves = state.get("moves", [None]*4)
    prof  = state.get("move_proficiency", {})
    print("\n  ┌── 技 " + "─" * 32)
    nums = ["①","②","③","④"]
    for i, move in enumerate(moves):
        if move:
            lv     = prof.get(move, {}).get("lv", 1)
            xp     = prof.get(move, {}).get("xp", 0)
            next_xp = MOVE_PROF_XP[min(lv, 4)]
            lv_str = f" \033[33mv{lv}\033[0m" if lv > 1 else f" v{lv}"
            xp_str = f"  ({xp}/{next_xp}xp)" if lv < 5 else "  (MAX)"
            marker = " ← 卵技" if move == state.get("egg_move") else ""
            print(f"  │ {nums[i]} {move}{lv_str}{xp_str}{marker}")
        else:
            th = MOVE_THRESHOLDS[i]
            print(f"  │ {nums[i]} ─ (EXP {th} で習得)")
    learned = [m for m in moves if m]
    if learned:
        print(f"  │")
        print(f"  │ 🥚 次世代へ遺伝: 各スロットの技をそれぞれの卵に引き継ぎます")
    print("  └" + "─" * 38)

    lineage = state.get("lineage", [])
    if lineage:
        print("\n  ┌── 系譜 " + "─" * 30)
        for e in lineage:
            cause = "産卵" if e["cause"] == "reproduced" else "死亡"
            sick  = f"  病:{e['sick_count']}回" if e["sick_count"] else ""
            print(f"  │ Gen{e['generation']:2d}  {quality_stars(e['quality'])}  Q={int(e['quality']):3d}  [{cause}]{sick}")
        print("  └" + "─" * 38)

    battle_log = state.get("battle_log", [])
    if battle_log:
        icon_map = {"win": "🏆", "lose": "💔", "draw": "🤝"}
        # 撃破済みユニーク敵
        defeated = list(dict.fromkeys(e["enemy"] for e in battle_log if e["result"] == "win"))
        if defeated:
            print("\n  ┌── 撃破記録 " + "─" * 27)
            for name in defeated:
                emoji = next((e["emoji"] for e in reversed(battle_log) if e["enemy"] == name), "👾")
                print(f"  │ 🏆 {emoji} {name}")
            print("  └" + "─" * 38)
        # 直近5件のバトル
        print("\n  ┌── バトル履歴 " + "─" * 25)
        for entry in reversed(battle_log[-5:]):
            icon = icon_map.get(entry["result"], "?")
            print(f"  │ {icon} {entry['emoji']} {entry['enemy']}")
        print("  └" + "─" * 38)
    print()

# ──────────────────────────────────────────
# バトル
# ──────────────────────────────────────────

def do_battle(state, enemy):
    import random, time
    rng = random.Random()

    pet_stats = state.get("stats", {})
    child_penalty = state["stage"] == "child"
    if child_penalty:
        pet_stats = {k: max(1, v // 2) for k, v in pet_stats.items()}
    pet_moves = [m for m in state.get("moves", []) if m]
    if not pet_moves:
        pet_moves = ["バグ修正"]

    bs = {
        "pet_hp":       pet_stats.get("hp", 50),
        "pet_hp_max":   pet_stats.get("hp", 50),
        "enemy_hp":     enemy["hp"],
        "enemy_hp_max": enemy["hp"],
        "pet_stunned":   False,
        "enemy_stunned": False,
        "pet_mods":   {"atk":1.0,"def":1.0,"spa":1.0,"spd":1.0,"spe":1.0},
        "enemy_mods": {"atk":1.0,"def":1.0,"spa":1.0,"spd":1.0,"spe":1.0},
        "pet_last_dmg":  0,
        "pet_charge":    False,
        "pet_streak":    {},
    }

    def hp_bar(hp, hp_max, width=14):
        ratio = max(0.0, hp / hp_max)
        filled = round(ratio * width)
        c = "\033[32m" if ratio > 0.5 else ("\033[33m" if ratio > 0.25 else "\033[31m")
        return f"{c}{'█'*filled}{'░'*(width-filled)}\033[0m"

    def calc_dmg(move, a_stats, a_mods, d_stats, d_mods):
        cat = move["cat"]
        if cat == "physical":
            atk  = a_stats.get("atk", 30) * a_mods["atk"]
            def_ = d_stats.get("def", 30) * d_mods["def"]
        elif cat == "swift":
            atk   = a_stats.get("spe", 30) * a_mods["spe"]
            def_  = d_stats.get("spe", 30) * d_mods["spe"]
            early = max(1.0, 2.1 - turn * 0.1)  # turn1: ×2.0, turn5: ×1.6, turn10: ×1.1
            base  = (atk / max(def_, 1)) * move["power"] / 5 * early
            return max(1, int(base * rng.uniform(0.85, 1.0)))
        else:
            atk  = a_stats.get("spa", 30) * a_mods["spa"]
            def_ = d_stats.get("spd", 30) * d_mods["spd"]
        base = (atk / max(def_, 1)) * move["power"] / 5
        return max(1, int(base * rng.uniform(0.85, 1.0)))

    def apply_eff(effect, actor_mods, target_mods, target_is_pet):
        msgs = []
        if   effect == "atk_up":    actor_mods["atk"]  = min(2.0, actor_mods["atk"]  * 1.2); msgs.append("攻撃が上がった！")
        elif effect == "def_up":    actor_mods["def"]  = min(2.0, actor_mods["def"]  * 1.2); msgs.append("防御が上がった！")
        elif effect == "spe_up":    actor_mods["spe"]  = min(2.0, actor_mods["spe"]  * 1.2); msgs.append("すばやさが上がった！")
        elif effect == "atk_down":  target_mods["atk"] = max(0.5, target_mods["atk"] * 0.8); msgs.append("相手の攻撃が下がった！")
        elif effect == "spd_down":  target_mods["spd"] = max(0.5, target_mods["spd"] * 0.8); msgs.append("相手の特防が下がった！")
        elif effect == "spe_down":  target_mods["spe"] = max(0.5, target_mods["spe"] * 0.8); msgs.append("相手のすばやさが下がった！")
        elif effect == "buff_clear":
            mods = bs["pet_mods"] if target_is_pet else bs["enemy_mods"]
            for k in mods: mods[k] = 1.0
            msgs.append("バフがすべて消された！")
        elif effect == "spy":       msgs.append("相手のステータスを看破した！")
        return msgs

    def header():
        pn = state["pet_name"]; en = enemy["name"]; ee = enemy["emoji"]
        print()
        print("  ╔═══════════════════════════════════╗")
        print("  ║          ⚔️  BATTLE  ⚔️              ║")
        print("  ╚═══════════════════════════════════╝")
        print()
        print(f"  🐔 {pn} Gen{state['generation']}  [{hp_bar(bs['pet_hp'],bs['pet_hp_max'])}]  {bs['pet_hp']}/{bs['pet_hp_max']}")
        if child_penalty:
            print(f"  ⚠️  子供のため全ステータス半減中")
        print(f"  {ee} {en}  [{hp_bar(bs['enemy_hp'],bs['enemy_hp_max'])}]  {bs['enemy_hp']}/{bs['enemy_hp_max']}")
        print()

    pn = state["pet_name"]; en = enemy["name"]

    for turn in range(1, 11):
        os.system("clear"); header()
        print(f"  ─── ターン {turn} ───────────────────────")
        print()
        time.sleep(0.4)

        # 先攻決定
        pet_spe   = pet_stats.get("spe", 30) * bs["pet_mods"]["spe"]
        enemy_spe = enemy["spe"] * bs["enemy_mods"]["spe"]
        pet_first = pet_spe >= enemy_spe

        # 技選択
        pmn  = rng.choice(pet_moves)
        pm   = dict(MOVES.get(pmn, {"power":50,"acc":90,"cat":"physical","effect":None}))
        em   = rng.choice(enemy["moves"])

        turn_log = []

        def pet_act():
            if rng.randint(1,100) > pm["acc"]:
                turn_log.append(f"  ✗  {pn} の {pmn} は外れた！"); return
            # 習熟度取得
            pprof = state.setdefault("move_proficiency", {})
            if pmn not in pprof:
                pprof[pmn] = {"lv": 1, "xp": 0}
            lv   = pprof[pmn]["lv"]
            mult = MOVE_PROF_MULT[min(lv - 1, 4)]
            lv_str = f" \033[33mv{lv}\033[0m" if lv > 1 else ""
            if pm["cat"] == "counter":
                last = bs["pet_last_dmg"]
                d = max(1, int(last * 2 * mult)) if last > 0 else 1
                bs["enemy_hp"] = max(0, bs["enemy_hp"] - d)
                sfx = f"受けた {last} の2倍！" if last > 0 else "しかしダメージを受けていない..."
                turn_log.append(f"  ⚡ {pn} の {pmn}{lv_str}！ → \033[33m{d} ダメージ\033[0m！  {sfx}")
            elif pm["cat"] == "status":
                if pm.get("effect") == "charge":
                    bs["pet_charge"] = True
                    turn_log.append(f"  ✦  {pn} の {pmn}{lv_str}！  次の攻撃の威力が2倍になった！")
                else:
                    msgs = apply_eff(pm.get("effect"), bs["pet_mods"], bs["enemy_mods"], False)
                    turn_log.append(f"  ✦  {pn} の {pmn}{lv_str}！  {'  '.join(msgs)}")
            else:
                # 反復強化（escalate）
                if pm.get("effect") == "escalate":
                    streak = bs["pet_streak"].get(pmn, 0) + 1
                    bs["pet_streak"][pmn] = streak
                    escalate_mult = min(0.5 * streak, 2.0)
                else:
                    escalate_mult = 1.0
                # チャージ倍率
                charge_mult = 1.0
                if bs["pet_charge"]:
                    charge_mult = 2.0
                    bs["pet_charge"] = False
                hits = rng.randint(2,3) if pm.get("effect") == "multi" else 1
                total = 0
                for _ in range(hits):
                    d = max(1, int(calc_dmg(pm, pet_stats, bs["pet_mods"], enemy, bs["enemy_mods"]) * mult * charge_mult * escalate_mult))
                    total += d; bs["enemy_hp"] = max(0, bs["enemy_hp"] - d)
                hs = f" ({hits}回ヒット)" if hits > 1 else ""
                extras = []
                if charge_mult > 1.0: extras.append("チャージ×2！")
                if escalate_mult != 1.0: extras.append(f"強化×{bs['pet_streak'].get(pmn,1)}！")
                extra_str = ("  " + "  ".join(extras)) if extras else ""
                turn_log.append(f"  ⚡ {pn} の {pmn}{lv_str}！ → \033[33m{total} ダメージ\033[0m！{hs}{extra_str}")
                if pm.get("effect") and pm["effect"] not in ("multi", "escalate"):
                    for msg in apply_eff(pm["effect"], bs["pet_mods"], bs["enemy_mods"], False):
                        turn_log.append(f"     {msg}")
            # 習熟XP加算・レベルアップチェック
            pprof[pmn]["xp"] += 1
            new_lv = sum(1 for t in MOVE_PROF_XP if pprof[pmn]["xp"] >= t)
            new_lv = min(new_lv, 5)
            if new_lv > lv:
                pprof[pmn]["lv"] = new_lv
                turn_log.append(f"  ✨ \033[33m{pmn} が v{new_lv} に上がった！\033[0m")

        def enemy_act():
            if rng.randint(1,100) > em["acc"]:
                turn_log.append(f"  ✗  {en} の {em['name']} は外れた！"); return
            if em["cat"] == "status":
                msgs = apply_eff(em.get("effect"), bs["enemy_mods"], bs["pet_mods"], True)
                turn_log.append(f"  ✦  {en} の {em['name']}！  {'  '.join(msgs)}")
                if em.get("effect") == "stun":
                    bs["pet_stunned"] = True
                    turn_log.append(f"     {pn} は次のターン動けない！")
            else:
                d = calc_dmg(em, enemy, bs["enemy_mods"], pet_stats, bs["pet_mods"])
                bs["pet_hp"] = max(0, bs["pet_hp"] - d)
                bs["pet_last_dmg"] = d
                turn_log.append(f"  💥 {en} の {em['name']}！ → \033[31m{d} ダメージ\033[0m！")
                if em.get("effect") == "stun":
                    bs["pet_stunned"] = True
                    turn_log.append(f"     {pn} は次のターン動けない！")

        actions = [(pet_act, bs, "pet_stunned"), (enemy_act, bs, "enemy_stunned")]
        if not pet_first:
            actions.reverse()

        for act_fn, _, stun_key in actions:
            if bs[stun_key]:
                who = pn if stun_key == "pet_stunned" else en
                turn_log.append(f"  💫 {who} は動けない！")
                bs[stun_key] = False
            else:
                act_fn()
            if bs["pet_hp"] <= 0 or bs["enemy_hp"] <= 0:
                break

        for line in turn_log:
            print(line); time.sleep(0.35)
        print(); time.sleep(0.3)

        if bs["pet_hp"] <= 0 or bs["enemy_hp"] <= 0:
            break

    # 結果
    os.system("clear"); header()
    state["last_battle_at"] = now_iso()

    if bs["enemy_hp"] <= 0 and bs["pet_hp"] > 0:
        result = "win"
        print(f"  \033[33;1m🎉 {pn} の勝利！  {en} を倒した！\033[0m")
        state["experience"] = state.get("experience", 0) + 30
        state["happiness"]  = min(100.0, state.get("happiness", 50.0) + 10)
        print(f"  EXP +30  Happiness +10")
    elif bs["pet_hp"] <= 0:
        result = "lose"
        print(f"  \033[31;1m😵 {pn} は倒れた...  {en} に負けた\033[0m")
        state["happiness"]  = max(0.0, state.get("happiness", 50.0) - 20)
        print(f"  Happiness -20")
    else:
        result = "draw"
        print(f"  ⏱️  時間切れ！  引き分け")
        state["happiness"]  = max(0.0, state.get("happiness", 50.0) - 5)
        print(f"  Happiness -5")

    log = state.setdefault("battle_log", [])
    log.append({"enemy": en, "emoji": enemy.get("emoji","👾"), "result": result, "at": now_iso()})
    state["battle_log"] = log[-50:]  # 直近50件保持
    print()
    return state

# ──────────────────────────────────────────
# ガチャ演出
# ──────────────────────────────────────────

_RST  = "\033[0m"
_BOLD = "\033[1m"

_QUALITY_COLOR = {
    "Legendary": "\033[33;1m",  # 金
    "Epic":      "\033[35;1m",  # 紫
    "Rare":      "\033[36;1m",  # 青
    "Common":    "\033[37;1m",  # 白
    "Poor":      "\033[90m",    # 灰
}
_RAINBOW = ["\033[31;1m","\033[33;1m","\033[32;1m","\033[36;1m","\033[34;1m","\033[35;1m"]

def gacha_reveal(egg, new_gen=None):
    import time
    q     = float(egg["quality"])
    label = quality_label(q)
    stats = egg["stats"]
    move  = egg["move"]

    # サスペンス
    print("\n\n  卵を開封中", end="", flush=True)
    for _ in range(6):
        time.sleep(0.25)
        print("・", end="", flush=True)
    time.sleep(0.4)
    os.system("clear")

    c = _QUALITY_COLOR.get(label, _BOLD)

    if label == "Legendary":
        banner = f"{'★' * 5}  ✨ LEGENDARY ✨  {'★' * 5}"
        for frame in range(10):
            os.system("clear")
            fc = _RAINBOW[frame % len(_RAINBOW)]
            print(f"\n\n  {fc}{banner}{_RST}\n")
            print(f"  {fc}Q={int(q)}  {quality_stars(q)}{_RST}")
            time.sleep(0.11)
        os.system("clear")
        print(f"\n\n  {c}{banner}{_RST}\n")
    elif label == "Epic":
        banner = f"{'★' * 3}  💜 EPIC 💜  {'★' * 3}"
        print(f"\n\n  {c}{banner}{_RST}\n")
    elif label == "Rare":
        banner = f"{'★' * 2}  💙 RARE 💙  {'★' * 2}"
        print(f"\n\n  {c}{banner}{_RST}\n")
    elif label == "Common":
        print(f"\n\n  {c}COMMON{_RST}\n")
    else:
        print(f"\n\n  {c}POOR{_RST}\n")

    print(f"  {c}Quality : {quality_stars(q)} {label} (Q={int(q)}){_RST}")
    move_str = move if move else "なし（経験で習得）"
    print(f"  技      : {move_str}\n")

    sbar = lambda v: "█" * round(v / STAT_MAX * 10) + "░" * (10 - round(v / STAT_MAX * 10))
    print(f"  {c}HP      [{sbar(stats['hp'])}] {stats['hp']:2d}{_RST}")
    print(f"  {c}こうげき [{sbar(stats['atk'])}] {stats['atk']:2d}{_RST}")
    print(f"  {c}ぼうぎょ [{sbar(stats['def'])}] {stats['def']:2d}{_RST}")
    print(f"  {c}とくこう [{sbar(stats['spa'])}] {stats['spa']:2d}{_RST}")
    print(f"  {c}とくぼう [{sbar(stats['spd'])}] {stats['spd']:2d}{_RST}")
    print(f"  {c}すばやさ [{sbar(stats['spe'])}] {stats['spe']:2d}{_RST}")
    gen_str = f"第{new_gen}世代" if new_gen else ""
    if move:
        print(f"\n  {gen_str}が始まります！  技「{move}」を引き継ぎました。")
    else:
        print(f"\n  {gen_str}が始まります！  技は経験で習得します。")
    print()

# ──────────────────────────────────────────
# ステータスバー用ワンライナー
# ──────────────────────────────────────────

STAGE_ICON = {
    "egg": "🥚", "baby": "🐣", "child": "🐥",
    "adult": "🐔", "sick": "🤒", "dead": "💀",
}

def oneliner(state):
    stage = state["stage"]
    icon  = STAGE_ICON.get(stage, "?")
    name  = state["pet_name"]
    gen   = state["generation"]
    q     = int(state["quality"])
    exp   = state["experience"]
    if state.get("pending_eggs"):
        print(f"🥚🥚🥚🥚 {name} Gen{gen} | 産卵中！ /buddy pick 1〜4")
    elif stage in ("egg", "dead"):
        print(f"{icon} {name} Gen{gen} Q={q} | {stage.upper()} EXP:{exp}")
    else:
        h = int(state["hunger"])
        hp = int(state["health"])
        print(f"{icon} {name} Gen{gen} Q={q} | ❤️{hp}% 🍖{h}% EXP:{exp}")

def _show_egg_choices(eggs):
    """産卵後の3択表示"""
    sbar = lambda v: "█"*round(v/STAT_MAX*10) + "░"*(10-round(v/STAT_MAX*10))
    for e in eggs:
        q = float(e["quality"])
        print(f"  ┌── 卵{e['index']} {quality_stars(q)} {quality_label(q)} (Q={int(q)}) " + "─"*10)
        s = e["stats"]
        print(f"  │  HP[{sbar(s['hp'])}]{s['hp']:2d}  こうげき[{sbar(s['atk'])}]{s['atk']:2d}  ぼうぎょ[{sbar(s['def'])}]{s['def']:2d}")
        print(f"  │  とくこう[{sbar(s['spa'])}]{s['spa']:2d}  とくぼう[{sbar(s['spd'])}]{s['spd']:2d}  すばやさ[{sbar(s['spe'])}]{s['spe']:2d}")
        mlv = e.get("move_lv", 1)
        move_str = f"{e['move']} v{mlv}" if e.get("move") else "なし（経験で習得）"
        print(f"  │  技: {move_str}")
        print(f"  └" + "─"*40)
        print()

# ──────────────────────────────────────────
# エントリーポイント
# ──────────────────────────────────────────

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--update"
    uid  = get_user_id()

    if mode == "--reset":
        save(fresh(uid))
        print(f"新しい卵が生まれました！ Gen1 / Quality: {quality_stars(50)} Rare (Q=50)")
        return

    state = migrate(load() or fresh(uid))
    state = apply_decay(state)

    if mode == "--egg":
        slot  = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 0
        moves = state.get("moves", [])
        if 0 <= slot < len(moves) and moves[slot]:
            state["egg_move"] = moves[slot]
            save(state)
            print(f"卵技を「{moves[slot]}」に設定しました。次世代に継承されます。")
        else:
            print(f"技スロット {slot+1} は未習得です。")
        return

    if mode == "--pick":
        pending = state.get("pending_eggs", [])
        if not pending:
            print("現在選べる卵はありません。")
            return
        idx = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 0
        if not (0 <= idx < len(pending)):
            print(f"1〜{len(pending)} の番号で選んでください。")
            return
        chosen  = pending[idx]
        new_gen = state["generation"] + 1
        egg_move_lv = chosen.get("move_lv", 1)
        egg = new_egg(state["user_id"], chosen["quality"], new_gen, chosen["lineage"],
                      egg_move=chosen["move"], egg_move_lv=egg_move_lv)
        egg["stats"]      = chosen["stats"]
        egg["moves"][0]   = chosen["move"]
        egg["last_event"] = "reproduced"
        gacha_reveal(chosen, new_gen)
        save(egg)
        return

    if mode == "--update":
        # hookから呼ばれる：栄養補給 + ステージ更新のみ（表示なし）
        state = apply_feed(state)
        state = apply_evolve(state)
        save(state)

    elif mode == "--oneliner":
        state = apply_evolve(state)
        oneliner(state)
        save(state)

    elif mode == "--show":
        # /buddy から呼ばれる：ステージ更新 + 表示（feedはhookに任せる）
        state = apply_evolve(state)
        show(state)
        save(state)

    elif mode == "--battle":
        import time as _time
        if len(sys.argv) < 3:
            print("相手を選んでください:")
            for k, v in ENEMIES.items():
                print(f"  {v['emoji']} {k}")
            return
        if state["stage"] in ("egg", "dead"):
            print(f"バトルできるのは孵化後のペットだけです。(現在: {state['stage']})")
            return
        enemy_name = sys.argv[2]
        enemy, ref = get_or_create_enemy(enemy_name, state)
        if ref is not False and ref is not None:
            print(f"\n  {enemy['emoji']} 未知の敵「{enemy_name}」を生成しました！  (「{ref}」を参考に)")
            _time.sleep(1.2)
        elif ref is None and enemy_name not in ENEMIES:
            print(f"\n  {enemy['emoji']} 未知の敵「{enemy_name}」を生成しました！")
            _time.sleep(1.2)
        state = do_battle(state, enemy)
        state = apply_evolve(state)
        save(state)

    elif mode == "--watch":
        _watch_loop()

def _status_message(state):
    stage, exp, q = state["stage"], state["experience"], float(state["quality"])
    if stage == "egg":
        return f"  あと {max(0, HATCH_AT - exp)} 回のツール使用で孵化..."
    elif stage == "baby":
        return f"  あと {max(0, CHILD_AT - exp)} 回で子供に成長！"
    elif stage == "child":
        return f"  あと {max(0, ADULT_AT - exp)} 回で大人に！"
    elif stage == "adult":
        left = max(0, REPRODUCE_AT - exp)
        next_q = min(100, q + 20 - state.get("sick_count", 0) * 5)
        return f"  あと {left} 回で産卵！  次世代予測: {quality_stars(next_q)} Q={int(next_q)}"
    elif stage == "sick":
        return f"  病気中... 使い続けて回復しよう！"
    elif stage == "dead":
        return f"  次のツール使用で第{state['generation']+1}世代が始まります..."
    return ""

def _watch_render(state, frame):
    from datetime import datetime as dt
    stage = state["stage"]
    q     = float(state["quality"])
    gen   = state["generation"]
    exp   = state["experience"]

    art = (ART2 if frame else ART).get(stage, ART["egg"])

    print()
    print("  ╔═══════════════════════════════════╗")
    print("  ║        🌟  Buddy  Watch  🌟         ║")
    print("  ╚═══════════════════════════════════╝")

    for line in art.split("\n"):
        print("  " + line)

    print()
    print(f"  Name     : {state['pet_name']}")
    print(f"  Gen      : 第{gen}世代   Quality: {quality_stars(q)} {quality_label(q)} (Q={int(q)})")
    print(f"  Stage    : {stage.upper()}   EXP: {exp}")

    if stage not in ("egg", "dead"):
        print()
        print(f"  Hunger    {bar(state['hunger'])}")
        print(f"  Happiness {bar(state['happiness'])}")
        print(f"  Health    {bar(state['health'])}")

    # ステータス
    stats = state.get("stats", {})
    if stats:
        print()
        for key in STAT_KEYS:
            val = stats.get(key, 0)
            filled = round(val / STAT_MAX * 10)
            b = "█" * filled + "░" * (10 - filled)
            print(f"  {STAT_LABELS[key]} [{b}] {val:2d}")

    # 技
    moves = state.get("moves", [None]*4)
    learned = [m for m in moves if m]
    if learned:
        print()
        nums = ["①","②","③","④"]
        for i, move in enumerate(moves[:4]):
            if move:
                print(f"  {nums[i]} {move}")

    print()
    print(_status_message(state))
    print()
    print(f"  ── {dt.now().strftime('%H:%M:%S')} ── Ctrl+C で終了 ──")

def _watch_loop():
    import time
    frame      = 0
    last_mtime = 0.0
    disp_state = None

    while True:
        try:
            mtime = os.path.getmtime(STATE_FILE)
        except FileNotFoundError:
            mtime = 0.0

        if mtime != last_mtime:
            raw        = load() or fresh(get_user_id())
            disp_state = apply_evolve(apply_decay(raw))
            last_mtime = mtime

        if disp_state:
            os.system("clear")
            _watch_render(disp_state, frame)

        frame = 1 - frame
        time.sleep(0.5)

if __name__ == "__main__":
    main()
