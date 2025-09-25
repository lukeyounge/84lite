import fitz
import re
from typing import List, Dict, Tuple
from pathlib import Path
from loguru import logger
import hashlib
from datetime import datetime
from .buddhist_anchors import BuddhistAnchorExtractor

class BuddhistTextChunk:
    def __init__(self, content: str, page_num: int, chunk_id: str,
                 source_file: str, chunk_type: str = "paragraph",
                 metadata: Dict = None, anchors: List = None,
                 cross_links: Dict = None):
        self.content = content.strip()
        self.page_num = page_num
        self.chunk_id = chunk_id
        self.source_file = source_file
        self.chunk_type = chunk_type
        self.metadata = metadata or {}
        self.anchors = anchors or []
        self.cross_links = cross_links or {}
        self.word_count = len(content.split())

class PDFProcessor:
    def __init__(self):
        self.anchor_extractor = BuddhistAnchorExtractor()
        self.buddhist_section_patterns = [
            r"^\d+\.\s+",  # Numbered sections (1. 2. 3.)
            r"^Chapter\s+\d+",  # Chapters
            r"^Part\s+[IVX]+",  # Roman numeral parts
            r"^\[.*?\]",  # Bracketed sections [MN 1], [SN 12.1], etc.
            r"^Sutta\s+\d+",  # Sutta numbers
            r"^Thus\s+have\s+I\s+heard",  # Traditional opening
            r"^At\s+one\s+time",  # Common sutta opening
            r"^The\s+Blessed\s+One\s+said",  # Buddha speaking
            r"^\*\*.*?\*\*",  # Bold headings
            r"^[A-Z][A-Z\s]{3,}$",  # ALL CAPS headings
        ]

        self.section_break_patterns = [
            r"\n\s*\n\s*\n",  # Multiple line breaks
            r"---+",  # Horizontal lines
            r"===+",  # Emphasis lines
            r"\*\*\*+",  # Asterisk separators
        ]

        self.buddhist_terms = {
            "pali": ["dhamma", "sutta", "vinaya", "abhidhamma", "nirvana", "samsara",
                    "karma", "jhana", "vipassana", "samadhi", "metta", "mudita",
                    "karuna", "upekkha", "anicca", "dukkha", "anatta"],
            "sanskrit": ["dharma", "sutra", "nirvana", "samsara", "karma", "dhyana",
                        "vipashyana", "samadhi", "maitri", "mudita", "karuna",
                        "upeksha", "anitya", "duhkha", "anatman"],
            "english": ["mindfulness", "meditation", "awakening", "enlightenment",
                       "compassion", "wisdom", "suffering", "impermanence",
                       "interdependence", "emptiness", "bodhisattva"]
        }

    def health_check(self) -> Dict:
        return {"status": "healthy", "service": "pdf_processor"}

    def process_pdf(self, pdf_path: str) -> Dict:
        logger.info(f"Processing PDF: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
            chunks = []

            total_pages = len(doc)
            full_text = ""

            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                text = page.get_text()
                full_text += f"\n--- Page {page_num + 1} ---\n{text}"

                page_chunks = self._chunk_page(text, page_num, pdf_path)
                chunks.extend(page_chunks)

            doc.close()

            # Extract glossary from the full document text
            document_id = Path(pdf_path).stem
            glossary = self.anchor_extractor.extract_glossary_from_document(full_text, document_id)
            logger.info(f"Extracted {len(glossary)} glossary terms from {document_id}")

            filtered_chunks = self._filter_meaningful_chunks(chunks)

            document_info = {
                "filename": Path(pdf_path).name,
                "pages": total_pages,
                "total_chunks": len(chunks),
                "meaningful_chunks": len(filtered_chunks),
                "processing_date": datetime.now().isoformat(),
                "document_hash": self._generate_document_hash(full_text),
                "detected_language": self._detect_buddhist_language(full_text),
                "estimated_tradition": self._estimate_tradition(full_text),
                "glossary_terms_extracted": len(glossary),
                "glossary_summary": self.anchor_extractor.get_glossary_summary()
            }

            logger.info(f"Processed {total_pages} pages into {len(filtered_chunks)} chunks")
            return {
                "chunks": filtered_chunks,
                "document_info": document_info
            }

        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            raise

    def _chunk_page(self, text: str, page_num: int, source_file: str) -> List[BuddhistTextChunk]:
        if not text.strip():
            return []

        chunks = []

        sections = self._split_into_sections(text)

        for i, section in enumerate(sections):
            if not section.strip():
                continue

            section_type = self._identify_section_type(section)

            if len(section.split()) > 300:
                sub_chunks = self._split_long_section(section, page_num, source_file, section_type)
                chunks.extend(sub_chunks)
            else:
                chunk_id = self._generate_chunk_id(section, page_num, i)
                # Extract Buddhist anchors from this chunk using both taxonomy and glossaries
                anchors = self.anchor_extractor.extract_anchors_with_glossary(section, chunk_id)

                metadata = {
                    "section_type": section_type,
                    "position_in_page": i,
                    "buddhist_terms_count": self._count_buddhist_terms(section),
                    "anchor_count": len(anchors),
                    "anchor_categories": ", ".join(set(anchor.category for anchor in anchors))
                }

                chunk = BuddhistTextChunk(
                    content=section,
                    page_num=page_num,
                    chunk_id=chunk_id,
                    source_file=source_file,
                    chunk_type=section_type,
                    metadata=metadata,
                    anchors=anchors
                )
                chunks.append(chunk)

        return chunks

    def _split_into_sections(self, text: str) -> List[str]:
        for pattern in self.section_break_patterns:
            text = re.sub(pattern, "SECTION_BREAK", text)

        sections = text.split("SECTION_BREAK")

        final_sections = []
        for section in sections:
            if self._looks_like_new_section(section):
                final_sections.append(section)
            elif final_sections:
                final_sections[-1] += "\n" + section
            else:
                final_sections.append(section)

        return [s.strip() for s in final_sections if s.strip()]

    def _looks_like_new_section(self, text: str) -> bool:
        first_line = text.strip().split('\n')[0] if text.strip() else ""

        for pattern in self.buddhist_section_patterns:
            if re.match(pattern, first_line, re.IGNORECASE):
                return True

        return len(first_line.split()) <= 10 and any(
            char.isupper() for char in first_line
        )

    def _identify_section_type(self, text: str) -> str:
        first_line = text.strip().split('\n')[0] if text.strip() else ""

        if re.match(r"^\[.*?\]", first_line):
            return "sutta_reference"
        elif re.match(r"^Chapter\s+\d+", first_line, re.IGNORECASE):
            return "chapter"
        elif re.match(r"^Thus\s+have\s+I\s+heard", first_line, re.IGNORECASE):
            return "sutta_opening"
        elif "The Blessed One said" in text or "The Buddha said" in text:
            return "buddha_teaching"
        elif any(term in text.lower() for term in ["question", "asked", "reply"]):
            return "dialogue"
        elif re.match(r"^\*\*.*?\*\*", first_line):
            return "heading"
        else:
            return "paragraph"

    def _split_long_section(self, section: str, page_num: int, source_file: str,
                          section_type: str) -> List[BuddhistTextChunk]:
        chunks = []
        paragraphs = section.split('\n\n')

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            if len((current_chunk + para).split()) <= 250:
                current_chunk += "\n\n" + para if current_chunk else para
            else:
                if current_chunk:
                    chunk_id = self._generate_chunk_id(current_chunk, page_num, chunk_index)
                    anchors = self.anchor_extractor.extract_anchors_with_glossary(current_chunk, chunk_id)

                    metadata = {
                        "section_type": section_type,
                        "is_continuation": chunk_index > 0,
                        "buddhist_terms_count": self._count_buddhist_terms(current_chunk),
                        "anchor_count": len(anchors),
                        "anchor_categories": ", ".join(set(anchor.category for anchor in anchors))
                    }

                    chunk = BuddhistTextChunk(
                        content=current_chunk,
                        page_num=page_num,
                        chunk_id=chunk_id,
                        source_file=source_file,
                        chunk_type=section_type,
                        metadata=metadata,
                        anchors=anchors
                    )
                    chunks.append(chunk)
                    chunk_index += 1

                current_chunk = para

        if current_chunk:
            chunk_id = self._generate_chunk_id(current_chunk, page_num, chunk_index)
            anchors = self.anchor_extractor.extract_anchors_with_glossary(current_chunk, chunk_id)

            metadata = {
                "section_type": section_type,
                "is_continuation": chunk_index > 0,
                "buddhist_terms_count": self._count_buddhist_terms(current_chunk),
                "anchor_count": len(anchors),
                "anchor_categories": ", ".join(set(anchor.category for anchor in anchors))
            }

            chunk = BuddhistTextChunk(
                content=current_chunk,
                page_num=page_num,
                chunk_id=chunk_id,
                source_file=source_file,
                chunk_type=section_type,
                metadata=metadata,
                anchors=anchors
            )
            chunks.append(chunk)

        return chunks

    def _filter_meaningful_chunks(self, chunks: List[BuddhistTextChunk]) -> List[BuddhistTextChunk]:
        meaningful_chunks = []

        for chunk in chunks:
            if self._is_meaningful_content(chunk):
                meaningful_chunks.append(chunk)

        return meaningful_chunks

    def _is_meaningful_content(self, chunk: BuddhistTextChunk) -> bool:
        content = chunk.content.lower()

        if chunk.word_count < 10:
            return False

        if len([c for c in content if c.isalpha()]) / len(content) < 0.5:
            return False

        if chunk.metadata.get("buddhist_terms_count", 0) > 0:
            return True

        meaningful_patterns = [
            r"teaching", r"dharma", r"dhamma", r"meditation", r"mindfulness",
            r"suffering", r"compassion", r"wisdom", r"path", r"practice",
            r"buddha", r"awakening", r"enlightenment", r"liberation"
        ]

        if any(re.search(pattern, content) for pattern in meaningful_patterns):
            return True

        return chunk.word_count >= 20

    def _count_buddhist_terms(self, text: str) -> int:
        text_lower = text.lower()
        count = 0

        for language, terms in self.buddhist_terms.items():
            for term in terms:
                count += len(re.findall(r'\b' + re.escape(term.lower()) + r'\b', text_lower))

        return count

    def _detect_buddhist_language(self, text: str) -> str:
        text_lower = text.lower()
        pali_count = sum(1 for term in self.buddhist_terms["pali"]
                        if re.search(r'\b' + re.escape(term) + r'\b', text_lower))
        sanskrit_count = sum(1 for term in self.buddhist_terms["sanskrit"]
                           if re.search(r'\b' + re.escape(term) + r'\b', text_lower))

        if pali_count > sanskrit_count:
            return "theravada_pali"
        elif sanskrit_count > pali_count:
            return "mahayana_sanskrit"
        else:
            return "english_general"

    def _estimate_tradition(self, text: str) -> str:
        text_lower = text.lower()

        theravada_indicators = ["sutta", "vinaya", "abhidhamma", "bhikkhu", "nibbana", "vipassana"]
        mahayana_indicators = ["sutra", "bodhisattva", "emptiness", "compassion", "wisdom"]
        zen_indicators = ["koan", "zazen", "satori", "zen", "dharma transmission"]
        tibetan_indicators = ["lama", "tulku", "bardo", "tantra", "vajrayana"]

        scores = {
            "theravada": sum(1 for term in theravada_indicators if term in text_lower),
            "mahayana": sum(1 for term in mahayana_indicators if term in text_lower),
            "zen": sum(1 for term in zen_indicators if term in text_lower),
            "tibetan": sum(1 for term in tibetan_indicators if term in text_lower)
        }

        if max(scores.values()) == 0:
            return "general_buddhist"

        return max(scores, key=scores.get)

    def _generate_chunk_id(self, content: str, page_num: int, chunk_index: int) -> str:
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"p{page_num}_{chunk_index}_{content_hash}"

    def _generate_document_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]