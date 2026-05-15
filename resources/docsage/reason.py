# -*- encoding: utf-8 -*-

import os
import re
import math
import json
import pandas as pd
import sqlite3
from typing import Any, Callable, Dict, List, Optional, Tuple


class SchemaAwareLLMReasoner:
    """
    Schema-aware LLM reasoning module.
    """

    def __init__(self, llm: Optional[Callable[[str], str]] = None, max_rows: int = 1000):
        """
        Args:
            llm: Optional pluggable LLM callable. Signature: (prompt: str) -> str
            max_rows: Max rows to include in the serialized table context
        """
        self.llm = llm
        self.max_rows = max_rows

    def answer(self, question: str, table: pd.DataFrame, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        End-to-end entry: build prompt -> call LLM (if provided) -> fallback reasoning -> return structured answer.

        Returns:
            {"answer": str, "reasoning": str, "used_llm": bool, "rows_considered": int, "confidence": int}
        """
        options = options or {}
        limited_table = self._limit_table(table, self.max_rows)
        prompt = self._build_structured_prompt(question, limited_table, options)

        # Prefer LLM path
        if callable(self.llm):
            try:
                raw = self.llm(prompt)
                answer_text, confidence = self._postprocess_llm_output(raw)
                return {
                    "answer": answer_text,
                    "reasoning": "LLM answered using schema-aware prompt.",
                    "used_llm": True,
                    "rows_considered": len(limited_table),
                    "confidence": confidence
                }
            except Exception:
                pass

        # Fallback deterministic reasoning
        fallback_answer, trace = self._deterministic_reasoning(question, limited_table)
        # For fallback reasoning, assign a moderate confidence score
        fallback_confidence = self._calculate_fallback_confidence(question, limited_table, fallback_answer)
        return {
            "answer": fallback_answer,
            "reasoning": trace,
            "used_llm": False,
            "rows_considered": len(limited_table),
            "confidence": fallback_confidence
        }

    def _build_structured_prompt(self, question: str, table: pd.DataFrame, options: Dict[str, Any]) -> str:
        """
        Structured context injection: serialize table + schema + clear instruction
        to force schema-aware behavior.
        """
        instruction = (
            "You are a careful data analyst. Answer ONLY using the data from the table below. "
            "If the table does not contain sufficient information, say 'Insufficient data'. "
            "Be concise and directly answer the question."
        )
        if options.get("allow_chain_of_thought"):
            instruction += " Explain your reasoning briefly."
        
        # Add confidence scoring instruction for Loong benchmark
        if options.get("require_confidence"):
            instruction += (
                "\n\nIMPORTANT: After your answer, provide a confidence score from 0-100 "
                "indicating how certain you are about your answer. Format: "
                "ANSWER: [your answer]\nCONFIDENCE: [0-100]"
            )

        schema_info = self._schema_summary(table)
        table_text = self._serialize_table(table, max_col_width=64)

        parts = [
            "[Instruction]",
            instruction,
            "",
            "[Question]",
            question.strip(),
            "",
            "[Schema]",
            schema_info,
            "",
            "[Table]",
            table_text,
            "",
            "[Answer strictly from the table]"
        ]
        return "\n".join(parts)

    def _schema_summary(self, table: pd.DataFrame) -> str:
        cols = []
        for c in table.columns:
            series = table[c]
            dtype = str(series.dtype)
            sample = series.dropna().head(3).tolist()
            cols.append({"name": c, "dtype": dtype, "samples": sample})
        return json.dumps({"columns": cols}, ensure_ascii=False)

    def _serialize_table(self, table: pd.DataFrame, max_col_width: int = 64) -> str:
        # Render a compact markdown table for readability
        def truncate(v: Any) -> str:
            s = "" if pd.isna(v) else str(v)
            if len(s) > max_col_width:
                return s[: max_col_width - 1] + "…"
            return s

        headers = list(table.columns)
        rows: List[List[str]] = []
        for _, row in table.iterrows():
            rows.append([truncate(row[h]) for h in headers])

        md = []
        md.append("| " + " | ".join(headers) + " |")
        md.append("| " + " | ".join(["---" for _ in headers]) + " |")
        for r in rows:
            md.append("| " + " | ".join(r) + " |")
        return "\n".join(md)

    def _limit_table(self, table: pd.DataFrame, max_rows: int) -> pd.DataFrame:
        if len(table) <= max_rows:
            return table.copy()
        return table.head(max_rows).copy()

    def _postprocess_llm_output(self, raw: Any) -> Tuple[str, int]:
        """
        Parse LLM output to extract answer and confidence score.
        Returns: (answer_text, confidence_score)
        """
        if raw is None:
            return "Insufficient data", 0
        
        raw_text = str(raw).strip()
        
        # Try to parse confidence score from structured output
        confidence_match = re.search(r'CONFIDENCE:\s*(\d+)', raw_text, re.IGNORECASE)
        if confidence_match:
            confidence = int(confidence_match.group(1))
            # Extract answer before CONFIDENCE line
            answer_match = re.search(r'ANSWER:\s*(.+?)(?=\nCONFIDENCE:|$)', raw_text, re.IGNORECASE | re.DOTALL)
            if answer_match:
                answer = answer_match.group(1).strip()
            else:
                answer = raw_text.split('\nCONFIDENCE:')[0].strip()
            return answer, max(0, min(100, confidence))
        
        # Try to extract confidence from JSON format
        try:
            if isinstance(raw, dict):
                answer = str(raw.get("answer") or raw.get("text") or "")
                confidence = int(raw.get("confidence", 50))  # Default to 50 if not provided
                return answer, max(0, min(100, confidence))
        except (ValueError, TypeError):
            pass
        
        # Fallback: return raw text with moderate confidence
        return raw_text, 50

    def _calculate_fallback_confidence(self, question: str, table: pd.DataFrame, answer: str) -> int:
        """
        Calculate confidence score for fallback reasoning based on data quality and answer type.
        """
        if not answer or answer == "Insufficient data":
            return 0
        
        confidence = 50  # Base confidence
        
        # Increase confidence based on data availability
        if not table.empty:
            confidence += 20
            if len(table) > 1:
                confidence += 10
        
        # Increase confidence for specific answer types
        if any(keyword in answer.lower() for keyword in ["sum", "total", "average", "mean", "count"]):
            confidence += 10  # Numerical answers are more reliable
        
        if any(keyword in answer.lower() for keyword in ["earliest", "latest", "first", "last"]):
            confidence += 15  # Temporal answers are quite reliable
        
        # Decrease confidence for uncertain answers
        if any(keyword in answer.lower() for keyword in ["maybe", "possibly", "likely", "perhaps"]):
            confidence -= 20
        
        return max(0, min(100, confidence))

    def _deterministic_reasoning(self, question: str, table: pd.DataFrame) -> Tuple[str, str]:
        q = question.lower()
        trace: List[str] = ["Deterministic fallback reasoning engaged."]

        if table.empty or table.shape[1] == 0:
            return "Insufficient data", "Empty table."

        # Try to find date-like column
        date_col = self._guess_date_column(table)
        num_cols = self._numeric_columns(table)
        text_cols = [c for c in table.columns if c not in num_cols]

        # 1) earliest/latest
        if any(k in q for k in ["earliest", "first", "oldest", "最早", "第一"]):
            if date_col:
                try:
                    sorted_df = self._sort_by_date(table, date_col, ascending=True)
                    trace.append(f"Sorted by {date_col} ascending.")
                    return self._row_to_text(sorted_df.iloc[0]), " -> ".join(trace)
                except Exception as e:
                    trace.append(f"Sort failed: {e}")
        if any(k in q for k in ["latest", "most recent", "newest", "最晚", "最新"]):
            if date_col:
                try:
                    sorted_df = self._sort_by_date(table, date_col, ascending=False)
                    trace.append(f"Sorted by {date_col} descending.")
                    return self._row_to_text(sorted_df.iloc[0]), " -> ".join(trace)
                except Exception as e:
                    trace.append(f"Sort failed: {e}")

        # 2) list/which/what for a given filter like company/product
        company_col = self._guess_company_column(table)
        product_col = self._guess_product_column(table)

        filt_val = self._guess_filter_value(question)
        if filt_val and (company_col or product_col):
            df = table
            if company_col:
                df = df[df[company_col].astype(str).str.contains(filt_val, case=False, na=False)]
            if product_col and df.empty:
                df = table[table[product_col].astype(str).str.contains(filt_val, case=False, na=False)]
            trace.append(f"Filtered by '{filt_val}'. Rows: {len(df)}")
            if not df.empty:
                # If a price column exists, list prices
                price_col = self._guess_price_column(df)
                if price_col:
                    vals = df[price_col].dropna().astype(str).unique().tolist()
                    return ", ".join(vals), " -> ".join(trace)
                # else return product names
                if product_col:
                    vals = df[product_col].dropna().astype(str).unique().tolist()
                    return ", ".join(vals), " -> ".join(trace)
                # else return row count
                return str(len(df)), " -> ".join(trace)

        # 3) aggregate (sum/avg/min/max) on numeric columns
        agg = self._guess_aggregation(question)
        if agg and num_cols:
            col = num_cols[0]
            series = pd.to_numeric(table[col], errors='coerce').dropna()
            if series.empty:
                return "Insufficient data", "No numeric values."
            if agg == "sum":
                return str(series.sum()), f"sum({col})"
            if agg == "avg":
                return str(round(series.mean(), 4)), f"avg({col})"
            if agg == "min":
                return f"{series.min()} (col={col})", f"min({col})"
            if agg == "max":
                return f"{series.max()} (col={col})", f"max({col})"

        # 4) Default: return a compact summary of table
        return self._compact_summary(table), "Default summary fallback."

    def _guess_date_column(self, table: pd.DataFrame) -> Optional[str]:
        candidates = [c for c in table.columns if re.search(r"date|time|released", c, re.I)]
        for c in candidates:
            try:
                pd.to_datetime(table[c], errors='raise')
                return c
            except Exception:
                continue
        # try coerce
        for c in candidates:
            coerced = pd.to_datetime(table[c], errors='coerce')
            if coerced.notna().any():
                return c
        return None

    def _sort_by_date(self, table: pd.DataFrame, col: str, ascending: bool) -> pd.DataFrame:
        s = pd.to_datetime(table[col], errors='coerce')
        df = table.copy()
        df['__dt__'] = s
        df = df.sort_values('__dt__', ascending=ascending)
        df = df.drop(columns=['__dt__'])
        df = df[df[col].notna()]
        return df

    def _numeric_columns(self, table: pd.DataFrame) -> List[str]:
        numeric_cols: List[str] = []
        for c in table.columns:
            if pd.api.types.is_numeric_dtype(table[c]):
                numeric_cols.append(c)
                continue
            # try to coerce price-like strings "$799" -> 799.0
            stripped = table[c].astype(str).str.replace(r"[^0-9\.-]", "", regex=True)
            coerced = pd.to_numeric(stripped, errors='coerce')
            if coerced.notna().any():
                numeric_cols.append(c)
        return numeric_cols

    def _guess_company_column(self, table: pd.DataFrame) -> Optional[str]:
        for key in ["company", "brand", "vendor"]:
            for c in table.columns:
                if c.lower() == key:
                    return c
        return None

    def _guess_product_column(self, table: pd.DataFrame) -> Optional[str]:
        for key in ["product", "model", "item"]:
            for c in table.columns:
                if c.lower() == key:
                    return c
        return None

    def _guess_price_column(self, table: pd.DataFrame) -> Optional[str]:
        for key in ["price", "amount", "cost"]:
            for c in table.columns:
                if key in c.lower():
                    return c
        return None

    def _guess_filter_value(self, question: str) -> Optional[str]:
        # naive extraction of a capitalized token like Apple / Samsung
        m = re.search(r"([A-Z][a-zA-Z0-9_\-]{2,})", question)
        if m:
            return m.group(1)
        # also try lowercase brand names
        for v in ["apple", "samsung", "huawei", "xiaomi"]:
            if v in question.lower():
                return v
        return None

    def _guess_aggregation(self, question: str) -> Optional[str]:
        q = question.lower()
        if any(k in q for k in ["sum", "total", "合计", "总和"]):
            return "sum"
        if any(k in q for k in ["avg", "average", "mean", "均值", "平均"]):
            return "avg"
        if any(k in q for k in ["min", "minimum", "最小"]):
            return "min"
        if any(k in q for k in ["max", "maximum", "最大"]):
            return "max"
        return None

    def _row_to_text(self, row: pd.Series) -> str:
        parts = []
        for c in row.index:
            val = row[c]
            if pd.isna(val):
                continue
            parts.append(f"{c}={val}")
        return ", ".join(parts)

    def _compact_summary(self, table: pd.DataFrame) -> str:
        # Return a short, traceable summary
        head = table.head(3)
        return f"Rows={len(table)}, Cols={list(table.columns)}, Head={head.to_dict(orient='records')}"


class SchemaGuidedReasoner:
    """
    Implementation of Schema-Guided Relational Reasoning method.
    """
    
    def __init__(self, reasoning_llm: Optional[Callable[[str], str]] = None):
        """
        Args:
            reasoning_llm: Optional LLM callable for query compilation and answer generation
        """
        self.reasoning_llm = reasoning_llm
        
    def compile_and_optimize_query(self, query: str, schema: dict) -> str:
        """
        Compile natural language query to SQL and optimize using schema information.
        
        Args:
            query: Natural language query
            schema: Relational schema
        
        Returns:
            Optimized SQL query string
        """
        if self.reasoning_llm is None:
            raise NotImplementedError("No LLM provided for query compilation")
        
        # Step 1: Compile natural language query to SQL using LLM
        raw_sql = self._compile_nl_to_sql(query, schema)
        
        # Step 2: Optimize SQL query using schema information
        optimized_sql = self._optimize_sql(raw_sql, schema)
        
        return optimized_sql
    
    def _compile_nl_to_sql(self, query: str, schema: dict) -> str:
        """
        Compile natural language query to SQL using LLM.
        
        Args:
            query: Natural language query
            schema: Relational schema
        
        Returns:
            Raw SQL query string
        """
        # Build prompt for LLM
        prompt = f"""
        You are an expert SQL developer. Convert the following natural language query into a syntactically correct SQL query.
        
        Schema Information:
        {json.dumps(schema, indent=2)}
        
        Natural Language Query:
        {query}
        
        Please return ONLY the SQL query, no other text.
        """
        
        # Call LLM to generate SQL
        sql = self.reasoning_llm(prompt)
        
        # Clean up SQL (remove any markdown formatting or extra text)
        sql = re.sub(r'^```sql\n|\n```$', '', sql, flags=re.MULTILINE)
        sql = sql.strip()
        
        return sql
    
    def _optimize_sql(self, sql: str, schema: dict) -> str:
        """
        Optimize SQL query using schema information.
        
        Args:
            sql: Raw SQL query
            schema: Relational schema
        
        Returns:
            Optimized SQL query string
        """
        # In this simplified implementation, we'll focus on:
        # 1. Using defined foreign keys for joins
        # 2. Pushing down filters
        # 3. Simplifying unnecessary complexity
        
        # For now, we'll return the raw SQL, but in a real implementation,
        # we would parse the SQL, analyze it, and apply optimization rules
        # using the schema information.
        
        # Simple optimization: ensure we're using proper join keys from schema
        optimized_sql = self._ensure_proper_join_keys(sql, schema)
        
        return optimized_sql
    
    def _ensure_proper_join_keys(self, sql: str, schema: dict) -> str:
        """
        Ensure SQL query uses proper foreign keys for joins based on schema.
        
        Args:
            sql: Raw SQL query
            schema: Relational schema
        
        Returns:
            SQL query with proper join keys
        """
        # This is a simplified implementation
        # In a real implementation, we would parse the SQL and replace
        # implicit joins with explicit joins using the foreign keys from schema
        
        # For now, return the original SQL
        return sql
    
    def execute_sql(self, sql: str, database: Any) -> pd.DataFrame:
        """
        Execute SQL query on the provided database.
        
        Args:
            sql: SQL query to execute
            database: Database to execute query on
                - If dict: keys are table names, values are pd.DataFrame
                - If sqlite3.Connection: SQLite database connection
        
        Returns:
            Query result as pandas DataFrame
        """
        if isinstance(database, dict):
            # Database is a dict of DataFrames
            return self._execute_sql_on_dataframes(sql, database)
        elif isinstance(database, sqlite3.Connection):
            # Database is a SQLite connection
            return pd.read_sql_query(sql, database)
        else:
            raise ValueError(f"Unsupported database type: {type(database)}")
    
    def _execute_sql_on_dataframes(self, sql: str, database: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Execute SQL query on a dict of DataFrames.
        
        Args:
            sql: SQL query to execute
            database: Dict of DataFrames, keys are table names
        
        Returns:
            Query result as pandas DataFrame
        """
        # Create an in-memory SQLite database
        conn = sqlite3.connect(":memory:")
        
        try:
            # Write all DataFrames to SQLite
            for table_name, df in database.items():
                df.to_sql(table_name, conn, index=False, if_exists='replace')
            
            # Execute SQL query
            result_df = pd.read_sql_query(sql, conn)
            
            return result_df
        finally:
            conn.close()
    
    def trace_provenance(self, result_df: pd.DataFrame, database: Any, doc_mapping: dict) -> List[dict]:
        """
        Trace provenance for each row in the result set.
        
        Args:
            result_df: Query result DataFrame
            database: Database used for query execution
            doc_mapping: Mapping from tuples to original document chunks
        
        Returns:
            List of provenance information for each result row
        """
        provenance_list = []
        
        for idx, row in result_df.iterrows():
            # For each result row, trace its source tuples
            source_tuples = self._trace_source_tuples(row, database, doc_mapping)
            
            provenance_list.append({
                "result_row": row.to_dict(),
                "source_tuples": source_tuples
            })
        
        return provenance_list
    
    def _trace_source_tuples(self, row: pd.Series, database: Any, doc_mapping: dict) -> List[dict]:
        """
        Trace source tuples for a single result row.
        
        Args:
            row: Result row
            database: Database used for query execution
            doc_mapping: Mapping from tuples to original document chunks
        
        Returns:
            List of source tuples with provenance information
        """
        source_tuples = []
        
        # This is a simplified implementation
        # In a real implementation, we would:
        # 1. Analyze the SQL query to determine which tables were joined
        # 2. For each table, extract the primary key values from the result row
        # 3. Look up the source tuples in the database
        # 4. Map each tuple to its original document chunk using doc_mapping
        
        for table_name in doc_mapping.keys():
            primary_key = hash(tuple(row.values)) % 1000
            
            # Look up document mapping if available
            if table_name in doc_mapping and primary_key in doc_mapping[table_name]:
                doc_info = doc_mapping[table_name][primary_key]
                source_tuples.append({
                    "table": table_name,
                    "primary_key": primary_key,
                    "doc_id": doc_info["doc_id"],
                    "chunk_id": doc_info["chunk_id"]
                })
        
        return source_tuples
    
    def generate_answer(self, query: str, result_df: pd.DataFrame, provenance: List[dict]) -> str:
        """
        Generate natural language answer based on query results and provenance.
        
        Args:
            query: Original natural language query
            result_df: Query result DataFrame
            provenance: Provenance information
        
        Returns:
            Natural language answer
        """
        if self.reasoning_llm is None:
            raise NotImplementedError("No LLM provided for answer generation")
        
        # Build prompt for LLM
        prompt = f"""
        You are an expert data analyst. Generate a concise, accurate natural language answer to the following query based on the provided results and provenance information.
        
        Query:
        {query}
        
        Results:
        {result_df.to_string(index=False)}
        
        Provenance Information:
        {json.dumps(provenance, indent=2)}
        
        Please generate a clear, concise answer that directly addresses the query. If the results are empty, say "No results found."
        """
        
        # Call LLM to generate answer
        answer = self.reasoning_llm(prompt)
        
        return answer.strip()
    
    def run(self, query: str, schema: dict, database: Any, doc_mapping: dict) -> Dict[str, Any]:
        """
        Run the full schema-guided reasoning pipeline.
        
        Args:
            query: Natural language query
            schema: Relational schema
            database: Database to execute query on
            doc_mapping: Mapping from tuples to original document chunks
        
        Returns:
            Dict containing:
                - answer: Natural language answer
                - sql_query: Optimized SQL query
                - result_set: Query result DataFrame
                - provenance: Provenance information
        """
        # Step 1: Compile and optimize query
        sql_query = self.compile_and_optimize_query(query, schema)
        
        # Step 2: Execute SQL query
        result_set = self.execute_sql(sql_query, database)
        
        # Step 3: Trace provenance
        provenance = self.trace_provenance(result_set, database, doc_mapping)
        
        # Step 4: Generate natural language answer
        answer = self.generate_answer(query, result_set, provenance)
        
        return {
            "answer": answer,
            "sql_query": sql_query,
            "result_set": result_set,
            "provenance": provenance
        }


def _load_sample_table() -> pd.DataFrame:
    csv_path = os.path.join(os.getcwd(), "extracted_phone_prices.csv")
    if os.path.exists(csv_path):
        try:
            return pd.read_csv(csv_path)
        except Exception:
            pass
    # fallback sample
    return pd.DataFrame([
        {"company": "Apple", "product": "iPhone 15", "price": "$799", "release_date": "September 2023"},
        {"company": "Samsung", "product": "Galaxy Z Fold5", "price": "$1799", "release_date": "September 2023"},
        {"company": "Apple", "product": "iPhone 15 Pro", "price": "$999", "release_date": "September 2023"},
    ])



def main():
    # Test SchemaAwareLLMReasoner (existing functionality)
    print("Testing SchemaAwareLLMReasoner...")
    reasoner = SchemaAwareLLMReasoner(llm=None)
    table = _load_sample_table()
    
    question = "What products does Apple produce?"
    result = reasoner.answer(question, table)
    
    print("Question:", question)
    print("Answer:", result["answer"]) 
    print("Reasoning:", result["reasoning"]) 
    print("Used LLM:", result["used_llm"])
    print()
    
    # Test SchemaGuidedReasoner (new functionality)
    print("Testing SchemaGuidedReasoner...")
    
    # Create a simple test scenario
    test_schema = {
        "entities": ["phones", "companies"],
        "attributes": {
            "phones": ["id", "company", "product", "price", "release_date"],
            "companies": ["id", "name", "founded", "country"]
        },
        "relationships": [
            {"from": "phones", "to": "companies", "foreign_key": "company"}
        ],
        "primary_keys": {
            "phones": ["id"],
            "companies": ["id"]
        }
    }
    
    # Create a simple test database
    test_db = {
        "phones": pd.DataFrame([
            {"id": 1, "company": "Apple", "product": "iPhone 15", "price": 799, "release_date": "2023-09-15"},
            {"id": 2, "company": "Apple", "product": "iPhone 15 Pro", "price": 999, "release_date": "2023-09-15"},
            {"id": 3, "company": "Samsung", "product": "Galaxy Z Fold5", "price": 1799, "release_date": "2023-08-11"}
        ]),
        "companies": pd.DataFrame([
            {"id": 1, "name": "Apple", "founded": 1976, "country": "USA"},
            {"id": 2, "name": "Samsung", "founded": 1969, "country": "South Korea"}
        ])
    }
    
    # Create test doc mapping
    test_doc_mapping = {
        "phones": {
            1: {"doc_id": "doc1", "chunk_id": 0, "text": "Apple released iPhone 15 in September 2023 with a price of $799."},
            2: {"doc_id": "doc1", "chunk_id": 1, "text": "iPhone 15 Pro starts at $999."},
            3: {"doc_id": "doc2", "chunk_id": 0, "text": "Samsung's Galaxy Z Fold5 costs $1799."}
        },
        "companies": {
            1: {"doc_id": "doc3", "chunk_id": 0, "text": "Apple Inc. was founded in 1976 in the USA."},
            2: {"doc_id": "doc4", "chunk_id": 0, "text": "Samsung Group was founded in 1969 in South Korea."}
        }
    }
    
    query = "What products does Apple produce?"
    
    # Note: SchemaGuidedReasoner requires a real LLM, so we'll just test initialization here
    schema_guided_reasoner = SchemaGuidedReasoner()
    print(f"SchemaGuidedReasoner initialized successfully")
    print(f"Test schema: {json.dumps(test_schema, indent=2)}")
    print(f"Test query: {query}")
    print("To run the full reasoning pipeline, provide a real LLM instance to SchemaGuidedReasoner")


if __name__ == "__main__":
    main()
