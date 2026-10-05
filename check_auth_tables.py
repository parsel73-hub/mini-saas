import sqlite3

con = sqlite3.connect("smoke_auth.db")
rows = list(con.execute("SELECT name FROM sqlite_master WHERE type='table'"))
print("TABLES:", [r[0] for r in rows])

users = list(con.execute("PRAGMA table_info(users)"))
print("USERS COLUMNS:", [r[1] for r in users])

for uid, email, phash in con.execute("SELECT id, email, password_hash FROM users"):
    print(f"USER {uid}: {email} hash_starts={phash[:7]} len={len(phash)}")
con.close()

