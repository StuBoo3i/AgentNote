from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


@dataclass
class InteractiveSchemaDiscoverer:
    """Implementation of the ASK algorithm for Interactive Schema Discovery."""
    
    query: str
    documents: List[str]
    
    def __post_init__(self):
        # Initialize internal state
        self.current_schema = {"entities": [], "attributes": {}, "relationships": []}
        self.uncertainties = []
        self.iteration_count = 0
        self.max_iterations = 5
        
    def generate_initial_schema(self) -> dict:
        """Generate initial schema using document analysis."""
        # Simple implementation that extracts entities and attributes from documents
        entities = set()
        attributes = {}
        relationships = []
        
        # Extract entities from query
        query_entities = self._extract_entities_from_query()
        entities.update(query_entities)
        
        # Extract entities and attributes from documents
        for doc in self.documents[:2]:  # Use first 2 documents for initial schema
            doc_entities, doc_attributes = self._extract_entities_and_attributes(doc)
            entities.update(doc_entities)
            
            # Merge attributes
            for entity in doc_attributes:
                if entity not in attributes:
                    attributes[entity] = set()
                attributes[entity].update(doc_attributes[entity])
        
        # Convert sets to lists for JSON serialization
        self.current_schema = {
            "entities": list(entities),
            "attributes": {k: list(v) for k, v in attributes.items()},
            "relationships": relationships
        }
        
        return self.current_schema
    
    def _extract_entities_from_query(self) -> Set[str]:
        """Extract entities from the query."""
        # Simple implementation that looks for common entity types
        entities = set()
        query_lower = self.query.lower()
        
        # Common entity types
        entity_types = ["company", "person", "product", "location", "event", "organization"]
        
        for entity_type in entity_types:
            if entity_type in query_lower:
                entities.add(entity_type.capitalize())
        
        return entities
    
    def _extract_entities_and_attributes(self, text: str) -> Tuple[Set[str], Dict[str, Set[str]]]:
        """Extract entities and attributes from text."""
        entities = set()
        attributes = {}
        
        # Simple rules for extracting entities and attributes
        # This is a placeholder - in a real implementation, we would use NLP techniques
        
        # Look for patterns like "Company X has CEO Y" or "X's CEO is Y"
        import re
        
        # Extract company-ceo pairs
        ceo_matches = re.finditer(r"([A-Za-z0-9_\-\s]+)(?:['‘’]s)?\s+(?:CEO|chief executive officer)\s+is\s+([A-Za-z0-9_\-\s]+)", text)
        for match in ceo_matches:
            company = match.group(1).strip()
            entities.add("Company")
            if "Company" not in attributes:
                attributes["Company"] = set()
            attributes["Company"].add("CEO")
        
        # Extract company-product pairs
        product_matches = re.finditer(r"([A-Za-z0-9_\-\s]+)\s+(?:produces|makes|manufactures)\s+([A-Za-z0-9_\-\s]+)", text)
        for match in product_matches:
            company = match.group(1).strip()
            product = match.group(2).strip()
            entities.add("Company")
            entities.add("Product")
            if "Company" not in attributes:
                attributes["Company"] = set()
            attributes["Company"].add("Product")
            
        return entities, attributes
    
    def detect_uncertainties(self) -> List[Dict[str, Any]]:
        """
        Detect three types of uncertainties:
        1. Entity alignment conflicts
        2. Attribute value distribution anomalies
        3. Missing relationships
        """
        uncertainties = []
        
        # 1. Entity alignment conflicts detection (simple simulation)
        entity_conflicts = self._detect_entity_alignment_conflicts()
        uncertainties.extend(entity_conflicts)
        
        # 2. Attribute value distribution anomalies detection
        value_anomalies = self._detect_attribute_value_anomalies()
        uncertainties.extend(value_anomalies)
        
        # 3. Missing relationships detection
        missing_relationships = self._detect_missing_relationships()
        uncertainties.extend(missing_relationships)
        
        self.uncertainties = uncertainties
        return uncertainties
    
    def _detect_entity_alignment_conflicts(self) -> List[Dict[str, Any]]:
        """Detect entity alignment conflicts (simple simulation)."""
        # This is a simplified implementation
        # In real scenario, we would analyze entity attributes across documents
        conflicts = []
        
        # Check if we have at least two entities with potential conflicts
        if len(self.current_schema["entities"]) >= 2:
            conflicts.append({
                "type": "entity_alignment",
                "description": f"Potential alignment conflict between {self.current_schema['entities'][0]} and {self.current_schema['entities'][1]}",
                "entity1": self.current_schema["entities"][0],
                "entity2": self.current_schema["entities"][1]
            })
        
        return conflicts
    
    def _detect_attribute_value_anomalies(self) -> List[Dict[str, Any]]:
        """Detect attribute value distribution anomalies (simple simulation)."""
        anomalies = []
        
        # Check if we have attributes to analyze
        if self.current_schema["attributes"]:
            entity = next(iter(self.current_schema["attributes"]))
            attributes = self.current_schema["attributes"][entity]
            
            if attributes:
                anomalies.append({
                    "type": "attribute_value_anomaly",
                    "description": f"Potential value anomaly in {entity}.{attributes[0]}",
                    "entity": entity,
                    "attribute": attributes[0]
                })
        
        return anomalies
    
    def _detect_missing_relationships(self) -> List[Dict[str, Any]]:
        """Detect missing relationships needed for the query."""
        missing_relationships = []
        
        # Check if we need more relationships
        if len(self.current_schema["entities"]) >= 2 and len(self.current_schema["relationships"]) == 0:
            missing_relationships.append({
                "type": "missing_relationship",
                "description": f"Missing relationship between {self.current_schema['entities'][0]} and {self.current_schema['entities'][1]}",
                "entity1": self.current_schema["entities"][0],
                "entity2": self.current_schema["entities"][1]
            })
        
        return missing_relationships
    
    def generate_questions(self) -> List[str]:
        """Generate natural language questions for each detected uncertainty."""
        questions = []
        
        for uncertainty in self.uncertainties:
            if uncertainty["type"] == "entity_alignment":
                questions.append(
                    f"What is the relationship between {uncertainty['entity1']} and {uncertainty['entity2']}?"
                )
            elif uncertainty["type"] == "attribute_value_anomaly":
                questions.append(
                    f"What are the valid values for {uncertainty['attribute']} of {uncertainty['entity']}?"
                )
            elif uncertainty["type"] == "missing_relationship":
                questions.append(
                    f"How are {uncertainty['entity1']} and {uncertainty['entity2']} related?"
                )
        
        return questions
    
    def retrieve_answers(self, questions: List[str]) -> Dict[str, List[str]]:
        """Retrieve answers for generated questions from documents."""
        answers = {}
        for question in questions:
            # Simple implementation that looks for relevant sentences in documents
            relevant_docs = []
            for doc in self.documents:
                if any(keyword in doc.lower() for keyword in question.lower().split()[:3]):
                    relevant_docs.append(doc[:500] + "...")  # Limit to 500 chars per doc
            answers[question] = relevant_docs[:2]  # Return max 2 relevant docs
        return answers
    
    def update_schema(self, answers: Dict[str, List[str]]) -> dict:
        """Update current schema based on retrieved answers."""
        # Simple implementation that adds relationships based on answers
        for question, retrieved_docs in answers.items():
            if "relationship between" in question or "how are" in question:
                # Look for relationship keywords in answers
                for doc in retrieved_docs:
                    if "has" in doc.lower():
                        # Simple rule: if "has" is found, add a relationship
                        entities = self.current_schema["entities"]
                        if len(entities) >= 2:
                            relationship = {
                                "from": entities[0],
                                "type": "has",
                                "to": entities[1]
                            }
                            if relationship not in self.current_schema["relationships"]:
                                self.current_schema["relationships"].append(relationship)
        
        return self.current_schema
    
    def check_convergence(self) -> bool:
        """Check if schema has converged."""
        # Convergence criteria:
        # 1. No uncertainties detected
        # 2. Maximum iterations reached
        # 3. Schema hasn't changed significantly (simplified: check if entities count is stable)
        
        if not self.uncertainties:
            return True
        
        if self.iteration_count >= self.max_iterations:
            return True
        
        # Simplified check: if we have at least 2 entities and 1 relationship
        if len(self.current_schema["entities"]) >= 2 and len(self.current_schema["relationships"]) >= 1:
            return True
        
        return False
    
    def run(self) -> dict:
        """Run the full interactive schema discovery pipeline."""
        # Step 1: Generate initial schema
        self.generate_initial_schema()
        
        while True:
            self.iteration_count += 1
            
            # Step 2: Detect uncertainties
            self.detect_uncertainties()
            
            # Step 3: Check convergence
            if self.check_convergence():
                break
            
            # Step 4: Generate questions for uncertainties
            questions = self.generate_questions()
            
            # Step 5: Retrieve answers
            answers = self.retrieve_answers(questions)
            
            # Step 6: Update schema
            self.update_schema(answers)
        
        return self.current_schema


# Test the implementation
if __name__ == "__main__":
    # Sample query and documents
    query = "What companies produce smartphones?"
    documents = [
        "Apple produces iPhone 15 and iPhone 15 Pro smartphones.",
        "Samsung makes Galaxy Z Fold5 and Galaxy S23 smartphones.",
        "Google manufactures Pixel 8 and Pixel 8 Pro smartphones.",
        "Microsoft is a software company that also makes Surface devices."
    ]
    
    # Create and run the schema discoverer
    discoverer = InteractiveSchemaDiscoverer(
        query=query,
        documents=documents
    )
    
    final_schema = discoverer.run()
    print("Final Schema:")
    print(f"Entities: {final_schema['entities']}")
    print(f"Attributes: {final_schema['attributes']}")
    print(f"Relationships: {final_schema['relationships']}")
