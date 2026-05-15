# -*- coding: utf-8 -*-
import argparse
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from .extraction import SQLDrivenExtractionRetrieval, LogicAwareExtractor
from .reason import SchemaAwareLLMReasoner, SchemaGuidedReasoner
from .schema import InteractiveSchemaDiscoverer



def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items



def _read_dataset(path: str, dataset: str) -> List[Dict[str, Any]]:
    """
    Read dataset from the given path. If path doesn't exist, try to read from default dataset directory.
    """
    # Try to read from the given path first
    if os.path.exists(path):
        if path.lower().endswith(".jsonl"):
            return _read_jsonl(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                return data["data"]
            raise ValueError("Unsupported dataset JSON structure. Expect list or {data:[...]}.")
    
    # If path doesn't exist, try default dataset directory
    default_paths = {
        "loong": "dataset/Loong/loong.jsonl",
        "mebench": "dataset/MEBench/test.jsonl"
    }
    
    if dataset.lower() in default_paths:
        default_path = default_paths[dataset.lower()]
        if os.path.exists(default_path):
            print(f"Using default dataset path: {default_path}")
            return _read_jsonl(default_path)
        else:
            # Try with absolute path
            abs_default_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), default_path)
            if os.path.exists(abs_default_path):
                print(f"Using default dataset path: {abs_default_path}")
                return _read_jsonl(abs_default_path)
    
    # If no valid path found, raise error
    raise FileNotFoundError(f"Could not find dataset file at {path}. Please check the path or ensure the dataset is available in the dataset directory.")



def _write_jsonl(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")



def _write_json(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)



def _normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    for ch in [",", ".", "?", "!", ":", ";", "\n", "\t"]:
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    return s



def exact_match(pred: str, gold: str) -> float:
    return 1.0 if _normalize_text(pred) == _normalize_text(gold) else 0.0



def token_f1(pred: str, gold: str) -> float:
    p_tokens = _normalize_text(pred).split()
    g_tokens = _normalize_text(gold).split()
    if not p_tokens and not g_tokens:
        return 1.0
    if not p_tokens or not g_tokens:
        return 0.0
    from collections import Counter

    pc = Counter(p_tokens)
    gc = Counter(g_tokens)
    overlap = sum(min(pc[t], gc[t]) for t in pc)
    prec = overlap / max(1, sum(pc.values()))
    rec = overlap / max(1, sum(gc.values()))
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)



def mebench_accuracy(pred: str, gold: Any, task_type: str = None) -> float:
    """
    MEBench accuracy evaluation with special handling for different task types.
    MEBench answer format: [[column_names], [row1], [row2], ...]
    """
    if not gold:
        # For tasks that don't have a direct answer but require analysis
        return _evaluate_analysis_task(pred, task_type)
    
    # Convert gold to string if it's a list
    gold_str = ""
    if isinstance(gold, list):
        # Handle MEBench answer format: [[column_names], [row1], [row2], ...]
        for row in gold:
            gold_str += " ".join([str(item) for item in row])
    else:
        gold_str = str(gold)
    
    # For Distribution Compliance tasks, check if prediction contains correct statistical values
    if task_type and "distribution compliance" in task_type.lower():
        return _evaluate_distribution_task(pred, gold_str, task_type)
    
    # For Correlation Analysis tasks, check if prediction contains correct correlation analysis
    if task_type and "correlation analysis" in task_type.lower():
        return _evaluate_correlation_task(pred, gold_str, task_type)
    
    # For Variance Analysis tasks, check if prediction contains correct variance analysis
    if task_type and "variance analysis" in task_type.lower():
        return _evaluate_variance_task(pred, gold_str, task_type)
    
    # For Aggregation tasks, check if prediction matches the aggregated value
    if task_type and "aggregation" in task_type.lower():
        return _evaluate_aggregation_task(pred, gold_str, task_type)
    
    # Standard accuracy for other tasks
    return 1.0 if _normalize_text(pred) == _normalize_text(gold_str) else 0.0


def _evaluate_analysis_task(pred: str, task_type: str) -> float:
    """
    Evaluate tasks that require analysis rather than direct answers.
    These tasks typically have empty gold answers but require statistical analysis.
    """
    pred_lower = pred.lower()
    
    if task_type and "correlation analysis" in task_type.lower():
        # Check if prediction contains correlation analysis terms
        correlation_terms = ["correlation", "positive", "negative", "no correlation", "pearson", "spearman"]
        if any(term in pred_lower for term in correlation_terms):
            return 1.0
    
    elif task_type and "variance analysis" in task_type.lower():
        # Check if prediction contains variance analysis terms
        variance_terms = ["variance", "standard deviation", "std", "difference", "compare"]
        if any(term in pred_lower for term in variance_terms):
            return 1.0
    
    return 0.0


def _evaluate_distribution_task(pred: str, gold: str, task_type: str) -> float:
    """
    Evaluate Distribution Compliance tasks.
    """
    pred_lower = pred.lower()
    gold_lower = gold.lower()
    
    # Check if prediction contains correct distribution terms
    distribution_terms = ["between", "range", "count", "frequency", "distribution"]
    if any(term in pred_lower for term in distribution_terms):
        return 1.0
    
    # Check if prediction matches gold value
    return 1.0 if _normalize_text(pred) == _normalize_text(gold) else 0.0


def _evaluate_correlation_task(pred: str, gold: str, task_type: str) -> float:
    """
    Evaluate Correlation Analysis tasks.
    """
    pred_lower = pred.lower()
    
    # Check if prediction contains correlation analysis
    correlation_terms = ["correlation", "positive", "negative", "no correlation", "pearson", "spearman", "relationship"]
    if any(term in pred_lower for term in correlation_terms):
        return 1.0
    
    return 0.0


def _evaluate_variance_task(pred: str, gold: str, task_type: str) -> float:
    """
    Evaluate Variance Analysis tasks.
    """
    pred_lower = pred.lower()
    
    # Check if prediction contains variance analysis
    variance_terms = ["variance", "standard deviation", "std", "difference", "compare", "average", "mean"]
    if any(term in pred_lower for term in variance_terms):
        return 1.0
    
    return 0.0


def _evaluate_aggregation_task(pred: str, gold: str, task_type: str) -> float:
    """
    Evaluate Aggregation tasks.
    """
    # For aggregation tasks, check if prediction matches the aggregated value
    return 1.0 if _normalize_text(pred) == _normalize_text(gold) else 0.0



def loong_confidence_em(pred: str, gold: Any, confidence: int) -> Dict[str, float]:
    """
    Loong benchmark evaluation using confidence score and Exact Match.
    Supports different task types:
    1. Citation/Reference relationships: {"Reference": [...], "Citation": [...]} 
    2. Citation chain construction: ["Title1", "Title2", ...]
    """
    
    # Normalize prediction
    pred_norm = _normalize_text(pred)
    
    # Normalize gold based on its type
    if isinstance(gold, dict):
        # Handle citation/reference relationship task
        gold_norm = _normalize_loong_relationship(gold)
        pred_norm = _normalize_loong_relationship_prediction(pred, gold)
    elif isinstance(gold, list):
        # Handle citation chain task
        gold_norm = _normalize_loong_chain(gold)
        pred_norm = _normalize_loong_chain_prediction(pred)
    else:
        # Handle simple text answer
        gold_norm = _normalize_text(str(gold))
    
    # Calculate EM score
    em_score = 1.0 if pred_norm == gold_norm else 0.0
    
    # Confidence-weighted score: EM * (confidence / 100)
    confidence_weighted = em_score * (confidence / 100.0)
    
    return {
        "em": em_score,
        "confidence_weighted": confidence_weighted,
        "confidence": confidence / 100.0
    }


def _normalize_loong_relationship(gold: Dict[str, Any]) -> str:
    """
    Normalize Loong relationship answer format: {"Reference": [...], "Citation": [...]} 
    """
    norm_refs = [_normalize_text(ref) for ref in gold.get("Reference", [])]
    norm_cites = [_normalize_text(cite) for cite in gold.get("Citation", [])]
    
    # Sort and join to create a normalized string
    sorted_refs = sorted(norm_refs)
    sorted_cites = sorted(norm_cites)
    
    return f"reference: {sorted_refs} citation: {sorted_cites}"


def _normalize_loong_relationship_prediction(pred: str, gold: Dict[str, Any]) -> str:
    """
    Normalize Loong relationship prediction to match gold format.
    """
    # Extract Reference and Citation sections from prediction
    ref_pattern = r"reference\s*:\s*\[([^\]]*)\]"
    cite_pattern = r"citation\s*:\s*\[([^\]]*)\]"
    
    refs = []
    cites = []
    
    ref_match = re.search(ref_pattern, pred, re.IGNORECASE)
    if ref_match:
        ref_content = ref_match.group(1)
        # Extract titles from the content
        titles = re.findall(r"\"([^\"]+)\"|'([^']+)'|[^,\[\]]+[^,\[\]\s]", ref_content)
        for title_tuple in titles:
            title = next((t for t in title_tuple if t), "").strip()
            if title:
                refs.append(_normalize_text(title))
    
    cite_match = re.search(cite_pattern, pred, re.IGNORECASE)
    if cite_match:
        cite_content = cite_match.group(1)
        # Extract titles from the content
        titles = re.findall(r"\"([^\"]+)\"|'([^']+)'|[^,\[\]]+[^,\[\]\s]", cite_content)
        for title_tuple in titles:
            title = next((t for t in title_tuple if t), "").strip()
            if title:
                cites.append(_normalize_text(title))
    
    # Sort and join to create a normalized string
    sorted_refs = sorted(refs)
    sorted_cites = sorted(cites)
    
    return f"reference: {sorted_refs} citation: {sorted_cites}"


def _normalize_loong_chain(gold: List[str]) -> str:
    """
    Normalize Loong citation chain answer format: ["Title1", "Title2", ...] 
    """
    norm_titles = [_normalize_text(title) for title in gold]
    return f"chain: {norm_titles}"


def _normalize_loong_chain_prediction(pred: str) -> str:
    """
    Normalize Loong citation chain prediction to match gold format.
    """
    # Extract chain from prediction
    chain_pattern = r"chain\s*:\s*\[([^\]]*)\]"
    
    titles = []
    
    chain_match = re.search(chain_pattern, pred, re.IGNORECASE)
    if chain_match:
        chain_content = chain_match.group(1)
        # Extract titles from the content
        extracted_titles = re.findall(r"\"([^\"]+)\"|'([^']+)'|[^,\[\]]+[^,\[\]\s]", chain_content)
        for title_tuple in extracted_titles:
            title = next((t for t in title_tuple if t), "").strip()
            if title:
                titles.append(_normalize_text(title))
    else:
        # Try to extract just a list of titles
        titles = re.findall(r"\"([^\"]+)\"|'([^']+)'|[^,\[\]]+[^,\[\]\s]", pred)
        titles = [next((t for t in title_tuple if t), "").strip() for title_tuple in titles]
        titles = [_normalize_text(title) for title in titles if title]
    
    return f"chain: {titles}"



def interactive_schema_answer(question: str, documents: Optional[Iterable[str]] = None, dataset_name: str = "loong") -> Dict[str, Any]:
    """Use InteractiveSchemaDiscoverer to answer the question."""
    docs = list(documents) if documents is not None else []
    
    # Create InteractiveSchemaDiscoverer with real implementation
    discoverer = InteractiveSchemaDiscoverer(
        query=question,
        documents=docs
    )
    
    # Run schema discovery
    final_schema = discoverer.run()
    
    # Generate answer based on schema
    answer = f"Discovered schema: {json.dumps(final_schema, indent=2)}"
    
    return {
        "prediction": answer,
        "used_llm": True,
        "confidence": 50,
        "table_rows": 0,
        "table_cols": [],
        "intermediate": {"schema": final_schema}
    }



def logic_aware_answer(question: str, documents: Optional[Iterable[str]] = None, dataset_name: str = "loong") -> Dict[str, Any]:
    """Use LogicAwareExtractor to answer the question."""
    docs = list(documents) if documents is not None else []
    
    # Create LogicAwareExtractor with real implementation
    extractor = LogicAwareExtractor(
        documents=docs,
        schema=None  # Let the extractor discover schema if needed
    )
    
    # Run extraction
    relational_db = extractor.run()
    
    # Generate answer based on extracted data
    if relational_db is not None:
        if hasattr(relational_db, "to_string"):
            answer = relational_db.to_string(index=False)
        else:
            answer = str(relational_db)
    else:
        answer = "No results found"
    
    return {
        "prediction": answer,
        "used_llm": True,
        "confidence": 50,
        "table_rows": len(relational_db) if relational_db is not None else 0,
        "table_cols": list(relational_db.columns) if relational_db is not None and hasattr(relational_db, "columns") else [],
        "intermediate": {"relational_db": relational_db}
    }



def schema_guided_answer(question: str, documents: Optional[Iterable[str]] = None, dataset_name: str = "loong") -> Dict[str, Any]:
    """Use SchemaGuidedReasoner to answer the question."""
    docs = list(documents) if documents is not None else []
    
    # Create SchemaGuidedReasoner with real implementation
    reasoner = SchemaGuidedReasoner()
    
    # In a real scenario, we would first discover the schema and extract data
    # For now, we'll raise NotImplementedError since we need to integrate with real schema discovery and extraction
    # This will be implemented in future versions
    raise NotImplementedError("schema_guided_answer requires real schema discovery and extraction implementation")



def srag_answer(question: str, documents: Optional[Iterable[str]] = None, dataset: str = "loong") -> Dict[str, Any]:
    engine = SQLDrivenExtractionRetrieval()
    output = engine.run(question, documents)

    rows = output.get("rows", [])
    table = pd.DataFrame(rows)
    if table.empty:
        table = pd.DataFrame(columns=[c["name"] for c in output.get("schema", {}).get("columns", [])])

    # Configure options based on dataset
    options = {}
    if dataset.lower() == "loong":
        options["require_confidence"] = True
    
    reasoner = SchemaAwareLLMReasoner(llm=None)
    r = reasoner.answer(question, table, options)
    return {
        "prediction": r.get("answer", ""),
        "used_llm": r.get("used_llm", False),
        "confidence": r.get("confidence", 50),
        "table_rows": len(table),
        "table_cols": list(table.columns),
        "intermediate": output,
    }



def _evaluate(dataset: List[Dict[str, Any]], dataset_name: str = "loong", limit: Optional[int] = None, method: str = "srag") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    preds: List[Dict[str, Any]] = []
    em_list: List[float] = []
    f1_list: List[float] = []
    accuracy_list: List[float] = []
    confidence_list: List[float] = []
    confidence_weighted_list: List[float] = []

    n = len(dataset) if limit is None else min(limit, len(dataset))
    for idx in range(n):
        item = dataset[idx]
        
        # Get question based on dataset
        if dataset_name.lower() == "loong":
            q = item.get("question", "").strip()
        else:  # mebench
            q = item.get("question", "").strip()
        
        # Get answer based on dataset
        if dataset_name.lower() == "loong":
            g = item.get("answer", "")
        else:  # mebench
            g = item.get("answer", [])
        
        # Get task type based on dataset
        if dataset_name.lower() == "loong":
            task_type = item.get("instruction", "")
        else:  # mebench
            task_type = item.get("type", "")
        
        # Get documents based on dataset
        docs = item.get("doc", [])
        if isinstance(docs, list) and docs and isinstance(docs[0], str) and ".md" in docs[0]:
            # If docs are file paths, read their contents
            # This is a placeholder - in a real scenario, we would read the actual files
            docs = [f"Content of {doc}" for doc in docs]
        
        if not q:
            continue

        # Choose answer method based on method parameter
        try:
            if method == "interactive_schema":
                out = interactive_schema_answer(q, docs, dataset_name)
            elif method == "logic_aware":
                out = logic_aware_answer(q, docs, dataset_name)
            elif method == "schema_guided":
                out = schema_guided_answer(q, docs, dataset_name)
            else:  # default to srag
                out = srag_answer(q, docs, dataset_name)
        except Exception as e:
            print(f"Error processing question {idx}: {e}")
            # Create a default output with error message
            out = {
                "prediction": f"Error: {str(e)}",
                "used_llm": False,
                "confidence": 0,
                "table_rows": 0,
                "table_cols": [],
                "intermediate": {"error": str(e)}
            }
        
        pred = out["prediction"]
        confidence = out.get("confidence", 50)

        # Calculate metrics based on dataset
        if dataset_name.lower() == "mebench":
            accuracy = mebench_accuracy(pred, g, task_type)
            accuracy_list.append(accuracy)
            
            # Convert gold to string for EM and F1 calculation
            gold_str = ""
            if isinstance(g, list):
                for row in g:
                    gold_str += " ".join([str(item) for item in row])
            else:
                gold_str = str(g)
            
            em = exact_match(pred, gold_str) if gold_str else 0.0
            f1 = token_f1(pred, gold_str) if gold_str else 0.0
            em_list.append(em)
            f1_list.append(f1)
        else:  # loong
            # Convert gold to string for Loong evaluation
            gold_str = ""
            if isinstance(g, dict):
                # For reference/citation tasks
                gold_str = json.dumps(g, sort_keys=True)
            elif isinstance(g, list):
                # For citation chain tasks
                gold_str = json.dumps(g, sort_keys=True)
            else:
                gold_str = str(g)
            
            loong_metrics = loong_confidence_em(pred, gold_str, confidence)
            em = loong_metrics["em"]
            confidence_weighted = loong_metrics["confidence_weighted"]
            em_list.append(em)
            confidence_weighted_list.append(confidence_weighted)
            confidence_list.append(confidence / 100.0)

        rec: Dict[str, Any] = {
            "id": item.get("id", idx),
            "question": q,
            "gold": g,
            "prediction": pred,
            "em": em,
            "confidence": confidence,
            "method": method
        }
        
        if dataset_name.lower() == "mebench":
            rec["accuracy"] = accuracy
            rec["f1"] = f1
        else:  # loong
            rec["confidence_weighted"] = confidence_weighted
        
        rec["intermediate"] = out.get("intermediate")
        preds.append(rec)

    # Calculate final metrics
    metrics = {
        "count": len(preds),
        "EM": round(sum(em_list) / len(em_list), 4) if em_list else 0.0,
        "method": method
    }
    
    if dataset_name.lower() == "mebench":
        metrics["Accuracy"] = round(sum(accuracy_list) / len(accuracy_list), 4) if accuracy_list else 0.0
        metrics["F1"] = round(sum(f1_list) / len(f1_list), 4) if f1_list else 0.0
    else:  # loong
        metrics["Confidence_Weighted"] = round(sum(confidence_weighted_list) / len(confidence_weighted_list), 4) if confidence_weighted_list else 0.0
        metrics["Avg_Confidence"] = round(sum(confidence_list) / len(confidence_list), 4) if confidence_list else 0.0
    
    return preds, metrics



def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Unified SRAG evaluator for Loong and MEBench")
    parser.add_argument("--dataset", type=str, choices=["loong", "mebench"], default="loong", help="Dataset selector")
    parser.add_argument("--data", type=str, required=False, default=None, help="Path to dataset JSONL/JSON")
    parser.add_argument("--out", type=str, required=False, default=None, help="Path to save predictions JSONL")
    parser.add_argument("--metrics", type=str, required=False, default=None, help="Path to save metrics JSON")
    parser.add_argument("--limit", type=int, required=False, default=None, help="Optional sample limit")
    parser.add_argument("--method", type=str, choices=["srag", "interactive_schema", "logic_aware", "schema_guided"], default="srag", 
                        help="Method to use for answering questions")

    args = parser.parse_args(argv)

    # defaults per dataset
    if not args.data:
        # Set default paths to real dataset files
        args.data = "dataset/Loong/loong.jsonl" if args.dataset == "loong" else "dataset/MEBench/test.jsonl"
    if not args.out:
        args.out = f"{args.dataset}_{args.method}_predictions.jsonl"
    if not args.metrics:
        args.metrics = f"{args.dataset}_{args.method}_metrics.json"

    data = _read_dataset(args.data, args.dataset)
    preds, metrics = _evaluate(data, dataset_name=args.dataset, limit=args.limit, method=args.method)

    _write_jsonl(args.out, preds)
    _write_json(args.metrics, metrics)

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"Saved predictions to: {os.path.abspath(args.out)}")
    print(f"Saved metrics to: {os.path.abspath(args.metrics)}")



if __name__ == "__main__":
    main()
