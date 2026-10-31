"""
Database Web Viewer on Port 8050
Allows user to view and inspect all tables in blood_bank.db directly in their browser.
"""
from flask import Flask, render_template_string, request
import sqlite3
import os

app = Flask(__name__)
DB_FILE = os.path.abspath("blood_bank.db")

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Cloud Blood Bank - Database Explorer</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background: #f4f6f9; color: #2d3748; }
        header { background: #c0392b; color: white; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; }
        header h1 { margin: 0; font-size: 1.3rem; }
        .container { display: flex; height: calc(100vh - 64px); }
        .sidebar { width: 260px; background: #ffffff; border-right: 1px solid #e2e8f0; padding: 16px; overflow-y: auto; }
        .sidebar h3 { font-size: 0.85rem; text-transform: uppercase; color: #718096; letter-spacing: 0.5px; margin-top: 0; }
        .sidebar ul { list-style: none; padding: 0; margin: 0; }
        .sidebar li { margin-bottom: 6px; }
        .sidebar a { display: block; padding: 8px 12px; border-radius: 6px; color: #2d3748; text-decoration: none; font-size: 0.95rem; font-weight: 500; }
        .sidebar a:hover, .sidebar a.active { background: #fdecea; color: #c0392b; font-weight: 600; }
        .content { flex: 1; padding: 24px; overflow-y: auto; }
        .table-card { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); overflow: hidden; }
        .card-header { padding: 14px 20px; border-bottom: 1px solid #edf2f7; display: flex; justify-content: space-between; align-items: center; }
        .card-header h2 { margin: 0; font-size: 1.15rem; color: #1a202c; }
        .badge { background: #edf2f7; color: #4a5568; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem; }
        th { background: #f7fafc; padding: 12px 16px; color: #4a5568; font-weight: 600; border-bottom: 1px solid #e2e8f0; }
        td { padding: 12px 16px; border-bottom: 1px solid #edf2f7; color: #2d3748; }
        tr:hover { background: #f8fafc; }
        .empty { padding: 40px; text-align: center; color: #a0aec0; }
    </style>
</head>
<body>
    <header>
        <h1>🗄️ Database Explorer & Inspector (blood_bank.db)</h1>
        <span>File: {{ db_file }}</span>
    </header>
    <div class="container">
        <div class="sidebar">
            <h3>Database Tables</h3>
            <ul>
                {% for t in tables %}
                <li>
                    <a href="/?table={{ t }}" class="{{ 'active' if t == selected_table else '' }}">
                        📋 {{ t }}
                    </a>
                </li>
                {% endfor %}
            </ul>
        </div>
        <div class="content">
            <div class="table-card">
                <div class="card-header">
                    <h2>Table: <code>{{ selected_table }}</code></h2>
                    <span class="badge">{{ rows|length }} records shown</span>
                </div>
                {% if rows %}
                <div style="overflow-x:auto;">
                    <table>
                        <thead>
                            <tr>
                                {% for col in columns %}
                                <th>{{ col }}</th>
                                {% endfor %}
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in rows %}
                            <tr>
                                {% for val in row %}
                                <td>{{ val if val is not none else 'NULL' }}</td>
                                {% endfor %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% else %}
                <div class="empty">No records found in this table.</div>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
"""

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def index():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [r[0] for r in cursor.fetchall()]
    
    selected_table = request.args.get("table")
    if not selected_table or selected_table not in tables:
        selected_table = "organizations" if "organizations" in tables else (tables[0] if tables else None)
        
    columns = []
    rows = []
    if selected_table:
        cursor.execute(f"PRAGMA table_info({selected_table})")
        columns = [col[1] for col in cursor.fetchall()]
        cursor.execute(f"SELECT * FROM {selected_table} ORDER BY 1 DESC LIMIT 100")
        rows = [list(r) for r in cursor.fetchall()]
        
    conn.close()
    return render_template_string(
        TEMPLATE,
        tables=tables,
        selected_table=selected_table,
        columns=columns,
        rows=rows,
        db_file=DB_FILE
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)

