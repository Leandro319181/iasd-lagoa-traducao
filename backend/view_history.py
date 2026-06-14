"""Lê o histórico SQLite e imprime um resumo diagnóstico.
Uso: python view_history.py [caminho_do_db]"""
import sqlite3
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "logs/historico.db"
conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row

total = conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
print(f"Total de blocos: {total}\n")

print("Por status:")
for row in conn.execute(
        "SELECT status, COUNT(*) c FROM blocks GROUP BY status ORDER BY c DESC"):
    pct = (row["c"] / total * 100) if total else 0
    print(f"  {row['status']:<20} {row['c']:>5}  ({pct:.1f}%)")

no_audio = conn.execute(
    "SELECT COUNT(*) FROM blocks WHERE status='ok' AND has_audio=0").fetchone()[0]
print(f"\nBlocos OK sem áudio (TTS falhou): {no_audio}")

print("\nÚltimos 10 blocos:")
for row in conn.execute(
        "SELECT created_at, status, pt_text, en_text FROM blocks ORDER BY id DESC LIMIT 10"):
    pt = (row["pt_text"] or "")[:40]
    en = (row["en_text"] or "")[:40]
    print(f"  [{row['created_at']}] {row['status']:<18} PT: {pt!r} EN: {en!r}")

conn.close()
