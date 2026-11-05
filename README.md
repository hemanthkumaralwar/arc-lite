# Arc Lite

Arc Lite is a chat assistant for ArchintX students. It answers only from an FAQ that staff maintain. If it isn't sure, it says **Unclear** or **Refused** instead of guessing.

## Links

| What | Where |
|---|---|
| Live app (chat and staff pages) | `https://YOUR-FRONTEND.vercel.app` |
| API | `https://YOUR-SERVICE.onrender.com` |
| API health check | `https://YOUR-SERVICE.onrender.com/health` |
| Staff login email | `YOUR-STAFF-EMAIL` |

The staff password is sent separately, not in this file.

---

## For testers

The first load can take up to a minute, because the free server wakes up after a quiet period. If the footer says **unreachable**, wait a minute and refresh.

| # | Where | What to do | Expected |
|---|---|---|---|
| 1 | Home page | Ask "how do I get my certificate" | An answer card showing **Answered** and a category |
| 2 | Home page | Ask "quantum physics" | **Refused**, with no category |
| 3 | Home page | Click 👍 or 👎 on an answer | "Saved" message; the button stays highlighted |
| 4 | Staff login | Enter a wrong password | "Invalid email or password." |
| 5 | Staff login | Sign in with the correct password | Opens the FAQ manager; FAQ and Dashboard links appear |
| 6 | FAQ manager | Add an entry, then ask the chat about it | The chat answers with that entry's text |
| 7 | FAQ manager | Edit that entry, then ask again | The new text appears |
| 8 | FAQ manager | Delete that entry, then ask again | The chat no longer uses it |
| 9 | Dashboard | Compare totals with your own count | Numbers match the conversations you made |
| 10 | Dashboard | Rate an answer 👎, then press **Refresh** | It appears in "Answered but rated down" |
| 11 | Phone | Open the site at about 375 pixels wide | No sideways scrolling |

**Reporting a problem:** write what you did, what you expected, what happened, and attach a screenshot. Include the browser and the time.

### Common problems

- **"Could not reach the Arc Lite server"**: wait a minute and try again. If it continues, tell the deployment team.
- **Sign-in fails with the right password**: check for extra spaces in the email. The password is case-sensitive.
- **"Your session has ended"**: staff sessions last 8 hours. Sign in again.
- **Staff pages go back to sign-in after a page reload**: this is intended. The session is kept only in the open page.

---

## Developer setup

Run these in Command Prompt. Use the `backend` folder unless the step says otherwise.

### 1. Create the virtual environment and install packages

```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Run `venv\Scripts\activate` each time you open a new Command Prompt. The prompt shows `(venv)` when it's active.

### 2. Copy the Neon connection string into `.env`

1. Sign in to neon.tech and open your project.
2. Click **Connect** and copy the connection string.
3. In `backend`, copy `.env.example.env` to `.env` if it doesn't exist yet:
   ```
   copy .env.example.env .env
   ```
4. Open `.env` in Notepad. Replace the `DATABASE_URL` line with the string you copied, starting with `DATABASE_URL=`. Also set `JWT_SECRET` to a random value of at least 32 characters.
5. Save with **UTF-8** encoding. Never commit `.env` to GitHub.

### 3. Run `migrate.py` whenever the schema changes

Run this after pulling changes that edit `app\schema.sql`, and before deploying them:
```
venv\Scripts\activate
python scripts\migrate.py
```
The script is safe to run more than once. It only adds what's missing.

### 4. Add the Gemini secrets in Render

The Gemini key is stored as a secret file, not in the code or in GitHub.

1. In Render, open **arc-lite-api**, then **Environment**.
2. Scroll to **Secret Files** and click **Add Secret File**.
3. **Filename:** `gemini.env`
4. **Contents:**
   ```
   GEMINI_API_KEY=your-key-here
   GEMINI_MODEL=gemini-3.1-flash-lite
   ```
5. Click **Save**. Render redeploys.
6. Confirm that `ENABLE_LLM_ASSIST` is set to `true` in the **Environment** list.

To get a key, sign in at aistudio.google.com and create one there.

---

## For the deployment team

### What runs where

| Part | Host | Source |
|---|---|---|
| Database | Neon (hosted PostgreSQL) | Connection string from the Neon dashboard |
| API | Render (free) | `backend` folder, using `render.yaml` |
| Website | Vercel (free) | `frontend` folder, no build step |

### Environment variables (Render)

| Name | Value |
|---|---|
| `DATABASE_URL` | Neon connection string. Keep it secret. |
| `JWT_SECRET` | Random value of 32 characters or more. Render generates it from `render.yaml`. |
| `CORS_ORIGINS` | `http://127.0.0.1:5500,http://localhost:5500,https://YOUR-FRONTEND.vercel.app` (no spaces, no trailing slash) |
| `ENABLE_LLM_ASSIST` | `false` |
| `PYTHON_VERSION` | `3.11.9` |

### Deployment order

1. **Database.** Create the Neon project and copy its connection string.
2. **Tables and staff login.** On a local machine, from `backend`, run `python scripts\migrate.py`, then `python scripts\seed.py`. This needs `DATABASE_URL` in `backend\.env`.
3. **API.** Push the repository to GitHub. In Render, create a **Blueprint** from `render.yaml`, and enter `DATABASE_URL` when asked. Wait for **Live**.
4. **Website.** In Vercel, import the repository, set **Root Directory** to `frontend`, and choose **Other** as the framework. Before deploying, set `apiBaseUrl` in `frontend/config.js` to the Render URL.
5. **Allow the website.** Put the Vercel address into `CORS_ORIGINS` on Render, then wait for the redeploy.

### Checks after each deployment

- Open `https://YOUR-SERVICE.onrender.com/health`. It must show `{"status":"ok"}`.
- Open the website. The footer must show **connected**.
- From the `backend` folder, run:
  ```
  venv\Scripts\activate
  python scripts\smoke_test.py https://YOUR-SERVICE.onrender.com
  python scripts\edge_cases.py https://YOUR-SERVICE.onrender.com
  ```
  Every line should read `[PASS]`, and the edge-case run should report no server errors.

### Before go-live

- **Replace the draft answers.** Every seeded answer begins with `[DRAFT]`, and students see those words. Confirm the text with ArchintX, then edit each entry in the FAQ manager. To list them:
  ```sql
  SELECT id, canonical_answer FROM faq_entries ORDER BY id;
  ```
- **Check the staff list.** Only accounts that should have access exist in the `staff` table.

### Staff accounts

Staff accounts can't be created from the website. They're managed by the team as follows. Run these on a machine whose `backend\.env` points to the live Neon database.

**Add a staff member**

1. Open Command Prompt in the `backend` folder and run:
   ```
   venv\Scripts\activate
   python scripts\create_staff.py
   ```
2. Enter the new person's email address.
3. Enter a password of at least 10 characters, then type it again to confirm. The characters don't show on screen.
4. Expected output: `Created staff account <email>.`

The script doesn't change the FAQ entries, because it only adds them when the table is empty.

If the email already exists, the script says so and leaves the existing password unchanged. To give someone a new password, remove them first and then add them again.

**Remove a staff member**

1. Open the Neon SQL Editor.
2. To see the current list:
   ```sql
   SELECT id, email, created_at FROM staff ORDER BY id;
   ```
3. To remove one person, replace the email and run:
   ```sql
   DELETE FROM staff WHERE email = 'person@example.com';
   ```
4. Expected result: `DELETE 1`. If it shows `DELETE 0`, the email wasn't found. Check the spelling against step 2.

A removed person can still use the site until their current session ends, which is up to 8 hours. To end every session immediately, including everyone else's, change `JWT_SECRET` in Render. Everyone then has to sign in again.

Always keep at least one staff account active.

### Other tasks

- **Ending all staff sessions:** change `JWT_SECRET` in Render. Every token then stops working.
- **Waking the API before a demo:** open `/health` a minute beforehand.
- **Running the test suite:** from `backend`, run `python -m pytest -v`. It needs no database.
