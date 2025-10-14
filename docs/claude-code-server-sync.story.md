# Goal
Нужно сделать синхронизацию кода между claude-code-server и claude-code-macos, которая раз в 5 минут просто синхронизирует файлы `*.jsonl` между сервером и маком на основе config.json.

# Task description
- [ ] изменение путей в файлах `*.jsonl` на основе значений конфига
- [ ] `config.json` сохраняется в корень проекта и указывает какие сервера между собой синхронизировать и соответствия названий проектов.
  - [ ] автоматическая подгрузка вариантов списка чтобы можно было самому выставлять match, или если если нет такого соответствия на macos то задавать создать папку вручную
  - [ ] задавать match
  - [ ] создавать вручную если нет match, вписать просто

# Prototype 1 with examples
- [x] У тебя есть папка моего macos  `/Users/user/.claude/projects` - `scripts/claude-code-sync/docs/20251014-0554-claude-home-directories-macos.md`
- [x] У тебя есть доступ `ssh eywa1` к моему серверу через alias by ssh key где стоит тоже `/home/user/.claude/projects` - `scripts/claude-code-sync/docs/20251014-0554-claude-home-directories-ubuntu-eywa1.md`
- [ ] самое простое чтобы сделать за полчаса и надежное мне кажется(Если видишь лучше предлагай!) - rsync на основе конфигу по расписанию plist на мое macos, синхронизация в одну или обе стороны
  - [ ] rsync функционал
  - [ ] plist scheduler
  - [ ] синхронизация (сразу оговорюсь я хочу чтобы с сервера на мой мак синхронизировалось все, ну конечно на основе того что я задам, а на сервер только что я укажу так как сам понимаешь вопрос уязвимости сервера и приватные данные хочу только "по кнопке"(по ручному действию апрувить что синхронизировать))
    - стоит пояснить варианты зачем мне это надо? Ну вот мне срочно надо продолжить локальную сессию с сервера и наоборот
    - мне просто приспичило на macos взять серверную сессию посомтреть внимательно у меня есть команда `cprompts` (cc-exporter) который "распаршивает" эти `.jsonl` в .json, .md и mermaid, мне удобно и мне банально удобно понимать и изучать это на моем macos в ide/obsidian.

Пример конкретный
- [ ] взять через rsync `/home/user/.claude/projects/-var-tmp-vibe-kanban-worktrees-vk-2bd7-run-orch-n` скопировать файл в `/Users/user/.claude/projects/-private-var-folders-dw-d6symylx7sz0b30vzcrfkdg80000gq-T-vibe-kanban-worktrees-vk-2bd7-run-orch-n` 
  - [ ] и внутри файла там есть куча путей их обязательно поменять в файлах и учитывать разницу
  - получается, наверное есть типовые различия надо как-то стандартизировать
    - `$PROGRAMDATA`  macos:ubuntu(eywa1) `/Users/user/.claude/projects/:/home/user/.claude/projects/`
    - `$VIBE_KANBAN_WORKTREES` macos:ubuntu(eywa1) `-var-tmp-vibe-kanban-worktrees-$PROJECT:-private-var-folders-dw-d6symylx7sz0b30vzcrfkdg80000gq-T-vibe-kanban-worktrees-$PROJECT`
    - `$OTHER_STANDARD_PROJECTS_PATHS` macos:ubuntu(eywa1) `-Users-user---Repositories-LLMs-memory--developerisnow:-home-user---Repositories-memory-monorepo`
- [ ] вот я короче незнаю как через `rsync` (он помощнее `scp`) и сделал через `scp` по-быстрому как знаю
```bash
claude-code-sync (main) ❯ scp -r eywa1:/home/user/.claude/projects/-var-tmp-vibe-kanban-worktrees-vk-2bd7-run-orch-n ./files
6ec30b85-2eb5-4 100%  783KB   1.1MB/s   00:00    
a6025db0-9af6-4 100% 1143KB   3.0MB/s   00:00    
37d01b18-80cc-4 100% 1515KB   4.0MB/s   00:00    
508d4a7a-11da-4 100%  837KB   2.4MB/s   00:00    
93860809-c700-4 100%  711KB   2.6MB/s   00:00    
27ff4316-2157-4 100%  788KB   2.2MB/s   00:00    
62424ed8-5da9-4 100%  666KB   2.5MB/s   00:00    
babb5316-bcd6-4 100%  826KB   2.3MB/s   00:00    
ae26684d-dfce-4 100%  635KB   2.3MB/s   00:00    
0c30e1c9-b2c8-4 100% 3005KB   5.3MB/s   00:00    
c2c15016-23f3-4 100%  798KB   2.3MB/s   00:00    
4ca2bcf7-833d-4 100% 1243KB   3.5MB/s   00:00    
f013236f-3ab0-4 100%  579KB   2.1MB/s   00:00    
5a764708-0f16-4 100%  831KB   2.3MB/s   00:00    
28478227-1bb4-4 100%  873KB   2.4MB/s   00:00    
70a098a9-47ef-4 100%  239KB   1.4MB/s   00:00    
ba42cae7-d19a-4 100%  252KB   1.4MB/s   00:00    
53413b25-2598-4 100% 1709KB   3.5MB/s   00:00    
10f6168e-ac66-4 100%  432KB   1.6MB/s   00:00    
claude-code-sync (main) ❯                   
```