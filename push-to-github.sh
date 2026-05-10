#!/bin/bash
# Скрипт для отправки проекта на GitHub
# Запустите: bash push-to-github.sh

set -e

# —— Настройки ——
REPO_NAME="journal-keeper"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  Приватный мультимодальный дневник → GitHub         ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Проверяем gh CLI
if ! command -v gh &>/dev/null; then
    echo "❌ gh CLI не установлен."
    echo "   Установите: https://cli.github.com/"
    exit 1
fi

# Проверяем авторизацию
if ! gh auth status &>/dev/null; then
    echo "⚠️  Вы не авторизованы на GitHub."
    echo ""
    echo "Варианты:"
    echo "  1. Интерактивная авторизация:"
    echo "     gh auth login"
    echo ""
    echo "  2. Через токен (Personal Access Token):"
    echo "     echo 'YOUR_GITHUB_TOKEN' | gh auth login --with-token"
    echo ""
    echo "Создайте токен: https://github.com/settings/tokens/new"
    echo "Необходимые права: repo, delete_repo"
    exit 1
fi

# Получаем имя пользователя
GH_USER=$(gh api user --jq '.login' 2>/dev/null)
if [ -z "$GH_USER" ]; then
    echo "❌ Не удалось получить имя пользователя GitHub."
    exit 1
fi

echo "✅ Авторизован как: $GH_USER"
echo ""

# Создаём репозиторий
echo "📦 Создаю репозиторий $REPO_NAME..."
gh repo create "$REPO_NAME" \
    --public \
    --description "Private Multimodal Diary with Local LLM and OCR — локальный дневник с LLM-редактором, OCR и полнотекстовым поиском" \
    --source "$REPO_DIR" \
    --push \
    || {
        # Если репозиторий уже существует — просто добавляем remote
        echo "⚠️  Репозиторий уже существует. Добавляю remote..."
        cd "$REPO_DIR"
        git remote remove origin 2>/dev/null || true
        git remote add origin "https://github.com/$GH_USER/$REPO_NAME.git"
        git push -u origin main
    }

echo ""
echo "🎉 Готово! Репозиторий доступен:"
echo "   https://github.com/$GH_USER/$REPO_NAME"
