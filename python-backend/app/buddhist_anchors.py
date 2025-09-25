"""
Buddhist Anchor Extraction System
Identifies and categorizes Buddhist concepts, terms, and teachings in text chunks.
"""
import re
from typing import Dict, List, Set, Tuple, Optional
from loguru import logger
from dataclasses import dataclass

@dataclass
class BuddhistAnchor:
    term: str
    category: str
    confidence: float
    context: str = ""
    chunk_id: str = ""
    aliases: List[str] = None
    related_terms: List[str] = None

class BuddhistAnchorExtractor:
    def __init__(self):
        # Build taxonomy dynamically from PDF glossaries instead of hardcoded terms
        self.document_glossaries = {}  # Store glossaries per document
        self.unified_glossary = {}  # Combined glossary from all documents
        self.dynamic_taxonomy = {}  # Built from PDF glossaries
        self.cross_references = {}  # Built from related terms in glossaries

    def _build_anchor_taxonomy(self) -> Dict[str, Dict]:
        """Comprehensive Buddhist term taxonomy organized by category"""
        return {
            "core_doctrines": {
                "Four Noble Truths": {
                    "aliases": ["4 Noble Truths", "Arya-satya", "Cattāri ariyasaccāni"],
                    "weight": 1.0,
                    "pattern": r"(?:Four|4)\s+Noble\s+Truth[s]?|Arya[- ]?satya|Catt[āa]ri\s+ariyasacc[āa]ni"
                },
                "Noble Eightfold Path": {
                    "aliases": ["Eightfold Path", "8-fold Path", "Middle Way", "Arya Ashtanga Marga"],
                    "weight": 1.0,
                    "pattern": r"(?:Noble\s+)?(?:Eight|8)[-\s]?fold\s+Path|Middle\s+Way|Arya\s+Ashtanga\s+Marga"
                },
                "Three Jewels": {
                    "aliases": ["Three Refuges", "Triple Gem", "Triratna", "Buddha Dharma Sangha"],
                    "weight": 1.0,
                    "pattern": r"Three\s+(?:Jewels|Refuges)|Triple\s+Gem|Triratna|Buddha[,\s]+Dharma[,\s]+Sangha"
                },
                "Dependent Origination": {
                    "aliases": ["Pratityasamutpada", "Conditioned Genesis", "12 Links", "Chain of Causation"],
                    "weight": 0.9,
                    "pattern": r"Dependent\s+Origination|Pratityasamutpada|Conditioned\s+Genesis|(?:Twelve|12)\s+Links|Chain\s+of\s+Causation"
                }
            },

            "meditation_practices": {
                "Vipassana": {
                    "aliases": ["Insight Meditation", "Mindfulness Meditation"],
                    "weight": 0.8,
                    "pattern": r"Vipassan[āa]|Insight\s+Meditation|Mindfulness\s+Meditation"
                },
                "Samatha": {
                    "aliases": ["Calm Abiding", "Concentration Meditation", "Shamatha"],
                    "weight": 0.8,
                    "pattern": r"Samath[āa]|Shamath[āa]|Calm\s+Abiding|Concentration\s+Meditation"
                },
                "Mindfulness": {
                    "aliases": ["Sati", "Smrti", "Present Moment Awareness"],
                    "weight": 0.9,
                    "pattern": r"Mindfulness|Sati(?:\s|$)|Smrti|Present\s+Moment\s+Awareness"
                },
                "Four Foundations of Mindfulness": {
                    "aliases": ["Satipatthana", "Cattāro Satipaṭṭhānā"],
                    "weight": 0.8,
                    "pattern": r"(?:Four\s+)?Foundations\s+of\s+Mindfulness|Satipatthana|Catt[āa]ro\s+Satipa[ṭt][ṭt]h[āa]n[āa]"
                }
            },

            "philosophical_concepts": {
                "Emptiness": {
                    "aliases": ["Śūnyatā", "Sunyata", "Voidness"],
                    "weight": 0.9,
                    "pattern": r"Emptiness|[SŚ][ūu]nyat[āa]|Voidness"
                },
                "Non-self": {
                    "aliases": ["Anatta", "Anatman", "No-self"],
                    "weight": 0.9,
                    "pattern": r"Non[-\s]?self|Anatt[āa]|Anatman|No[-\s]?self"
                },
                "Impermanence": {
                    "aliases": ["Anicca", "Anitya", "Transience"],
                    "weight": 0.8,
                    "pattern": r"Impermanence|Anicc[āa]|Anity[āa]|Transience"
                },
                "Suffering": {
                    "aliases": ["Dukkha", "Duhkha", "Unsatisfactoriness"],
                    "weight": 0.8,
                    "pattern": r"Suffering|Dukkh[āa]|Duhkh[āa]|Unsatisfactoriness"
                },
                "Buddha Nature": {
                    "aliases": ["Tathāgatagarbha", "Tathagatagarbha", "Inherent Buddha"],
                    "weight": 0.8,
                    "pattern": r"Buddha\s+Nature|Tath[āa]gatagarbha|Inherent\s+Buddha"
                }
            },

            "beings_and_realms": {
                "Buddha": {
                    "aliases": ["Gautama Buddha", "Siddhartha", "Shakyamuni", "Awakened One"],
                    "weight": 1.0,
                    "pattern": r"(?:Gautama\s+)?Buddha|Siddhartha|Shakyamuni|Awakened\s+One"
                },
                "Bodhisattva": {
                    "aliases": ["Enlightenment Being", "Buddha-to-be"],
                    "weight": 0.8,
                    "pattern": r"Bodhisattva|Enlightenment\s+Being|Buddha[-\s]?to[-\s]?be"
                },
                "Arhat": {
                    "aliases": ["Arahant", "Worthy One", "Perfected One"],
                    "weight": 0.7,
                    "pattern": r"Arhat|Arahant|Worthy\s+One|Perfected\s+One"
                },
                "Six Realms": {
                    "aliases": ["Six Worlds", "Samsaric Realms", "Gati"],
                    "weight": 0.7,
                    "pattern": r"Six\s+(?:Realms|Worlds)|Samsaric\s+Realms|Gati"
                }
            },

            "scriptures_and_texts": {
                "Pali Canon": {
                    "aliases": ["Tipitaka", "Tripitaka", "Three Baskets"],
                    "weight": 0.8,
                    "pattern": r"Pali\s+Canon|[TṬ]ipitaka|[TṬ]ripitaka|Three\s+Baskets"
                },
                "Lotus Sutra": {
                    "aliases": ["Saddharma Pundarika", "White Lotus"],
                    "weight": 0.7,
                    "pattern": r"Lotus\s+Sutra|Saddharma\s+Pundarika|White\s+Lotus\s+Sutra"
                },
                "Heart Sutra": {
                    "aliases": ["Prajnaparamita Heart Sutra", "Hridaya"],
                    "weight": 0.7,
                    "pattern": r"Heart\s+Sutra|Prajnaparamita\s+Heart\s+Sutra|Hridaya"
                },
                "Dhammapada": {
                    "aliases": ["Path of Dharma", "Verses of Doctrine"],
                    "weight": 0.7,
                    "pattern": r"Dhammapada|Path\s+of\s+Dharma|Verses\s+of\s+Doctrine"
                }
            },

            "practices_and_virtues": {
                "Compassion": {
                    "aliases": ["Karuna", "Loving-kindness", "Metta"],
                    "weight": 0.9,
                    "pattern": r"Compassion|Karun[āa]|Loving[-\s]?kindness|Mett[āa]"
                },
                "Wisdom": {
                    "aliases": ["Prajna", "Panna", "Transcendent Wisdom"],
                    "weight": 0.9,
                    "pattern": r"(?:Transcendent\s+)?Wisdom|Prajn[āa]|Pann[āa]"
                },
                "Generosity": {
                    "aliases": ["Dana", "Giving", "Charity"],
                    "weight": 0.7,
                    "pattern": r"Generosity|D[āa]na|(?:Buddhist\s+)?Giving|Charity"
                },
                "Ethics": {
                    "aliases": ["Sila", "Precepts", "Moral Conduct"],
                    "weight": 0.8,
                    "pattern": r"(?:Buddhist\s+)?Ethics|[SŚ][īi]la|Precepts|Moral\s+Conduct"
                }
            }
        }

    def _build_cross_references(self) -> Dict[str, List[str]]:
        """Define relationships between Buddhist concepts"""
        return {
            "Four Noble Truths": ["Noble Eightfold Path", "Suffering", "Impermanence", "Dependent Origination"],
            "Noble Eightfold Path": ["Four Noble Truths", "Mindfulness", "Ethics", "Wisdom"],
            "Dependent Origination": ["Four Noble Truths", "Impermanence", "Non-self", "Emptiness"],
            "Vipassana": ["Mindfulness", "Four Foundations of Mindfulness", "Non-self", "Impermanence"],
            "Samatha": ["Mindfulness", "Vipassana", "Concentration"],
            "Emptiness": ["Non-self", "Dependent Origination", "Wisdom", "Buddha Nature"],
            "Non-self": ["Emptiness", "Impermanence", "Suffering", "Vipassana"],
            "Compassion": ["Wisdom", "Bodhisattva", "Loving-kindness", "Generosity"],
            "Buddha": ["Three Jewels", "Buddha Nature", "Bodhisattva"],
            "Bodhisattva": ["Buddha", "Compassion", "Wisdom", "Buddha Nature"],
            "Mindfulness": ["Vipassana", "Four Foundations of Mindfulness", "Noble Eightfold Path"],
            "Heart Sutra": ["Emptiness", "Wisdom", "Prajnaparamita"],
            "Lotus Sutra": ["Buddha Nature", "Bodhisattva", "Buddha"]
        }

    def extract_anchors(self, text: str, chunk_id: str) -> List[BuddhistAnchor]:
        """Extract Buddhist anchors from text chunk using glossary terms only"""
        return self.extract_anchors_with_glossary(text, chunk_id)

    def _calculate_confidence(self, matched_term: str, context: str, base_weight: float) -> float:
        """Calculate confidence score for anchor based on context"""
        confidence = base_weight

        # Boost confidence for proper capitalization
        if matched_term[0].isupper():
            confidence += 0.1

        # Boost confidence for Buddhist context words
        buddhist_context_words = [
            'dharma', 'sangha', 'meditation', 'enlightenment', 'awakening',
            'liberation', 'nirvana', 'samsara', 'karma', 'rebirth',
            'monastery', 'monk', 'nun', 'teaching', 'practice'
        ]

        context_lower = context.lower()
        context_boost = sum(0.05 for word in buddhist_context_words if word in context_lower)
        confidence += min(context_boost, 0.2)  # Cap context boost at 0.2

        # Penalize if appears in non-Buddhist context
        non_buddhist_contexts = ['christian', 'islam', 'jewish', 'hindu', 'secular']
        if any(word in context_lower for word in non_buddhist_contexts):
            confidence *= 0.7

        return min(confidence, 1.0)

    def _deduplicate_anchors(self, anchors: List[BuddhistAnchor]) -> List[BuddhistAnchor]:
        """Remove duplicate anchors, keeping highest confidence"""
        seen_terms = {}
        deduplicated = []

        for anchor in anchors:
            if anchor.term not in seen_terms or anchor.confidence > seen_terms[anchor.term].confidence:
                seen_terms[anchor.term] = anchor

        return list(seen_terms.values())

    def find_cross_links(self, anchors: List[BuddhistAnchor], all_document_anchors: Dict[str, List[BuddhistAnchor]]) -> Dict[str, List[str]]:
        """Find cross-links between current chunk and other documents"""
        cross_links = {}
        current_terms = {anchor.term for anchor in anchors}

        for anchor in anchors:
            related_chunks = []

            # Find chunks with related terms
            for related_term in anchor.related_terms:
                for doc_id, doc_anchors in all_document_anchors.items():
                    for doc_anchor in doc_anchors:
                        if doc_anchor.term == related_term and doc_anchor.confidence > 0.6:
                            related_chunks.append(f"{doc_id}#{doc_anchor.term}")

            if related_chunks:
                cross_links[anchor.term] = related_chunks[:5]  # Limit to top 5

        return cross_links

    def get_anchor_summary(self, anchors: List[BuddhistAnchor]) -> Dict[str, int]:
        """Get summary of anchors by category"""
        summary = {}
        for anchor in anchors:
            summary[anchor.category] = summary.get(anchor.category, 0) + 1
        return summary

    def extract_glossary_from_document(self, document_text: str, document_id: str) -> Dict[str, Dict]:
        """Extract glossary terms from document text"""
        logger.info(f"Extracting glossary from document: {document_id}")

        glossary = {}

        # Enhanced glossary section patterns for Buddhist scholarly texts
        glossary_patterns = [
            # Standard "g. Glossary" pattern from contents page structure
            r"(?i)g\.\s*glossary\s*\n(.*?)(?=\n[a-z]\.\s+[A-Z]|\n[A-Z][A-Z\s]*\n|\Z)",
            # Traditional glossary patterns
            r"(?i)glossary\s*\n(.*?)(?=\n[A-Z][A-Z\s]*\n|\Z)",
            r"(?i)definitions?\s*\n(.*?)(?=\n[A-Z][A-Z\s]*\n|\Z)",
            r"(?i)technical\s+terms?\s*\n(.*?)(?=\n[A-Z][A-Z\s]*\n|\Z)",
            r"(?i)vocabulary\s*\n(.*?)(?=\n[A-Z][A-Z\s]*\n|\Z)",
            r"(?i)sanskrit\s+terms?\s*\n(.*?)(?=\n[A-Z][A-Z\s]*\n|\Z)",
            r"(?i)pali\s+terms?\s*\n(.*?)(?=\n[A-Z][A-Z\s]*\n|\Z)",
            r"(?i)tibetan\s+terms?\s*\n(.*?)(?=\n[A-Z][A-Z\s]*\n|\Z)",
            # Abbreviations section (often contains key terms)
            r"(?i)ab\.\s*abbreviations\s*\n(.*?)(?=\n[a-z]\.\s+[A-Z]|\n[A-Z][A-Z\s]*\n|\Z)",
            r"(?i)abbreviations\s*\n(.*?)(?=\n[A-Z][A-Z\s]*\n|\Z)"
        ]

        for pattern in glossary_patterns:
            matches = re.finditer(pattern, document_text, re.DOTALL)
            for match in matches:
                glossary_text = match.group(1)
                terms = self._parse_glossary_section(glossary_text)
                glossary.update(terms)

        # Also look for definition patterns throughout the text
        definition_patterns = [
            # Pattern: "Term (definition)" or "Term: definition"
            r"([A-Za-z][A-Za-z\s]{2,30})\s*[\(:]([^\.]+[\.\)])",
            # Pattern: "Term – definition" or "Term — definition"
            r"([A-Za-z][A-Za-z\s]{2,30})\s*[–—]\s*([^\.]+\.)",
            # Pattern: italicized terms with definitions
            r"\*([A-Za-z][A-Za-z\s]{2,30})\*\s*[–—:]?\s*([^\.]+\.)"
        ]

        for pattern in definition_patterns:
            matches = re.finditer(pattern, document_text)
            for match in matches:
                term = match.group(1).strip()
                definition = match.group(2).strip().rstrip('.')

                # Filter for likely Buddhist terms
                if self._is_likely_buddhist_term(term, definition):
                    glossary[term] = {
                        "definition": definition,
                        "source": "inline_definition",
                        "confidence": 0.7
                    }

        # Also extract terms from key sections (introduction, chapter titles, etc.)
        structural_terms = self._extract_structural_terms(document_text)
        glossary.update(structural_terms)

        logger.info(f"Extracted {len(glossary)} terms from glossary and structural sections")
        self.document_glossaries[document_id] = glossary
        self._update_unified_glossary()

        # Build cross-references after updating glossary
        self.build_cross_references()

        return glossary

    def _parse_glossary_section(self, glossary_text: str) -> Dict[str, Dict]:
        """Parse a formal glossary section"""
        terms = {}

        # Split into potential term-definition pairs
        lines = glossary_text.split('\n')
        current_term = None
        current_definition = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this looks like a new term entry
            if self._looks_like_glossary_term(line):
                # Save previous term if exists
                if current_term and current_definition:
                    terms[current_term] = {
                        "definition": current_definition.strip(),
                        "source": "glossary_section",
                        "confidence": 0.9
                    }

                # Extract term and start of definition
                parts = re.split(r'[:\-–—]', line, 1)
                if len(parts) == 2:
                    current_term = parts[0].strip()
                    current_definition = parts[1].strip()
                else:
                    current_term = line
                    current_definition = ""
            else:
                # Continuation of current definition
                if current_term:
                    current_definition += " " + line

        # Don't forget the last term
        if current_term and current_definition:
            terms[current_term] = {
                "definition": current_definition.strip(),
                "source": "glossary_section",
                "confidence": 0.9
            }

        return terms

    def _looks_like_glossary_term(self, line: str) -> bool:
        """Check if a line looks like a glossary term entry"""
        # Starts with a word, may be followed by pronunciation, then definition
        pattern = r"^[A-Za-z][A-Za-z\s\(\)]{1,40}[:–—\-]"
        return bool(re.match(pattern, line))

    def _is_likely_buddhist_term(self, term: str, definition: str) -> bool:
        """Check if a term/definition pair is likely Buddhist"""
        buddhist_keywords = [
            'buddha', 'dharma', 'meditation', 'mindfulness', 'enlightenment',
            'awakening', 'liberation', 'nirvana', 'samsara', 'karma', 'rebirth',
            'suffering', 'impermanence', 'compassion', 'wisdom', 'monastery',
            'monk', 'nun', 'teaching', 'practice', 'path', 'truth', 'noble',
            'eightfold', 'precept', 'jhana', 'samadhi', 'vipassana'
        ]

        text_to_check = (term + " " + definition).lower()
        return any(keyword in text_to_check for keyword in buddhist_keywords)

    def _update_unified_glossary(self):
        """Update the unified glossary from all document glossaries"""
        self.unified_glossary = {}

        for doc_id, glossary in self.document_glossaries.items():
            for term, data in glossary.items():
                if term in self.unified_glossary:
                    # If term exists, keep the one with higher confidence
                    if data["confidence"] > self.unified_glossary[term]["confidence"]:
                        self.unified_glossary[term] = data
                        self.unified_glossary[term]["sources"] = [doc_id]
                    elif data["confidence"] == self.unified_glossary[term]["confidence"]:
                        # Same confidence, add source
                        if "sources" not in self.unified_glossary[term]:
                            self.unified_glossary[term]["sources"] = []
                        self.unified_glossary[term]["sources"].append(doc_id)
                else:
                    self.unified_glossary[term] = data.copy()
                    self.unified_glossary[term]["sources"] = [doc_id]

    def extract_anchors_with_glossary(self, text: str, chunk_id: str) -> List[BuddhistAnchor]:
        """Extract anchors using document glossaries only"""
        anchors = []

        # Extract anchors from glossary terms only
        for term, term_data in self.unified_glossary.items():
            # Create case-insensitive pattern for the term
            pattern = r'\b' + re.escape(term) + r'\b'
            matches = list(re.finditer(pattern, text, re.IGNORECASE))

            for match in matches:
                # Extract context
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()

                confidence = term_data.get("confidence", 0.8)

                # Determine category based on term characteristics or use glossary_term
                category = self._categorize_glossary_term(term, term_data.get("definition", ""))

                anchor = BuddhistAnchor(
                    term=term,
                    category=category,
                    confidence=confidence,
                    context=context,
                    chunk_id=chunk_id,
                    aliases=[],
                    related_terms=self._find_related_terms(term)
                )
                anchors.append(anchor)

        # Deduplicate and sort
        anchors = self._deduplicate_anchors(anchors)
        anchors.sort(key=lambda x: x.confidence, reverse=True)

        logger.debug(f"Extracted {len(anchors)} glossary-based anchors from chunk {chunk_id}")
        return anchors

    def get_glossary_summary(self) -> Dict[str, int]:
        """Get summary of extracted glossary terms"""
        return {
            "total_terms": len(self.unified_glossary),
            "documents_processed": len(self.document_glossaries),
            "high_confidence_terms": sum(1 for term_data in self.unified_glossary.values()
                                       if term_data.get("confidence", 0) > 0.8)
        }

    def _categorize_glossary_term(self, term: str, definition: str) -> str:
        """Categorize a glossary term based on its definition and characteristics"""
        text_to_analyze = (term + " " + definition).lower()

        # Define category keywords
        category_patterns = {
            "meditation_practice": ["meditation", "mindfulness", "awareness", "concentration", "jhana", "samadhi", "vipassana", "samatha"],
            "core_doctrine": ["truth", "path", "noble", "suffering", "cessation", "origin", "nirvana"],
            "philosophical_concept": ["emptiness", "impermanence", "non-self", "interdependence", "dependent", "nature"],
            "being_or_person": ["buddha", "bodhisattva", "arhat", "monk", "nun", "practitioner", "teacher"],
            "scripture_or_text": ["sutra", "sutta", "text", "scripture", "teaching", "discourse", "commentary"],
            "practice_or_virtue": ["compassion", "wisdom", "generosity", "ethics", "precept", "virtue", "conduct"],
            "place_or_realm": ["realm", "world", "paradise", "monastery", "temple", "place"]
        }

        # Check each category
        for category, keywords in category_patterns.items():
            if any(keyword in text_to_analyze for keyword in keywords):
                return category

        # Default category
        return "glossary_term"

    def _find_related_terms(self, term: str) -> List[str]:
        """Find terms related to the given term based on definition similarity or context"""
        related = []
        if not self.unified_glossary.get(term):
            return related

        term_definition = self.unified_glossary[term].get("definition", "").lower()

        # Simple approach: find terms with shared significant words in definitions
        term_words = set(word for word in term_definition.split() if len(word) > 4)

        for other_term, other_data in self.unified_glossary.items():
            if other_term == term:
                continue

            other_definition = other_data.get("definition", "").lower()
            other_words = set(word for word in other_definition.split() if len(word) > 4)

            # If they share 2+ significant words, consider them related
            shared_words = term_words.intersection(other_words)
            if len(shared_words) >= 2:
                related.append(other_term)

        return related[:5]  # Limit to top 5 related terms

    def build_cross_references(self) -> Dict[str, List[str]]:
        """Build cross-references between all glossary terms"""
        cross_refs = {}
        for term in self.unified_glossary.keys():
            cross_refs[term] = self._find_related_terms(term)

        self.cross_references = cross_refs
        return cross_refs

    def get_term_definition(self, term: str) -> Optional[str]:
        """Get definition for a specific term"""
        if term in self.unified_glossary:
            return self.unified_glossary[term].get("definition")
        return None

    def get_terms_by_category(self, category: str) -> List[str]:
        """Get all terms in a specific category"""
        terms = []
        for term, term_data in self.unified_glossary.items():
            if self._categorize_glossary_term(term, term_data.get("definition", "")) == category:
                terms.append(term)
        return terms

    def _extract_structural_terms(self, document_text: str) -> Dict[str, Dict]:
        """Extract key terms from structural elements like chapter titles, introductions"""
        terms = {}

        # Extract from introduction section
        intro_pattern = r"(?i)i\.\s*introduction\s*\n(.*?)(?=\n[a-z0-9]\.\s+[A-Z]|tr\.\s+Translation|\Z)"
        intro_matches = re.finditer(intro_pattern, document_text, re.DOTALL)

        for match in intro_matches:
            intro_text = match.group(1)
            # Look for capitalized Buddhist terms in introduction
            intro_terms = self._extract_terms_from_text(intro_text, "introduction")
            terms.update(intro_terms)

        # Extract from chapter/section titles that contain Buddhist concepts
        chapter_patterns = [
            r"(?i)·\s+([A-Z][^·\n]*(?:Buddha|Dharma|Sangha|Meditation|Enlightenment|Awakening|Sutra|Sutta)[^·\n]*)",
            r"(?i)Chapter\s+\d+[:\.\-]\s*([A-Z][^\n]*(?:Buddha|Dharma|Sangha|Meditation|Enlightenment|Awakening|Sutra|Sutta)[^\n]*)",
            r"(?i)\d+\.[A-Z]\s+([A-Z][^\n]*(?:Buddha|Dharma|Sangha|Meditation|Enlightenment|Awakening|Sutra|Sutta)[^\n]*)"
        ]

        for pattern in chapter_patterns:
            matches = re.finditer(pattern, document_text)
            for match in matches:
                title = match.group(1).strip()
                if len(title) < 100:  # Reasonable title length
                    # Extract individual terms from the title
                    title_terms = self._extract_terms_from_text(title, "chapter_title")
                    terms.update(title_terms)

        # Look for Buddha names and specific textual references
        buddha_name_pattern = r"(?i)(Buddha\s+\w+|Tathāgata|Bhagavat|Śākyamuni|Maitreya|Amitābha|Avalokiteśvara)"
        buddha_matches = re.finditer(buddha_name_pattern, document_text)
        for match in buddha_matches:
            name = match.group(1).strip()
            terms[name] = {
                "definition": f"A Buddha or Buddhist figure mentioned in this text.",
                "source": "structural_extraction",
                "confidence": 0.6
            }

        logger.debug(f"Extracted {len(terms)} structural terms")
        return terms

    def _extract_terms_from_text(self, text: str, source_type: str) -> Dict[str, Dict]:
        """Extract Buddhist terms from a text section"""
        terms = {}

        # Look for capitalized terms that might be Buddhist concepts
        # Focus on terms that are likely to be proper nouns or technical terms
        term_patterns = [
            r"\b([A-Z][a-z]*(?:\s+[A-Z][a-z]*){0,2})\b",  # Capitalized terms (1-3 words)
            r"\b([A-Z][a-zāīūṛṅñṭḍṇḷśṣ]+)\b",  # Single capitalized words with diacritics
        ]

        for pattern in term_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                term = match.group(1).strip()

                # Filter criteria for Buddhist terms
                if (len(term) >= 4 and  # Minimum length
                    not term.lower() in ['this', 'that', 'they', 'there', 'then', 'thus', 'the', 'these', 'those'] and
                    self._looks_like_buddhist_term(term)):

                    # Extract surrounding context for definition
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    context = text[start:end].strip()

                    terms[term] = {
                        "definition": f"Buddhist term or concept mentioned in {source_type}: {context[:150]}...",
                        "source": source_type,
                        "confidence": 0.5
                    }

        return terms

    def _looks_like_buddhist_term(self, term: str) -> bool:
        """Check if a term looks like it could be Buddhist"""
        term_lower = term.lower()

        # Buddhist language indicators
        buddhist_indicators = [
            # Sanskrit/Pali endings
            'a', 'ā', 'i', 'ī', 'u', 'ū', 'e', 'o',
            # Common Buddhist word parts
            'dharma', 'buddha', 'bodhi', 'sangha', 'karma', 'sutra', 'sutta',
            'muni', 'gata', 'patra', 'ratna', 'mani', 'padme', 'hum',
            # Tibetan indicators
            'pa', 'ba', 'ma', 'wa', 'tse', 'che', 'je', 'la'
        ]

        # Check if term contains diacritical marks (common in Buddhist texts)
        if any(char in term for char in 'āīūṛṅñṭḍṇḷśṣḥṃ'):
            return True

        # Check if term ends with common Buddhist suffixes
        for indicator in buddhist_indicators:
            if term_lower.endswith(indicator):
                return True

        # Check if term contains Buddhist word parts
        for indicator in ['buddha', 'dharma', 'sangha', 'bodhi', 'karma', 'sutra', 'mani', 'padme']:
            if indicator in term_lower:
                return True

        return False