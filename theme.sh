#!/bin/bash
CONFIG="$HOME/.config/ghostty/config"
SAVE_FILE="$HOME/.claude/buddy/.theme-save"

set_sakura() {
    mkdir -p "$(dirname "$CONFIG")"
    touch "$CONFIG"
    # Save current theme line (empty string if none set)
    grep -E '^theme[[:space:]]*=' "$CONFIG" | head -1 > "$SAVE_FILE" 2>/dev/null || echo "" > "$SAVE_FILE"
    # Replace theme with Sakura
    sed -i '' '/^theme[[:space:]]*=/d' "$CONFIG"
    echo "theme = Sakura" >> "$CONFIG"
}

restore_theme() {
    [ -f "$SAVE_FILE" ] || return
    [ -f "$CONFIG" ] || return
    saved=$(cat "$SAVE_FILE")
    sed -i '' '/^theme[[:space:]]*=/d' "$CONFIG"
    [ -n "$saved" ] && echo "$saved" >> "$CONFIG"
    rm -f "$SAVE_FILE"
}

case "$1" in
    set) set_sakura ;;
    restore) restore_theme ;;
esac
