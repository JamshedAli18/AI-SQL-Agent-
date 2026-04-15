import sqlite3
import json
from langchain_core.tools import tool

DB_PATH = "techcorp.db"

@tool
def execute_sql(sql: str) -> str:
    """Executes a SQL query on the TechCorp database and returns results."""
    try:
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql)

        # If it's a SELECT query
        if sql.strip().upper().startswith("SELECT"):
            columns = [desc[0] for desc in cursor.description]
            rows    = cursor.fetchall()
            conn.close()
            if not rows:
                return "No results found."
            # Format as readable JSON
            result = [dict(zip(columns, row)) for row in rows]
            return json.dumps(result, indent=2)
        else:
            # For write operations
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return f"Success. {affected} row(s) affected."

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return f"ERROR: {str(e)}"

@tool
def get_schema() -> str:
    """Returns the full database schema with table structures."""
    try:
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        schema_parts = []
        for (table_name,) in tables:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            col_defs = [f"  {col[1]} ({col[2]})" for col in columns]
            schema_parts.append(
                f"Table: {table_name}\nColumns:\n" + "\n".join(col_defs)
            )

        conn.close()
        return "\n\n".join(schema_parts)

    except Exception as e:
        return f"ERROR: {str(e)}"