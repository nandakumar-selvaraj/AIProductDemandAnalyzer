# Rollback

Root-owned release controller accepts only bounded JSON, approved repositories/digests, full SHA, deploy/rollback and explicit schema compatibility review. No caller Compose flags/shell. Host flock plus workflow concurrency serialize releases.

Successful active.json/active.env and previous.json are private under `/var/lib/demand/releases`; history records timestamp/SHA/result without secrets. New releases pull digests, back up existing data, stop old API writes, migrate, compare Alembic heads, wait container readiness and test API/SPA over trusted HTTPS. DB digest changes require separate upgrade approval.

Application health failure after successful backward-compatible migration restores/rechecks prior images and records result; workflow still fails for investigation. Migration failure stops with manual recovery required because partial schema may be incompatible. First release has no prior application. No automatic migration downgrade or reset.

After compatibility approval, manual rollback from operator root session (documentation only):

```sh
python3 - <<'PY' | /usr/local/sbin/demand-release
import json
from pathlib import Path
print(json.dumps({'action': 'rollback', 'schema_backward_compatible': True,
                  'release': json.loads(Path('/var/lib/demand/releases/previous.json').read_text())}))
PY
```

Exact previous manifest is required; rollback never migrates backwards. Verify public browser behavior afterward. Retain previous images in registry. A checkbox does not prove schema compatibility: use additive migrations first and retire old readers/writers later. Destructive schema changes need migration-specific forward-fix/backup/restore review and approval; database restore can lose data to chosen RPO.
