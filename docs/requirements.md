# Claude Code Server Sync - Requirements

## 📋 Prerequisites

### SSH Access
- [ ] SSH key configured for server
- [ ] SSH alias `eywa1` (or custom) added to `~/.ssh/config`
- [ ] Test: `ssh eywa1 "echo OK"` works

### System
- [ ] Python 3.7+
- [ ] rsync installed (default on macOS/Linux)
- [ ] Claude Code installed on both machines

## 🎯 Core Features

### Discovery & Setup
- [ ] `scan server` - List all projects on server
- [ ] `scan local` - List all projects on macOS
- [ ] `setup` - Interactive wizard to match projects
- [ ] Auto-detects existing projects

### Sync Operations
- [ ] `pull` - Server → macOS with path transformation
- [ ] `push` - macOS → Server with manual approval
- [ ] `list` - Show configured project mappings
- [ ] Path transformation reversibility (roundtrip safe)

### Path Mapping
- [ ] Ubuntu `/var/tmp/*` → macOS `/private/var/folders/.../T/*`
- [ ] Project names: `-var-tmp-*` → `-private-var-folders-...-T-*`
- [ ] Repository paths transformation
- [ ] Configurable path patterns

### Security
- [ ] Mac = orchestrator (server never pushes)
- [ ] Manual approval for push operations
- [ ] Read-only mode for sensitive projects
- [ ] Config.json excluded from git

### Automation
- [ ] LaunchAgent plist for scheduled sync
- [ ] `sync-all.sh` helper script
- [ ] Configurable interval (default 5min)
- [ ] Logging to file

## 🔧 Setup Checklist

### First-Time Setup
1. [ ] Clone repository
2. [ ] Verify SSH access: `ssh eywa1 ls ~/.claude/projects`
3. [ ] Run: `python3 src/sync.py setup`
4. [ ] Follow interactive wizard
5. [ ] Test: `python3 src/sync.py list`

### Configure Project Mapping
1. [ ] Scan server: `python3 src/sync.py scan server`
2. [ ] Scan local: `python3 src/sync.py scan local`
3. [ ] Match projects interactively during setup
4. [ ] Set sync mode per project (server-to-mac/bidirectional)

### First Sync
1. [ ] List configured: `python3 src/sync.py list`
2. [ ] Pull test project: `python3 src/sync.py pull <name>`
3. [ ] Verify files in `~/.claude/projects/<macos-dir>/`
4. [ ] Check paths are transformed correctly

### Automation (Optional)
1. [ ] Copy plist to `~/Library/LaunchAgents/`
2. [ ] Edit paths in plist
3. [ ] Load: `launchctl load ~/Library/LaunchAgents/com.claude.sync.plist`
4. [ ] Verify: `launchctl list | grep claude`

## 🐛 Troubleshooting

### SSH Issues
- [ ] Check `~/.ssh/config` has host configured
- [ ] Test: `ssh -v eywa1` for verbose output
- [ ] Verify key permissions: `chmod 600 ~/.ssh/id_rsa`

### Path Transformation
- [ ] Verify `temp_escaped` paths match actual project names
- [ ] List real names: `ls ~/.claude/projects/`
- [ ] Update `examples/config.example.json` if needed

### Sync Failures
- [ ] Check logs: `~/logs/claude-sync.log`
- [ ] Verify rsync installed: `which rsync`
- [ ] Test manual rsync: `rsync -av eywa1:~/.claude/projects/ /tmp/test/`

## ✅ Acceptance Criteria

### Functional
- [ ] Can scan both server and local projects
- [ ] Interactive setup creates valid config.json
- [ ] Pull operation transforms paths correctly
- [ ] Push requires manual confirmation
- [ ] List shows all configured projects

### Quality
- [ ] No hardcoded paths in code
- [ ] Config example covers common scenarios
- [ ] Error messages are clear and actionable
- [ ] Documentation is complete

### Security
- [ ] config.json is gitignored
- [ ] SSH key never stored in code
- [ ] Server cannot initiate push to mac
- [ ] Confirmation required for destructive operations
