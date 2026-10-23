"""
One-time local upgrade (run this ONCE on your PC after installing the
cloud-deploy files). It adds the two new image-bytes columns to the
existing local SQLite database so old saved analyses keep working.

Usage (from the project root, venv active):
    python local_db_upgrade.py
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "chest_xray_ai_db.sqlite")

if not os.path.exists(DB_PATH):
    print("No local database found - nothing to upgrade (it will be created fresh on next start).")
    raise SystemExit(0)

con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.execute("PRAGMA table_info(Analyses)")
columns = [row[1] for row in cur.fetchall()]

added = []
if "original_image_bytes" not in columns:
    cur.execute("ALTER TABLE Analyses ADD COLUMN original_image_bytes BLOB")
    added.append("original_image_bytes")
if "processed_image_bytes" not in columns:
    cur.execute("ALTER TABLE Analyses ADD COLUMN processed_image_bytes BLOB")
    added.append("processed_image_bytes")

con.commit()
con.close()

if added:
    print("Upgraded local database. Added columns: " + ", ".join(added))
else:
    print("Local database is already up to date.")
