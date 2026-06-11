# Database Migrations Guide

This guide explains how to work with database migrations in Syft Space. Whether you're new to migrations or just new to this project, this document will help you get started.

## What Are Migrations?

**Migrations are version control for your database schema.** Just like git tracks changes to your code, migrations track changes to your database structure (tables, columns, indexes, etc.).

When you:
- Add a new table → Create a migration
- Add/remove a column → Create a migration
- Change a column type → Create a migration

Migrations ensure everyone's database stays in sync and upgrades happen safely.

---

## Quick Start

All migration commands use [just](https://github.com/casey/just), a simple command runner. Run commands from the `backend/` directory.

```bash
cd backend/

# See all available commands
just

# Check your current database state
just status
```

### Most Common Commands

| What you want to do | Command |
|---------------------|---------|
| See current state | `just status` |
| Apply all migrations | `just upgrade` |
| Create a new migration | `just generate "description"` |
| Undo last migration | `just downgrade` |
| Undo ALL migrations | `just downgrade-all` |
| Delete database (clean slate) | `just wipe` |
| Delete + rebuild from migrations | `just rebuild` |

---

## Developer Workflows

### Scenario 1: You're Adding a New Feature with Database Changes

Let's say you're adding a "user_preferences" table.

**Step 1: Create your model**

```python
# syft_space/components/preferences/entities.py
from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4

class UserPreference(SQLModel, table=True):
    __tablename__ = "user_preferences"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(...)
    theme: str = Field(default="light")
```

**Step 2: Register your model** (Important!)

Add your model to `syft_space/alembic/env.py`:

```python
# Add with other imports at the top
from syft_space.components.preferences.entities import UserPreference  # noqa: F401
```

> **Why?** Alembic needs to "see" your model to detect changes. If you skip this, your migration will be empty!

**Step 3: Generate the migration**

```bash
just generate "add user preferences table"
```

This creates a new file in `syft_space/alembic/versions/` like:
```
abc123def456_add_user_preferences_table.py
```

**Step 4: Review the generated migration**

Open the file and check that it looks correct. The `upgrade()` function should create your table, and `downgrade()` should drop it.

**Step 5: Test it**

```bash
just upgrade    # Apply the migration
just status     # Verify it worked
```

**Step 6: Commit everything together**

```bash
git add .
git commit -m "feat: add user preferences"
```

---

### Scenario 2: You're Modifying an Existing Table

Adding a column to an existing table requires more care.

**Example: Adding an `email_verified` column to users**

**Step 1: Update your model**

```python
class User(SQLModel, table=True):
    # ... existing fields ...
    email_verified: bool = Field(default=False)  # New field
```

**Step 2: Generate migration**

```bash
just generate "add email_verified to users"
```

**Step 3: Review carefully!**

For existing tables with data, you may need to edit the migration:

```python
def upgrade() -> None:
    # Add as nullable first (so existing rows don't break)
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=True))

    # Set default for existing rows
    op.execute("UPDATE users SET email_verified = false")

    # Now make it non-nullable if needed
    op.alter_column('users', 'email_verified', nullable=False)
```

---

### Scenario 3: Your PR Has a Migration Conflict

This happens when another PR with migrations merged before yours. It's like a git merge conflict, but for migrations.

**You'll see this error:**
```
ERROR: Multiple heads detected!
```

**How to fix it:**

```bash
# 1. Get the latest changes
git pull origin main

# 2. Merge the migration branches
just merge-heads

# 3. Commit the merge migration
git add .
git commit -m "chore: merge migrations"
git push
```

That's it! The `merge-heads` command creates a "merge migration" that combines both branches.

---

### Scenario 4: Your Local Database is Messed Up

Sometimes your local DB gets out of sync. Here's how to fix it:

**Option A: Just re-sync (no data loss)**

```bash
just upgrade
```

If you're just behind on migrations, this catches you up.

**Option B: Reset to the last stable release**

```bash
just reset-to-release
```

Drops your database and rebuilds it to the last released version. Good for getting back to a known-good state.

**Option C: Rebuild from current migrations**

```bash
just rebuild
```

Drops everything and applies all current migrations. You'll lose all local data.

**Option D: Complete wipe (starting from scratch)**

```bash
just wipe
```

Just deletes the database file. Use this when migration files don't exist or are broken. Run `just upgrade` afterward to recreate.

---

## Command Reference

### Everyday Commands

```bash
just status          # Where am I? Show current migration + release info
just upgrade         # Apply all pending migrations
just downgrade       # Undo the last migration
just downgrade-all   # Undo ALL migrations (empty database)
just history         # Show all migrations in order
```

### Creating Migrations

```bash
just generate "description"    # Create a new migration
```

> Always use a clear description like "add user roles table" or "add email to orders"

### Fixing Problems

```bash
just merge-heads       # Fix "multiple heads" conflict
just reset-to-release  # Reset DB to last released version
just rebuild           # Drop DB + apply all migrations
just wipe              # Just delete DB (when migrations are broken)
just check             # Verify migration chain is healthy
```

### Release Commands (for maintainers)

```bash
just validate-release      # Run all validation tests
just mark-release 1.2.0    # Mark current state as a release
```

---

## How Development vs Production Differs

| | Development (`DEBUG=true`) | Production (`DEBUG=false`) |
|---|---|---|
| Migration fails | Falls back to creating tables directly | **App crashes** (intentional!) |
| New tables | Auto-created even without migration | Requires migration |
| Safety | Convenient for iteration | Strict for data integrity |

**Why does production crash?** Because silently ignoring migration failures can corrupt data. It's better to fail loudly and fix the issue.

---

## Project Structure

```
backend/
├── justfile                          # All the commands you run
└── syft_space/
    ├── alembic.ini                   # Alembic configuration
    └── alembic/
        ├── env.py                    # Entity imports go here!
        ├── script.py.mako            # Template for new migrations
        ├── RELEASE_MARKER            # Tracks last released version
        └── versions/                 # Migration files live here
            ├── 640a7f9a94e1_initial_schema.py
            └── b80a47b5e5b7_add_ingestion_jobs_and_marketplaces.py
```

### Key Files

| File | What it does |
|------|--------------|
| `justfile` | Defines all the `just` commands |
| `alembic/env.py` | **Register new models here!** |
| `alembic/versions/*.py` | Individual migration files |
| `alembic/RELEASE_MARKER` | Tracks the last released migration |

---

## Troubleshooting

### "No changes detected" when generating migration

Your model isn't being seen by Alembic. Check:

1. Did you add `table=True` to your model?
   ```python
   class MyModel(SQLModel, table=True):  # <-- This is required!
   ```

2. Did you import it in `alembic/env.py`?
   ```python
   from syft_space.components.myfeature.entities import MyModel  # noqa: F401
   ```

3. Are you in the `backend/` directory?

### "Table already exists" error

Your database has tables that the migration is trying to create. This usually means the DB was created outside of migrations.

```bash
# Tell Alembic "the DB is already at this state"
uv run alembic -c syft_space/alembic.ini stamp head
```

### "Multiple heads detected"

Two migrations branched from the same point. See [Scenario 3](#scenario-3-your-pr-has-a-migration-conflict) above.

### "Target database is not up to date"

You have unapplied migrations:

```bash
just upgrade
```

### App won't start in production

With `DEBUG=false`, the app crashes if migrations fail. Check:

```bash
just status    # See current state
just history   # See all migrations
just upgrade   # Try to apply manually and see the error
```

---

## Best Practices

### Do

- **Review generated migrations** - Autogenerate isn't perfect
- **Test locally first** - Run `just upgrade` and `just downgrade` before pushing
- **Use clear descriptions** - `"add user roles"` not `"update"`
- **Commit migrations with code** - Keep them in sync
- **Handle existing data** - Think about what happens to current rows

### Don't

- **Don't edit applied migrations** - Create a new one instead
- **Don't delete migration files** - They're history
- **Don't forget `env.py`** - New models must be imported
- **Don't skip review** - Always check what autogenerate created

---

## For Release Managers

### Before a Release

```bash
# 1. Ensure clean migration chain
just check

# 2. Run full validation (tests fresh install, upgrade, downgrade)
just validate-release

# 3. If all passes, tag the release
git tag v1.2.0

# 4. Update the release marker
just mark-release 1.2.0
```

### What RELEASE_MARKER Does

This file tracks the last "known good" migration. It enables:
- `just reset-to-release` - Developers can reset to stable state
- `just validate-release` - Tests upgrade path from last release
- Future squashing of migrations if needed

---

## Current Database Schema

| Table | Purpose |
|-------|---------|
| `tenants` | Multi-tenancy support |
| `datasets` | Dataset configurations |
| `models` | Model configurations |
| `endpoints` | API endpoints |
| `policies` | Endpoint rate limiting and guards |
| `provisioner_states` | Dataset provisioner tracking |
| `ingestion_jobs` | File ingestion job tracking |
| `marketplaces` | External marketplace configs |

All tables use UUID primary keys and include `created_at`/`updated_at` timestamps.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `true` | Dev mode (lenient) vs prod mode (strict) |
| `SQLITE_DB_PATH` | `~/.syft-space/app.db` | Database file location |
| `RESET_DB` | `false` | Drop all tables on startup (dangerous!) |

---

## Need Help?

- Run `just` to see all available commands
- Run `just status` to see where you are
- Check the migration files in `syft_space/alembic/versions/` for examples
- Ask in the team chat if you're stuck!
