# ThoraxAI — Deploy on PythonAnywhere (Free · No GitHub · Always Online)

Your app runs on PythonAnywhere's servers 24/7 — your PC can be switched off
and everyone can still open the site.

    Anyone's browser  →  https://YOUR-NAME.pythonanywhere.com  →  your Flask app
                          (works even when your laptop is off)

## Why this host (matches what you wanted)
* Site stays up with your PC OFF — no sleep, no wake-up delay
* NO GitHub, NO credit card — you upload files in the browser like Google Drive
* Your accounts / history / uploaded X-rays persist permanently
* Free forever (Beginner plan)

## Honest limits of the free plan
* URL is a subdomain:  your-username.pythonanywhere.com  (custom names are paid)
* 512 MB disk — plenty for a demo project
* An UNUSED web app expires after ~1 month → just log in to pythonanywhere.com
  once a month (open the Web page and click "Extend" if it asks)
* Outbound internet from code is limited to an allowlist — fine for ThoraxAI,
  because its report engine runs locally
* No MySQL on new free accounts — fine, ThoraxAI uses SQLite

==========================================================================
## STEP 0 — One-time prep on your PC (5 minutes)

1. Open `app.py` and set debug mode OFF (search for `debug=True`):

       app.run(debug=False)          # was app.run(debug=True)

   (On the server the WSGI file also forces FLASK_DEBUG=0 — but fix it here
   too so nothing ever runs in debug mode publicly.)

2. Generate the package list — double-click **GET_REQUIREMENTS.bat**
   (it creates `requirements.txt` from your .venv).

3. Build the upload zip — double-click **MAKE_UPLOAD_ZIP.bat**
   (it creates `thoraxai_upload.zip`, automatically leaving out .venv,
   __pycache__, .git, ngrok.exe).

   NOTE: the zip INCLUDES your database + uploads so your existing studies
   show up online. If you prefer a fresh start, remove the *.db file from
   the project folder before making the zip.

==========================================================================
## STEP 1 — Sign up (2 minutes)

1. Go to https://www.pythonanywhere.com  →  **Create a free account**
2. Confirm the email they send you.

==========================================================================
## STEP 2 — Upload the code (5 minutes)

1. Dashboard → **Files** (left menu) → click **Upload a file** →
   choose `thoraxai_upload.zip` (it lands in /home/yourname/)
2. Open a **Bash** console (left menu → Consoles → Bash) and run:

       unzip -o thoraxai_upload.zip -d thoraxai

3. Check it worked:

       ls thoraxai        # should show app.py, config.py, templates, ...

==========================================================================
## STEP 3 — Create the web app (5 minutes)

1. Left menu → **Web** → **Add a new web app**
2. Click through the wizard:
   - Domain: shows your-username.pythonanywhere.com  → Next
   - Choose **Manual configuration** (NOT the Flask option)
   - Python version: pick 3.12 (or the newest offered) → Next
3. In "Source code" set the path to:  /home/yourname/thoraxai
4. Click the **WSGI configuration file** link — DELETE everything in it and
   paste the contents of the `wsgi.py` file from this kit, then:
   - set USERNAME = "yourname"
   - set FOLDER   = "thoraxai"
   - Save the file (Ctrl+S).

==========================================================================
## STEP 4 — Packages (5 minutes)

1. On the Web page, scroll to **Virtualenv** → type a name like
   `thoraxai-venv` → choose Python 3.12 → Create.
2. Open a Bash console and run (replace yourname):

       workon thoraxai-venv
       pip install -r /home/yourname/thoraxai/requirements.txt

   If a package fails because it is Windows-only, remove that line from
   requirements.txt and run the command again.
   If `opencv-python` fails, run instead:
       pip install opencv-python-headless

==========================================================================
## STEP 5 — Static files (2 minutes)

On the Web page, scroll to **Static files** → Add one row:

       URL:  /static/          Directory:  /home/yourname/thoraxai/static

==========================================================================
## STEP 6 — Go live!

1. Click the big green **Reload** button on the Web page.
2. Open https://yourname.pythonanywhere.com  🎉

That's it — the site is now online 24/7, even with your PC off.

==========================================================================
## If something goes wrong
* Open the Web page → **Error log** link → it shows the exact error.
* "ModuleNotFoundError" → Step 4 not done, or wrong virtualenv selected
  (Web page → Virtualenv → make sure it points at thoraxai-venv).
* "no such table" / empty history → the *.db file was not uploaded, or
  config.py points at an absolute Windows path (tell me, I'll fix config.py).
* CSS / images missing → check the Static files mapping (Step 5).
* Still stuck? Paste me the error log text and I'll fix it.

## Keeping the site alive
* Log in to pythonanywhere.com about once a month and open the Web page
   (click "Extend" if it offers — otherwise nothing to do).
* Your site does NOT sleep and does NOT need your laptop.

## Security checklist before sharing the link
* [ ] debug=False in app.py
* [ ] wsgi.py has FLASK_DEBUG=0 (it does by default in this kit)
* [ ] Don't upload this kit's zip anywhere public (it may contain your db)
