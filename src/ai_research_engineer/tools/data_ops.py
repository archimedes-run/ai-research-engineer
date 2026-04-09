"""
Database Operations using DuckDB.
Allows agents to query Parquet files using SQL without loading data into memory.
"""

import duckdb
import logging
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

def query_duckdb(query: str, working_dir: str) -> str:
    """
    Execute a read-only SQL query against local Parquet/CSV files.
    """
    try:
        # 1. Security & Safety Checks (Expanded)
        forbidden_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE"]
        if any(keyword in query.upper() for keyword in forbidden_keywords):
            return f"Error: Only SELECT statements are allowed. Forbidden keywords detected."
            
        # 2. Connect to DuckDB (In-memory mode, pointing to file system)
        con = duckdb.connect(database=':memory:')
        
        original_cwd = os.getcwd()
        try:
            os.chdir(working_dir)
            
            # 3. Execute Query with Hard Limit
            if "LIMIT" not in query.upper():
                query += " LIMIT 1000"
                
            df = con.execute(query).fetchdf()
            
            # 4. Format Output as Token-Efficient Markdown
            row_count = len(df)
            
            if row_count >= 1000:
                sample_md = df.head(5).to_markdown(index=False)
                return (
                    f"⚠️ WARNING: Result truncated at 1000 rows. Use aggregations (GROUP BY) for analysis.\n"
                    f"Total rows returned: {row_count}\n\n"
                    f"Data Sample (First 5 rows):\n{sample_md}"
                )
                
            return df.to_markdown(index=False)
            
        finally:
            os.chdir(original_cwd)
            con.close()
            
    except Exception as e:
        logger.error(f"DuckDB Query Failed: {e}")
        return f"Error executing query: {str(e)}"

def get_schema(filepath: str, working_dir: str) -> str:
    """
    Get the schema (columns and types) of a Parquet or CSV file.
    """
    return query_duckdb(f"DESCRIBE SELECT * FROM '{filepath}'", working_dir)