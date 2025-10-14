# Claude Code Server Sync

Быстрый способ держать `.jsonl` сессии Claude Code синхронизированными между macOS и сервером `eywa1`. Вся логика строится на `rsync`, а пути внутри файлов приводятся к нужному формату через простые правила замены.

---

## ⚡️ Quick Start
- Проверь SSH алиас (в примере — `eywa1`):

  ```bash
  ssh eywa1 "echo ok"
  ```

- Создай личный конфиг:

  ```bash
  cp examples/config.example.json config.json
  ```

- Отредактируй `config.json` — пропиши реальные пути и проекты.
- Пробный прогон, чтобы подтянуть один проект:

  ```bash
  python3 src/sync.py pull vibe-orchestrator
  ```

---

## 🗂 Структура конфига

```json
{
  "ssh_alias": "eywa1",
  "paths": {
    "macos_root": "/Users/user/.claude/projects",
    "server_root": "/home/user/.claude/projects"
  },
  "rewrite_rules": [
    { "server": "/home/user/.claude/projects", "mac": "/Users/user/.claude/projects" },
    { "server": "-var-tmp", "mac": "-private-var-folders-dw-...-T" },
    { "server": "-home-user---Repositories-", "mac": "-Users-user---Repositories-" }
  ],
  "projects": [
    {
      "name": "vibe-orchestrator",
      "server_dir": "-var-tmp-vibe-kanban-worktrees-vk-2bd7-run-orch-n",
      "macos_dir": "-private-var-folders-dw-...-vk-2bd7-run-orch-n",
      "mode": "pull"
    },
    {
      "name": "memory-monorepo",
      "server_dir": "-home-user---Repositories-memory-monorepo",
      "macos_dir": "-Users-user---Repositories-LLMs-memory--developerisnow",
      "mode": "both"
    }
  ]
}
```

- `mode: pull` — тянем только с сервера.
- `mode: push` — пушим только руками с мака.
- `mode: both` — двунаправленный режим (push все равно вручную).
- `rewrite_rules` — строки, которые нужно заменить в `.jsonl`. Чем длиннее совпадение, тем раньше оно применяется (правила сортируются автоматически).

---

## 🧰 Команды

```bash
# Посмотреть список проектов и пути
python3 src/sync.py list

# Сервер → macOS
python3 src/sync.py pull vibe-orchestrator

# macOS → сервер (спросит подтверждение)
python3 src/sync.py push memory-monorepo

# Пройтись по всем pull/both проектам (используется планировщиком)
python3 src/sync.py sync-all

# Любую команду можно запустить с dry-run (прокинет флаг в rsync)
python3 src/sync.py --dry-run pull vibe-orchestrator
```

---

## ⏱ Планировщик (macOS LaunchAgent)

1. Сделай скрипт исполняемым:

   ```bash
   chmod +x scripts/sync-all.sh
   ```

2. Создай `~/Library/LaunchAgents/com.claude.sync.plist` со следующим содержимым:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.claude.sync</string>

       <key>ProgramArguments</key>
       <array>
           <string>/Users/user/__Repositories/LLMs-claude-code-exporter/scripts/claude-code-sync/scripts/sync-all.sh</string>
       </array>

       <key>StartInterval</key>
       <integer>300</integer> <!-- каждые 5 минут -->

       <key>RunAtLoad</key>
       <true/>

       <key>StandardOutPath</key>
       <string>/Users/user/__Repositories/LLMs-claude-code-exporter/logs/claude-sync.log</string>

       <key>StandardErrorPath</key>
       <string>/Users/user/__Repositories/LLMs-claude-code-exporter/logs/claude-sync.error.log</string>
   </dict>
   </plist>
   ```

3. Подними агент:

   ```bash
   launchctl load ~/Library/LaunchAgents/com.claude.sync.plist
   launchctl list | grep claude.sync
   ```

4. Логи:

   ```bash
   tail -f ~/logs/claude-sync.log
   ```

Агент гоняет `sync-all` — он подтянет все `pull/both` проекты. `push` по Cron не запускаем ради безопасности.

---

## 🔄 Как переписываются пути

| Что было (Ubuntu)                         | Что станет (macOS)                                        |
|------------------------------------------|-----------------------------------------------------------|
| `/home/user/.claude/projects/...`        | `/Users/user/.claude/projects/...`                        |
| `/var/tmp/vibe-kanban-worktrees-...`     | `/private/var/folders/dw/.../T/vibe-kanban-worktrees-...` |
| `-home-user---Repositories-`             | `-Users-user---Repositories-`                             |

Правила можно расширять — просто добавляй новые элементы в `rewrite_rules`. Они применяются и при pull, и при push (во втором случае направления меняются на обратные).

---

## 🛠 Troubleshooting

- **rsync говорит “command not found”** — установи `brew install rsync` (на macOS штатный уже есть).
- **SSH не цепляется** — проверь `~/.ssh/config`, права на ключ и алиас.
- **Файлы не переписались** — удостоверься, что правило замены точно совпадает со строкой (можно поискать `rg "var-tmp"` в `.jsonl`).
- **Нужно проверить, что поменяется, но не писать** — используй `--dry-run`.

---

## 🔐 Модель работы
- Все команды выполняет Mac.
- Сервер никаких ключей от мака не имеет.
- Push всегда требует ручного действия (или `--yes`, если понимаешь, что делаешь).

---

## 📁 Содержимое репозитория
- `src/sync.py` — основной CLI.
- `scripts/sync-all.sh` — обёртка для LaunchAgent.
- `examples/config.example.json` — шаблон конфига.
- `docs/` — история и заметки.
- `files/` — примеры выгрузок (не используются кодом).
