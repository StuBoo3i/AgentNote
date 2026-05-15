from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Iterable

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


@dataclass
class ColumnSpec:
    name: str
    dtype: str = "TEXT"  # SQLite basic types supported: TEXT/INTEGER/REAL


@dataclass
class TableSchema:
    name: str
    columns: List[ColumnSpec]

    def to_sql_create(self) -> str:
        cols = ", ".join(f"{c.name} {c.dtype}" for c in self.columns)
        return f"CREATE TABLE IF NOT EXISTS {self.name} ({cols});"


@dataclass
class ExtractionRow:
    values: Dict[str, Any]
    confidence_score: float = 0.0
    is_valid: bool = True


@dataclass
class ParseResult:
    schema: TableSchema
    sql: str
    reasoning: str = ""  # Optional: keep parsing rationale/chain


@dataclass
class LogicAwareExtractor:
    """Implementation of Logic-Aware Structured Extraction (CLEAR mechanism)."""
    
    documents: List[str]
    schema: Optional[dict] = None
    
    def __post_init__(self):
        # Initialize internal state
        self.candidate_tuples = []
        self.final_tuples = []
        self.temp_db_conn = sqlite3.connect(":memory:")
        self.tau_low = 0.7  # Low confidence threshold
        self.tau_high = 0.95  # High confidence threshold
        
        # If schema is not provided, infer it from documents
        if self.schema is None:
            self.schema = self._infer_schema()
    
    def _infer_schema(self) -> dict:
        """Infer schema from documents."""
        # Simple implementation that infers entities and attributes from documents
        entities = set()
        attributes = {}
        relationships = []
        
        for doc in self.documents:
            # Extract entities and attributes using simple rules
            doc_entities, doc_attributes = self._extract_entities_and_attributes(doc)
            entities.update(doc_entities)
            
            # Merge attributes
            for entity in doc_attributes:
                if entity not in attributes:
                    attributes[entity] = set()
                attributes[entity].update(doc_attributes[entity])
        
        return {
            "entities": list(entities),
            "attributes": {k: list(v) for k, v in attributes.items()},
            "relationships": relationships,
            "constraints": {
                "functional_dependencies": [],
                "temporal_constraints": [],
                "numerical_ranges": [],
                "foreign_keys": []
            }
        }
    
    def _extract_entities_and_attributes(self, text: str) -> Tuple[Set[str], Dict[str, Set[str]]]:
        """Extract entities and attributes from text."""
        entities = set()
        attributes = {}
        
        # Simple rules for extracting entities and attributes
        # Look for patterns like "Company X has CEO Y" or "X's CEO is Y"
        
        # Extract company-ceo pairs
        ceo_matches = re.finditer(r"([A-Za-z0-9_\-\s]+)(?:['‘’]s)?\s+(?:CEO|chief executive officer)\s+is\s+([A-Za-z0-9_\-\s]+)", text)
        for match in ceo_matches:
            company = match.group(1).strip()
            entities.add("Company")
            if "Company" not in attributes:
                attributes["Company"] = set()
            attributes["Company"].add("CEO")
        
        # Extract product-price pairs
        price_matches = re.finditer(r"([A-Za-z0-9_\-\s]+)\s+costs?\s+(\$[0-9,]+)", text)
        for match in price_matches:
            product = match.group(1).strip()
            entities.add("Product")
            if "Product" not in attributes:
                attributes["Product"] = set()
            attributes["Product"].add("Price")
        
        return entities, attributes
    
    def extract_basic_tuples(self) -> List[Dict[str, Any]]:
        """Extract candidate tuples from documents."""
        candidate_tuples = []
        
        # Simple implementation that extracts tuples using regex patterns
        for doc in self.documents:
            tuples_from_doc = self._extract_tuples_from_text(doc)
            candidate_tuples.extend(tuples_from_doc)
        
        self.candidate_tuples = candidate_tuples
        return candidate_tuples
    
    def _extract_tuples_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract tuples from a single document."""
        extracted = []
        
        # Check schema entities and extract corresponding tuples
        entities = self.schema.get("entities", [])
        
        if "Company" in entities:
            # Extract company-ceo pairs
            matches = re.finditer(r"([A-Za-z0-9_\-\s]+)(?:['‘’]s)?\s+(?:CEO|chief executive officer)\s+is\s+([A-Za-z0-9_\-\s]+)", text)
            for match in matches:
                company, ceo = match.groups()
                extracted.append({
                    "Company": company.strip(),
                    "CEO": ceo.split(",")[0].strip()
                })
        
        if "Product" in entities:
            # Extract product-price pairs
            matches = re.finditer(r"([A-Za-z0-9_\-\s]+)\s+costs?\s+(\$[0-9,]+)", text)
            for match in matches:
                product, price = match.groups()
                extracted.append({
                    "Product": product.strip(),
                    "Price": price.strip()
                })
        
        return extracted
    
    def evaluate_confidence(self, tuples: List[Dict[str, Any]]) -> List[ExtractionRow]:
        """Evaluate confidence scores for extracted tuples (Level A)."""
        evaluated_rows = []
        
        for t in tuples:
            # Simulate confidence calculation with Conformal Prediction
            # In real implementation, this would use LoRA-fine-tuned model and calibration
            confidence_score = self._calculate_calibrated_confidence(t)
            
            evaluated_row = ExtractionRow(
                values=t,
                confidence_score=confidence_score,
                is_valid=confidence_score >= self.tau_low
            )
            evaluated_rows.append(evaluated_row)
        
        return evaluated_rows
    
    def _calculate_calibrated_confidence(self, tuple_data: Dict[str, Any]) -> float:
        """Calculate calibrated confidence score using Conformal Prediction."""
        # Simple simulation: generate confidence between 0.6 and 1.0
        import random
        return random.uniform(0.6, 1.0)
    
    def check_logical_consistency(self, rows: List[ExtractionRow]) -> List[ExtractionRow]:
        """Check cross-record logical consistency (Level B)."""
        # Create temp tables for constraint checking
        self._create_temp_tables()
        
        # Insert rows into temp tables
        self._insert_into_temp_tables(rows)
        
        # Check all constraints
        invalid_rows = []
        
        # 1. Check functional dependencies
        fd_violations = self._check_functional_dependencies()
        invalid_rows.extend(fd_violations)
        
        # 2. Check temporal constraints
        temporal_violations = self._check_temporal_constraints()
        invalid_rows.extend(temporal_violations)
        
        # 3. Check numerical ranges
        numerical_violations = self._check_numerical_ranges()
        invalid_rows.extend(numerical_violations)
        
        # 4. Check foreign key constraints
        fk_violations = self._check_foreign_keys()
        invalid_rows.extend(fk_violations)
        
        # Mark invalid rows
        for row in rows:
            if row in invalid_rows:
                row.is_valid = False
        
        return rows
    
    def _create_temp_tables(self):
        """Create temporary tables in SQLite for constraint checking."""
        # Create tables for each entity
        for entity in self.schema["entities"]:
            attributes = self.schema["attributes"].get(entity, [])
            if not attributes:
                continue
            
            # Create columns for the entity
            columns = [ColumnSpec(attr) for attr in attributes]
            table_schema = TableSchema(name=entity, columns=columns)
            
            # Create table in temp DB
            self.temp_db_conn.execute(table_schema.to_sql_create())
        
        # Enable foreign key constraints
        self.temp_db_conn.execute("PRAGMA foreign_keys = ON;")
    
    def _insert_into_temp_tables(self, rows: List[ExtractionRow]):
        """Insert rows into temporary tables."""
        # For simplicity, we'll assume all rows belong to the first entity
        # In real implementation, we'd map rows to appropriate entities
        if not rows or not self.schema["entities"]:
            return
        
        entity = self.schema["entities"][0]
        attributes = self.schema["attributes"].get(entity, [])
        if not attributes:
            return
        
        # Prepare insert statement
        placeholders = ",".join(["?"] * len(attributes))
        insert_sql = f"INSERT INTO {entity} ({', '.join(attributes)}) VALUES ({placeholders});"
        
        # Insert rows
        for row in rows:
            values = tuple(row.values.get(attr, None) for attr in attributes)
            self.temp_db_conn.execute(insert_sql, values)
        
        self.temp_db_conn.commit()
    
    def _check_functional_dependencies(self) -> List[ExtractionRow]:
        """Check functional dependencies."""
        # Simple simulation: return empty list (no violations)
        return []
    
    def _check_temporal_constraints(self) -> List[ExtractionRow]:
        """Check temporal constraints."""
        # Simple simulation: return empty list (no violations)
        return []
    
    def _check_numerical_ranges(self) -> List[ExtractionRow]:
        """Check numerical range constraints."""
        # Simple simulation: return empty list (no violations)
        return []
    
    def _check_foreign_keys(self) -> List[ExtractionRow]:
        """Check foreign key constraints."""
        # Simple simulation: return empty list (no violations)
        return []
    
    def correct_invalid_tuples(self, rows: List[ExtractionRow]) -> List[ExtractionRow]:
        """Correct invalid tuples (Level C)."""
        corrected_rows = []
        
        for row in rows:
            if row.is_valid and row.confidence_score >= self.tau_low:
                corrected_rows.append(row)
                continue
            
            # For now, we'll just mark low confidence rows as invalid
            # In real implementation, this would use retrieval-augmented LLM for correction
            corrected_row = ExtractionRow(
                values=row.values,
                confidence_score=row.confidence_score,
                is_valid=False
            )
            corrected_rows.append(corrected_row)
        
        return corrected_rows
    
    def create_relational_database(self, rows: List[ExtractionRow]) -> Any:
        """Create final relational database from corrected tuples."""
        if not rows:
            return None
        
        # Extract column names from schema
        if not self.schema["entities"] or not self.schema["attributes"]:
            return None
        
        entity = self.schema["entities"][0]
        columns = self.schema["attributes"].get(entity, [])
        
        # Create data for database
        data = []
        for row in rows:
            row_data = [row.values.get(col, None) for col in columns]
            data.append(row_data)
        
        if PANDAS_AVAILABLE:
            # Return pandas DataFrame if available
            return pd.DataFrame(data, columns=columns)
        else:
            # Otherwise return list of dicts
            return [dict(zip(columns, row)) for row in data]
    
    def run(self) -> Any:
        """Run the full Logic-Aware Extraction pipeline."""
        # Step 1: Extract basic tuples
        candidates = self.extract_basic_tuples()
        
        # Step 2: Evaluate confidence
        evaluated_rows = self.evaluate_confidence(candidates)
        
        # Step 3: Check logical consistency
        consistent_rows = self.check_logical_consistency(evaluated_rows)
        
        # Step 4: Correct invalid tuples
        corrected_rows = self.correct_invalid_tuples(consistent_rows)
        
        # Step 5: Create relational database
        relational_db = self.create_relational_database(corrected_rows)
        
        # Cleanup
        self.temp_db_conn.close()
        
        return relational_db


def safe_import_transformers_pipeline():
    try:
        from transformers import pipeline  # type: ignore
        return pipeline
    except Exception:
        return None


def load_optional_prompt(prompt_rel_path: str) -> Optional[str]:
    """Load prompt text if prompts/query_to_sql_schema.txt exists for LLM parsing template."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_path = os.path.join(base_dir, "prompts", prompt_rel_path)
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        # Also search an upper-level prompts directory
        repo_root = os.path.dirname(base_dir)
        alt_path = os.path.join(repo_root, "prompts", prompt_rel_path)
        if os.path.exists(alt_path):
            with open(alt_path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception:
        pass
    return None


class LLMClient:
    """Prefer OpenAI API; fallback to heuristic parser if unavailable."""

    def __init__(self) -> None:
        self._openai_available = False
        self._openai_client = None
        # New OpenAI SDK (>=1.0) interface
        try:
            from openai import OpenAI  # type: ignore

            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._openai_client = OpenAI()
                self._openai_available = True
        except Exception:
            self._openai_available = False

    def parse_query(self, question: str) -> ParseResult:
        if self._openai_available:
            try:
                return self._parse_with_openai(question)
            except Exception:
                pass
        # Fallback to local heuristics
        return self._parse_with_heuristics(question)

    def _parse_with_openai(self, question: str) -> ParseResult:
        prompt_template = load_optional_prompt("query_to_sql_schema.txt")
        system_msg = (
            "You are a system that converts a natural language question into "
            "(a) a target relational table schema and (b) a SQLite SQL query that selects from that schema. "
            "Return STRICT JSON with keys: schema: {name, columns:[{name,dtype}]}, sql, reasoning."
        )
        user_msg = (
            f"Question: {question}\n"
            "Constraints: The SQL must select from the table you define; avoid joins; use columns you create."
        )

        if prompt_template:
            user_msg = prompt_template.replace("{{QUESTION}}", question)

        # Use responses.create (new SDK) to request structured JSON output
        try:
            resp = self._openai_client.responses.create(  # type: ignore
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                input=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = resp.output[0].content[0].text if hasattr(resp, "output") else resp.choices[0].message.content  # type: ignore
            data = json.loads(content)
            schema_obj = data.get("schema") or {}
            cols = [ColumnSpec(**c) for c in schema_obj.get("columns", [])]
            schema = TableSchema(name=schema_obj.get("name", "target"), columns=cols)
            sql = data.get("sql", f"SELECT * FROM {schema.name}")
            reasoning = data.get("reasoning", "")
            return ParseResult(schema=schema, sql=sql, reasoning=reasoning)
        except Exception as e:
            # Final fallback
            return self._parse_with_heuristics(question)

    def _parse_with_heuristics(self, question: str) -> ParseResult:
        # Simple heuristic: build a generic schema and extract potential filters from the question
        schema = TableSchema(
            name="facts",
            columns=[
                ColumnSpec("entity", "TEXT"),
                ColumnSpec("attribute", "TEXT"),
                ColumnSpec("value", "TEXT"),
                ColumnSpec("source", "TEXT"),
            ],
        )

        # Extract from question: year, capitalized entity candidates, attribute keywords
        year = None
        m = re.search(r"(19|20)\d{2}", question)
        if m:
            year = m.group(0)

        # Entity candidates: consecutive Capitalized words
        entity_candidates = re.findall(r"([A-Z][\w\-]*(?:\s+[A-Z][\w\-]*)+)", question)

        # Attribute keyword set
        attr_keywords = []

        where_clauses = []
        if year:
            where_clauses.append(f"value LIKE '%{year}%'")
        if entity_candidates:
            ors = " OR ".join([f"entity LIKE '%{e}%'" for e in entity_candidates])
            where_clauses.append(f"({ors})")
        if attr_keywords:
            ors = " OR ".join([f"attribute LIKE '%{a}%'" for a in attr_keywords])
            where_clauses.append(f"({ors})")

        sql = f"SELECT entity, attribute, value, source FROM {schema.name}"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        return ParseResult(schema=schema, sql=sql, reasoning="heuristic")


class SLMClient:
    """Prefer local transformers text-generation for structured extraction; otherwise fallback to rules."""

    def __init__(self) -> None:
        self._pipe = None
        pipeline = safe_import_transformers_pipeline()
        if pipeline:
            model_name = os.getenv("SLM_MODEL", "Mistral-7B")  # Lightweight placeholder model
            try:
                self._pipe = pipeline(
                    "text-generation",
                    model=model_name,
                    trust_remote_code=True,
                    device_map="auto",
                    max_new_tokens=512,
                )
            except Exception:
                self._pipe = None

    def extract(self, schema: TableSchema, texts: Iterable[str]) -> List[ExtractionRow]:
        if self._pipe is not None:
            try:
                return self._extract_with_lm(schema, texts)
            except Exception:
                pass
        return self._extract_with_rules(schema, texts)

    def _build_prompt(self, schema: TableSchema, text_chunk: str) -> str:
        cols = ", ".join([f"{c.name}:{c.dtype}" for c in schema.columns])
        instruction = (
            "You are an information extractor. Only extract facts that match the schema. "
            "Return JSONL, one object per fact with exactly the schema columns as keys. "
            "Ignore unrelated text."
        )
        return (
            f"{instruction}\n"
            f"Schema: table={schema.name}; columns=[{cols}]\n"
            f"Text:\n{text_chunk}\n"
            "Output JSONL:"
        )

    def _extract_with_lm(self, schema: TableSchema, texts: Iterable[str]) -> List[ExtractionRow]:
        rows: List[ExtractionRow] = []
        for chunk in texts:
            prompt = self._build_prompt(schema, chunk)
            out = self._pipe(prompt)[0]["generated_text"][len(prompt) :]
            # Parse JSONL
            for line in out.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    # Keep only columns defined in schema
                    values = {c.name: obj.get(c.name, None) for c in schema.columns}
                    rows.append(ExtractionRow(values=values))
                except Exception:
                    # Skip non-JSON lines
                    continue
        return rows

    def _extract_with_rules(self, schema: TableSchema, texts: Iterable[str]) -> List[ExtractionRow]:
        # Rule-based extraction:
        # - Match common Chinese patterns like "X 是 Y", "X 的 Z 是 Y", "X 任命 Y 为 Z"
        # - Also support English patterns "X is Y" / "X's Z is Y"
        rows: List[ExtractionRow] = []
        col_names = [c.name for c in schema.columns]
        has_entity = "entity" in col_names
        has_attribute = "attribute" in col_names
        has_value = "value" in col_names
        has_source = "source" in col_names

        patterns: List[Tuple[str, Any]] = [
            (r"([\u4e00-\u9fa5A-Za-z0-9_\-]+)\s*是\s*([\u4e00-\u9fa5A-Za-z0-9_\-]+)", ("entity", "value")),
            (r"([\u4e00-\u9fa5A-Za-z0-9_\-]+)\s*的\s*([\u4e00-\u9fa5A-Za-z0-9_\-]+)\s*是\s*([\u4e00-\u9fa5A-Za-z0-9_\-]+)", ("entity", "attribute", "value")),
            (r"([A-Za-z0-9_\-\s]+)\s+is\s+([A-Za-z0-9_\-\s]+)", ("entity", "value")),
            (r"([A-Za-z0-9_\-\s]+)'s\s+([A-Za-z0-9_\-\s]+)\s+is\s+([A-Za-z0-9_\-\s]+)", ("entity", "attribute", "value")),
            (r"([\u4e00-\u9fa5A-Za-z0-9_\-]+)\s*任命\s*([\u4e00-\u9fa5A-Za-z0-9_\-]+)\s*为\s*([\u4e00-\u9fa5A-Za-z0-9_\-]+)", ("entity", "value", "attribute")),
        ]

        for text in texts:
            for pat, mapping in patterns:
                for m in re.finditer(pat, text):
                    groups = [g.strip() for g in m.groups()]
                    values: Dict[str, Any] = {}
                    if has_entity and len(groups) >= 1:
                        values["entity"] = groups[0]
                    if has_attribute and len(groups) >= 3 and isinstance(mapping, tuple) and len(mapping) == 3:
                        # For triplets, locate attribute position according to mapping
                        attr_idx = mapping.index("attribute") if "attribute" in mapping else None
                        if attr_idx is not None and attr_idx < len(groups):
                            values["attribute"] = groups[attr_idx]
                    if has_value:
                        # Locate value position
                        if isinstance(mapping, tuple):
                            if "value" in mapping:
                                v_idx = mapping.index("value")
                                if v_idx < len(groups):
                                    values["value"] = groups[v_idx]
                        elif len(groups) >= 2:
                            values["value"] = groups[1]
                    if has_source:
                        values["source"] = "heuristic"

                    # Keep only schema columns
                    filtered = {c.name: values.get(c.name, None) for c in schema.columns}

                    # Require at least one of entity/value/attribute
                    if any(filtered.get(k) for k in ["entity", "value", "attribute"]):
                        rows.append(ExtractionRow(values=filtered))

        return rows


class SQLDrivenExtractionRetrieval:
    def __init__(self, llm: Optional[LLMClient] = None, slm: Optional[SLMClient] = None) -> None:
        self.llm = llm or LLMClient()
        self.slm = slm or SLMClient()

    def parse_query(self, question: str) -> ParseResult:
        return self.llm.parse_query(question)

    def extract_candidates(self, schema: TableSchema, documents: Iterable[str]) -> List[ExtractionRow]:
        return self.slm.extract(schema, documents)

    def _create_temp_table_and_insert(self, conn: sqlite3.Connection, schema: TableSchema, rows: List[ExtractionRow]) -> None:
        conn.execute(f"DROP TABLE IF EXISTS {schema.name}")
        conn.execute(schema.to_sql_create())
        if not rows:
            return
        col_names = [c.name for c in schema.columns]
        placeholders = ",".join(["?"] * len(col_names))
        insert_sql = f"INSERT INTO {schema.name} ({', '.join(col_names)}) VALUES ({placeholders})"
        values_list = []
        for r in rows:
            values_list.append(tuple(r.values.get(col, None) for col in col_names))
        conn.executemany(insert_sql, values_list)
        conn.commit()

    def execute_sql(self, parse_result: ParseResult, rows: List[ExtractionRow]) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(":memory:")
        try:
            self._create_temp_table_and_insert(conn, parse_result.schema, rows)
            sql = parse_result.sql.strip().rstrip(";")
            cur = conn.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            data = [dict(zip(cols, row)) for row in cur.fetchall()]
            return data
        finally:
            conn.close()

    def run(self, question: str, documents: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        parse_result = self.parse_query(question)
        docs = list(documents) if documents is not None else self._load_default_documents()
        candidates = self.extract_candidates(parse_result.schema, docs)
        result_rows = self.execute_sql(parse_result, candidates)
        return {
            "schema": {
                "name": parse_result.schema.name,
                "columns": [{"name": c.name, "dtype": c.dtype} for c in parse_result.schema.columns],
            },
            "sql": parse_result.sql,
            "rows": result_rows,
        }

    def _load_default_documents(self) -> List[str]:
        # If repository has document_store.db, try to load; otherwise use built-in samples.
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "document_store.db")
        if not os.path.exists(db_path):
            # Built-in sample facts
            return [
                "Apple's CEO is Tim Cook, serving since 2011.",
                "Apple is a technology company headquartered in Cupertino.",
                "Apple's CEO is Tim Cook.",
                "Microsoft's CEO is Satya Nadella.",
                "Google's CEO is Sundar Pichai.",
                "OpenAI's CEO is Sam Altman, who briefly left in 2023 and returned.",
            ]

        try:
            docs: List[str] = []
            conn = sqlite3.connect(db_path)
            with conn:
                # Assumed simple schema: documents(id INTEGER, content TEXT)
                # If the table does not exist, return empty
                cur = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
                )
                if cur.fetchone():
                    for (content,) in conn.execute("SELECT content FROM documents"):
                        if content:
                            docs.append(str(content))
            conn.close()
            if docs:
                return docs
        except Exception:
            pass

        # Fallback to samples
        return [
            "Apple's CEO is Tim Cook, serving since 2011.",
            "Apple's CEO is Tim Cook.",
            "OpenAI's CEO is Sam Altman, who briefly left in 2023 and returned.",
        ]


def run_pipeline(question: str, documents: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    engine = SQLDrivenExtractionRetrieval()
    return engine.run(question, documents)



def _pretty_print(result: Dict[str, Any]) -> None:
    print("=== Target Schema ===")
    print(json.dumps(result["schema"], ensure_ascii=False, indent=2))
    print("\n=== SQL ===")
    print(result["sql"])
    print("\n=== Final Rows ===")
    print(json.dumps(result["rows"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Run SQLDrivenExtractionRetrieval test if no arguments provided
        print("Running SQLDrivenExtractionRetrieval test...")
        
        question = "What is the capital of France?"
        result = run_pipeline(question)
        _pretty_print(result)
        sys.exit(0)
    
    question = sys.argv[1]
    output = run_pipeline(question)
    _pretty_print(output)
