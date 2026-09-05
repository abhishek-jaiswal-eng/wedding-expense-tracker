# 💍 Wedding Expense Tracker

A private, shared Streamlit app for the Groom and Bride sides of a wedding
to track planned vs. actual spend, who paid for what, and who owes what —
with separate points of view for each side, an Admin panel, and
controllable cross-side visibility.

---

## 1. Overview

This app lets both families:

- Record expenses with a clear distinction between:
  - **Expense For** — whose expense it is (Groom / Bride / Shared)
  - **Entered By** — which side recorded it (Groom / Bride)
  - **Purchased For** — who the item/service was actually for (Groom / Bride / Both)
  - **Paid By** — who actually paid the money (Groom / Bride / Shared / Other)
- See a **Groom POV**, **Bride POV**, and **Overall** dashboard
- Track planned vs. actual amounts, payments made, and pending balances
- See a **settlement/contribution summary** (who effectively paid for whom)
- Control, as an **Admin**, whether one side can see the other side's entries
- Export data to CSV (only the data they're allowed to see — Admin can
  export everything)

All data is stored locally in a SQLite database file
(`wedding_expenses.db`) that lives alongside the app.

---

## 2. Requirements

- Python 3.9+
- pip
- SQLite (bundled with Python — no separate install needed)
- Streamlit (installed via `requirements.txt`)

---

## 3. Project Structure

```
.
├── app.py                          # Streamlit UI — pages, navigation, forms
├── auth.py                         # Passphrase authentication (Groom/Bride/Admin)
├── config.py                       # Constants: dropdown options, roles, settings keys
├── database.py                     # SQLite schema, migrations, CRUD, visibility-aware queries
├── permissions.py                  # Visibility rules — who can see whose expenses
├── requirements.txt                # Python dependencies
├── .gitignore                      # Excludes secrets.toml and the database file
└── .streamlit/
    └── secrets.toml.example        # Placeholder config — copy to secrets.toml
```

**Why separate files?** Database logic never imports Streamlit, so it can
be tested independently of the UI. `permissions.py` is the single place
that decides "who can see whose data," which every page routes through —
this keeps the visibility rules consistent and auditable in one spot
instead of scattered across pages.

---

## 4. Local Installation

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
python -m pip install -r requirements.txt
```

On **Windows** (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

> Avoid `sudo pip install ...` — modern Ubuntu/Debian systems mark the
> system Python as "externally managed" and will refuse global installs
> (or worse, silently affect other tools). Always use a virtual
> environment as shown above.

---

## 5. Configuration (Passphrases)

The app uses **three separate passphrases** — one each for Groom, Bride,
and Admin. None of them are hardcoded in the source code.

Required configuration keys:

```
GROOM_PASSPHRASE
BRIDE_PASSPHRASE
ADMIN_PASSPHRASE
```

### Option A — Local environment variables

```bash
export GROOM_PASSPHRASE="your-groom-passphrase"
export BRIDE_PASSPHRASE="your-bride-passphrase"
export ADMIN_PASSPHRASE="your-admin-passphrase"
```

(On Windows PowerShell: `$env:GROOM_PASSPHRASE = "..."`, etc.)

### Option B — Streamlit secrets (recommended, also required for Streamlit Cloud)

1. Copy the example file:

   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

2. Edit `.streamlit/secrets.toml` and replace the placeholders:

   ```toml
   GROOM_PASSPHRASE = "your-groom-passphrase"
   BRIDE_PASSPHRASE = "your-bride-passphrase"
   ADMIN_PASSPHRASE = "your-admin-passphrase"
   ```

`.streamlit/secrets.toml` is already listed in `.gitignore` — **never
commit your real passphrases**. Only `secrets.toml.example` (with
placeholder values) should ever go into version control.

The app checks `st.secrets` first, then falls back to environment
variables, so either method (or both) works.

---

## 6. Running Locally

```bash
streamlit run app.py
```

Then open the URL Streamlit prints (typically `http://localhost:8501`).
Log in with the Groom, Bride, or Admin passphrase depending on who's
using it.

---

## 7. Database

- Data is stored in `wedding_expenses.db` (SQLite), created automatically
  next to `app.py` the first time the app runs.
- `init_db()` in `database.py` runs on every app start. It:
  - Creates the schema from scratch if the database is new.
  - **Migrates** an older schema in place if it detects one (see below),
    without deleting any existing rows.
  - Adds indexes on `entered_by`, `expense_for`, `category`,
    `expense_date`, and `status` for faster filtering.
  - Ensures a `settings` table exists with default visibility settings
    (both sides private by default).

### Migration notes

If you're upgrading from an earlier version of this app where the
`expense_type` column actually meant "whose expense it is" (Groom/Bride),
the migration:

1. Renames that column to `expense_for` (its real meaning).
2. Adds new `entered_by`, `purchased_for`, and a redefined `expense_type`
   (now used for the specific item/service, e.g. "Hotel", "Photography").
3. Backfills `entered_by` and `purchased_for` from the existing
   `expense_for` value for old rows, so nothing is left blank.

This runs automatically and is safe to run repeatedly — no manual steps,
and no existing expenses are lost.

---

## 8. User Roles & Permissions

| Role  | Can enter expenses as | Can view | Can edit/delete |
|-------|------------------------|----------|------------------|
| Groom | Groom                  | Own side always; Bride's side only if Admin enables it | Only expenses entered by Groom |
| Bride | Bride                  | Own side always; Groom's side only if Admin enables it | Only expenses entered by Bride |
| Admin | Any side (selectable)  | Everything, always | Everything |

Note the difference between **Expense For** and **Entered By**: a Bride
user can absolutely record an expense *for* the Groom (e.g. she bought
his sherwani) — what's fixed to her login is *who entered it*, not whose
expense it is.

---

## 9. Visibility Control

By default, Groom and Bride can each only see expenses **their own side
entered** — Overall/Groom POV/Bride POV views only show what's fully
visible to them.

Admin can independently toggle, from **⚙️ Admin Panel → Visibility
Settings**:

- Groom can see Bride expenses: ON/OFF
- Bride can see Groom expenses: ON/OFF

**This is enforced in the database query itself**, not just hidden in the
UI — `permissions.py` computes the allowed `entered_by` values for the
current role, and every read (dashboard, list, summary, export) passes
that into a SQL `WHERE entered_by IN (...)` filter. A user cannot see
rows outside their permission by changing pages, filters, or navigating
directly, because the disallowed rows are never fetched from the
database in the first place.

Editing/deleting is a separate, stricter rule: regardless of visibility
settings, Groom and Bride can only edit/delete expenses **they
themselves entered** — visibility settings control *viewing* the other
side's data, not modifying it.

---

## 10. Deployment (Streamlit Community Cloud)

1. Push this repository to GitHub (make sure `.streamlit/secrets.toml`
   is **not** committed — check `.gitignore`).
2. On [share.streamlit.io](https://share.streamlit.io), create a new app
   pointing at `app.py` in this repo.
3. In the app's **Settings → Secrets**, paste:

   ```toml
   GROOM_PASSPHRASE = "your-groom-passphrase"
   BRIDE_PASSPHRASE = "your-bride-passphrase"
   ADMIN_PASSPHRASE = "your-admin-passphrase"
   ```

4. Deploy.

### ⚠️ Important: SQLite persistence on Streamlit Cloud

Streamlit Community Cloud's filesystem is **ephemeral** — the app's
container can be restarted or redeployed (e.g. after inactivity or a
new push), which will **reset `wedding_expenses.db` and lose all
data**. SQLite works well for local use or a single always-on server,
but is not a safe choice for long-term shared use on Streamlit Cloud.

For real production/shared use across the full wedding-planning period,
consider:

- Migrating to a hosted **PostgreSQL** database (e.g. via Supabase,
  Neon, or Railway) and swapping out `database.py`'s connection logic
  accordingly, or
- Regularly backing up `wedding_expenses.db` (see below) if you choose
  to stick with SQLite and accept the risk.

---

## 11. Backup

To back up your data, simply copy the SQLite file:

```bash
cp wedding_expenses.db wedding_expenses_backup_$(date +%Y%m%d).db
```

Do this regularly (e.g. weekly, or before any deployment/redeploy) if
running on a platform with an ephemeral filesystem. The Admin Panel's
**Export Complete Dataset (CSV)** button is also a good lightweight
backup you can save to Google Drive/email after each session.

---

## 12. Loading States & Duplicate Submission Protection

Every save/update/delete/login/settings action shows a spinner
(e.g. "💾 Saving...") while it runs, and:

- Add/Update forms compute a signature of the submitted values and
  silently ignore an identical resubmission within a few seconds,
  so double-clicking "Save" can't create duplicate rows.
- Delete requires an explicit two-step confirmation ("Delete" →
  "Yes, delete it") before anything is removed.

---

## 13. Known Limitations / Not Automatically Verified

- This was tested with Streamlit's `AppTest` framework (headless,
  simulated clicks) and manual review — not verified against a live
  Streamlit Cloud deployment or with real concurrent multi-user browser
  sessions.
- SQLite has no built-in row-level locking beyond what `sqlite3` itself
  provides. Two people saving at the exact same instant is unlikely in a
  small family use-case but is not stress-tested here.
- The `st.secrets` vs. environment-variable fallback was tested with
  environment variables in the sandboxed test run; behavior against a
  real `.streamlit/secrets.toml` file should be spot-checked once
  deployed.
