import os
import json
import hashlib
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import re
from dataclasses import dataclass, asdict

import PyPDF2
import pdfplumber
import tiktoken


@dataclass
class LocationMetadata:
    """Stores location and structure information for each chunk"""
    page_numbers: List[int]          # Pages this chunk spans
    start_page: int                   # First page of chunk
    end_page: int                     # Last page of chunk
    section: Optional[str]            # Main section (e.g., "Chapter 1")
    subsection: Optional[str]         # Subsection (e.g., "1.1 Introduction")
    paragraph_range: Tuple[int, int]  # Start and end paragraph numbers
    position: Dict                    # Position in document
    hierarchy_level: int              # 0=title, 1=chapter, 2=section, etc.
    outline_path: List[str]          # Full path in doc structure


@dataclass
class RelationshipMetadata:
    """Stores relationship information between chunks"""
    chunk_id: int
    previous_chunk_id: Optional[int]
    next_chunk_id: Optional[int]
    parent_chunk_id: Optional[int]      # For hierarchical relationships
    child_chunk_ids: List[int]          # Sub-chunks if any
    related_chunk_ids: List[int]        # Semantically related chunks
    references_to: List[str]            # What this chunk references
    referenced_by_ids: List[int]        # Chunks that reference this one
    continuation_of: Optional[int]      # If split mid-sentence/paragraph
    continues_in: Optional[int]         # Next part if split


class EnhancedPDFIndexer:
    """
    Enhanced PDF indexer with location and relationship tracking
    """
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.section_patterns = {
            'chapter': r'(?i)^chapter\s+(\d+|[IVX]+)',
            'section': r'(?i)^(?:\d+\.)+\s+\w+',
            'part': r'(?i)^part\s+(\d+|[IVX]+)',
            'article': r'(?i)^article\s+(\d+|[IVX]+)',
            'heading': r'^[A-Z][^.!?]*$'  # All caps or title case line
        }
        
    def extract_with_location(self, pdf_path: str) -> Dict:
        """
        Extract text with detailed location information
        """
        pages_data = []
        document_outline = []
        
        with pdfplumber.open(pdf_path) as pdf:
            # Try to extract document outline/bookmarks
            try:
                with open(pdf_path, 'rb') as file:
                    pypdf_reader = PyPDF2.PdfReader(file)
                    if pypdf_reader.outline:
                        document_outline = self._parse_outline(pypdf_reader.outline)
            except:
                pass
            
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                
                # Extract paragraphs
                paragraphs = self._extract_paragraphs(page_text)
                
                # Detect sections and headings
                sections = self._detect_sections(page_text)
                
                pages_data.append({
                    'page_number': page_num,
                    'text': page_text,
                    'paragraphs': paragraphs,
                    'sections': sections,
                    'char_count': len(page_text),
                    'word_count': len(page_text.split()),
                    'bbox': {
                        'width': float(page.width),
                        'height': float(page.height)
                    }
                })
        
        return {
            'pages': pages_data,
            'outline': document_outline,
            'total_pages': len(pages_data)
        }
    
    def _extract_paragraphs(self, text: str) -> List[Dict]:
        """
        Extract paragraphs with their positions
        """
        paragraphs = []
        # Split by double newlines or indentation patterns
        para_splits = re.split(r'\n\s*\n', text)
        
        char_position = 0
        for i, para in enumerate(para_splits):
            if para.strip():
                paragraphs.append({
                    'id': i,
                    'text': para.strip(),
                    'start_char': char_position,
                    'end_char': char_position + len(para),
                    'word_count': len(para.split())
                })
            char_position += len(para) + 2  # +2 for the split newlines
            
        return paragraphs
    
    def _detect_sections(self, text: str) -> List[Dict]:
        """
        Detect section headers and structure
        """
        sections = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
                
            for section_type, pattern in self.section_patterns.items():
                if re.match(pattern, line_stripped):
                    sections.append({
                        'type': section_type,
                        'text': line_stripped,
                        'line_number': line_num,
                        'hierarchy_level': self._get_hierarchy_level(section_type)
                    })
                    break
                    
        return sections
    
    def _get_hierarchy_level(self, section_type: str) -> int:
        """
        Determine hierarchy level based on section type
        """
        hierarchy = {
            'part': 1,
            'chapter': 2,
            'article': 2,
            'section': 3,
            'heading': 4
        }
        return hierarchy.get(section_type, 5)
    
    def _parse_outline(self, outline, level=0) -> List[Dict]:
        """
        Parse PDF outline/bookmarks
        """
        result = []
        for item in outline:
            if isinstance(item, list):
                result.extend(self._parse_outline(item, level + 1))
            else:
                result.append({
                    'title': item.title,
                    'level': level,
                    'page': item.page.idnum if hasattr(item, 'page') else None
                })
        return result
    
    def create_chunks_with_metadata(self, pdf_data: Dict) -> List[Dict]:
        """
        Create chunks with location and relationship metadata
        """
        chunks = []
        chunk_id = 0
        current_section = None
        current_subsection = None
        full_text = ""
        
        # Build full text and section map
        section_map = {}  # chunk_id -> section info
        
        for page_data in pdf_data['pages']:
            page_num = page_data['page_number']
            page_text = page_data['text']
            full_text += f"\n--- Page {page_num} ---\n{page_text}"
            
            # Track sections
            for section in page_data['sections']:
                if section['hierarchy_level'] <= 2:
                    current_section = section['text']
                    current_subsection = None
                elif section['hierarchy_level'] == 3:
                    current_subsection = section['text']
        
        # Create chunks with overlap
        sentences = re.split(r'(?<=[.!?])\s+', full_text)
        current_chunk_text = ""
        current_pages = set()
        paragraph_counter = 0
        
        for i, sentence in enumerate(sentences):
            # Extract page number from sentence if present
            page_marker = re.search(r'--- Page (\d+) ---', sentence)
            if page_marker:
                current_pages.add(int(page_marker.group(1)))
            
            current_chunk_text += " " + sentence
            current_tokens = len(self.encoding.encode(current_chunk_text))
            
            if current_tokens >= self.chunk_size:
                # Create chunk with metadata
                chunk = self._create_chunk(
                    chunk_id=chunk_id,
                    text=current_chunk_text.strip(),
                    pages=list(current_pages),
                    section=current_section,
                    subsection=current_subsection,
                    position_in_doc=i / len(sentences),
                    paragraph_range=(paragraph_counter, paragraph_counter + current_chunk_text.count('\n\n'))
                )
                chunks.append(chunk)
                
                # Prepare next chunk with overlap
                overlap_sentences = sentences[max(0, i - 5):i + 1]  # Last 5 sentences
                current_chunk_text = " ".join(overlap_sentences)
                chunk_id += 1
                paragraph_counter += current_chunk_text.count('\n\n')
        
        # Add final chunk
        if current_chunk_text.strip():
            chunk = self._create_chunk(
                chunk_id=chunk_id,
                text=current_chunk_text.strip(),
                pages=list(current_pages),
                section=current_section,
                subsection=current_subsection,
                position_in_doc=1.0,
                paragraph_range=(paragraph_counter, paragraph_counter + current_chunk_text.count('\n\n'))
            )
            chunks.append(chunk)
        
        # Build relationships
        chunks = self._build_relationships(chunks, pdf_data)
        
        return chunks
    
    def _create_chunk(self, chunk_id: int, text: str, pages: List[int],
                     section: str, subsection: str, position_in_doc: float,
                     paragraph_range: Tuple[int, int]) -> Dict:
        """
        Create a chunk with location metadata
        """
        return {
            'chunk_id': chunk_id,
            'content': text,
            'token_count': len(self.encoding.encode(text)),
            'hash': hashlib.md5(text.encode()).hexdigest(),
            'location_metadata': {
                'page_numbers': pages,
                'start_page': min(pages) if pages else 0,
                'end_page': max(pages) if pages else 0,
                'section': section,
                'subsection': subsection,
                'paragraph_range': paragraph_range,
                'position': {
                    'percentage_in_doc': round(position_in_doc * 100, 2),
                    'is_beginning': position_in_doc < 0.1,
                    'is_middle': 0.1 <= position_in_doc <= 0.9,
                    'is_end': position_in_doc > 0.9
                },
                'hierarchy_level': 3 if subsection else (2 if section else 1),
                'outline_path': self._build_outline_path(section, subsection)
            }
        }
    
    def _build_outline_path(self, section: str, subsection: str) -> List[str]:
        """
        Build hierarchical path for chunk
        """
        path = []
        if section:
            path.append(section)
        if subsection:
            path.append(subsection)
        return path
    
    def _build_relationships(self, chunks: List[Dict], pdf_data: Dict) -> List[Dict]:
        """
        Build relationship metadata between chunks
        """
        for i, chunk in enumerate(chunks):
            # Sequential relationships
            prev_id = i - 1 if i > 0 else None
            next_id = i + 1 if i < len(chunks) - 1 else None
            
            # Find related chunks (same section)
            related = []
            if chunk['location_metadata']['section']:
                for j, other in enumerate(chunks):
                    if i != j and other['location_metadata']['section'] == chunk['location_metadata']['section']:
                        related.append(j)
            
            # Detect references in text
            references = self._extract_references(chunk['content'])
            
            # Find parent/child relationships based on hierarchy
            parent_id = None
            child_ids = []
            current_level = chunk['location_metadata']['hierarchy_level']
            
            # Look for parent (previous chunk with lower hierarchy level)
            for j in range(i - 1, -1, -1):
                if chunks[j]['location_metadata']['hierarchy_level'] < current_level:
                    parent_id = j
                    break
            
            # Look for children (following chunks with higher hierarchy level)
            for j in range(i + 1, len(chunks)):
                if chunks[j]['location_metadata']['hierarchy_level'] > current_level:
                    child_ids.append(j)
                elif chunks[j]['location_metadata']['hierarchy_level'] <= current_level:
                    break  # Stop when we reach same or lower level
            
            # Check if chunk continues from previous or continues to next
            continuation_of = None
            continues_in = None
            
            # Simple heuristic: if chunk starts mid-sentence
            if not chunk['content'].strip()[0].isupper() and prev_id is not None:
                continuation_of = prev_id
            
            # If chunk ends without proper punctuation
            if chunk['content'].strip()[-1] not in '.!?])"' and next_id is not None:
                continues_in = next_id
            
            chunk['relationship_metadata'] = {
                'chunk_id': i,
                'previous_chunk_id': prev_id,
                'next_chunk_id': next_id,
                'parent_chunk_id': parent_id,
                'child_chunk_ids': child_ids[:5],  # Limit to first 5 children
                'related_chunk_ids': related[:10],  # Limit to 10 related
                'references_to': references,
                'referenced_by_ids': [],  # Will be populated in second pass
                'continuation_of': continuation_of,
                'continues_in': continues_in
            }
        
        # Second pass: build referenced_by relationships
        for i, chunk in enumerate(chunks):
            for ref in chunk['relationship_metadata']['references_to']:
                # Find chunks that might contain this reference
                for j, other in enumerate(chunks):
                    if ref.lower() in other['content'].lower() and i != j:
                        other['relationship_metadata']['referenced_by_ids'].append(i)
        
        return chunks
    
    def _extract_references(self, text: str) -> List[str]:
        """
        Extract references to other parts of document
        """
        references = []
        
        # Common reference patterns
        patterns = [
            r'(?i)see\s+(?:page|section|chapter|part)\s+(\w+)',
            r'(?i)refer\s+to\s+(\w+)',
            r'(?i)as\s+mentioned\s+in\s+(\w+)',
            r'(?i)described\s+in\s+(\w+)',
            r'\(see\s+([^)]+)\)',
            r'Part\s+\d+',
            r'Section\s+[\d.]+',
            r'Chapter\s+\d+'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            references.extend(matches)
        
        return list(set(references))  # Remove duplicates
    
    def create_navigation_graph(self, chunks: List[Dict]) -> Dict:
        """
        Create a navigation graph for the document
        """
        graph = {
            'nodes': [],
            'edges': [],
            'sections': {},
            'hierarchy': {}
        }
        
        # Create nodes
        for chunk in chunks:
            node = {
                'id': chunk['chunk_id'],
                'label': f"Chunk {chunk['chunk_id']}",
                'section': chunk['location_metadata']['section'],
                'pages': chunk['location_metadata']['page_numbers'],
                'level': chunk['location_metadata']['hierarchy_level']
            }
            graph['nodes'].append(node)
            
            # Group by section
            section = chunk['location_metadata']['section'] or 'No Section'
            if section not in graph['sections']:
                graph['sections'][section] = []
            graph['sections'][section].append(chunk['chunk_id'])
        
        # Create edges (relationships)
        for chunk in chunks:
            rel = chunk['relationship_metadata']
            
            # Sequential edges
            if rel['next_chunk_id'] is not None:
                graph['edges'].append({
                    'from': rel['chunk_id'],
                    'to': rel['next_chunk_id'],
                    'type': 'sequential'
                })
            
            # Parent-child edges
            if rel['parent_chunk_id'] is not None:
                graph['edges'].append({
                    'from': rel['parent_chunk_id'],
                    'to': rel['chunk_id'],
                    'type': 'parent-child'
                })
            
            # Reference edges
            for ref_id in rel['referenced_by_ids'][:5]:  # Limit for visualization
                graph['edges'].append({
                    'from': rel['chunk_id'],
                    'to': ref_id,
                    'type': 'reference'
                })
        
        return graph
    
    def process_document(self, pdf_path: str) -> Dict:
        """
        Process a PDF document with full location and relationship tracking
        """
        print(f"Extracting structure from: {pdf_path}")
        
        # Extract with location data
        pdf_data = self.extract_with_location(pdf_path)
        
        # Create chunks with metadata
        chunks = self.create_chunks_with_metadata(pdf_data)
        
        # Create navigation graph
        nav_graph = self.create_navigation_graph(chunks)
        
        # Build complete index
        index = {
            'document_id': hashlib.md5(pdf_path.encode()).hexdigest(),
            'file_name': os.path.basename(pdf_path),
            'file_path': pdf_path,
            'processed_at': datetime.now().isoformat(),
            'statistics': {
                'total_pages': pdf_data['total_pages'],
                'total_chunks': len(chunks),
                'sections_found': len(set(c['location_metadata']['section'] 
                                        for c in chunks if c['location_metadata']['section'])),
                'has_outline': len(pdf_data['outline']) > 0
            },
            'document_outline': pdf_data['outline'],
            'chunks': chunks,
            'navigation_graph': nav_graph
        }
        
        return index
    
    def query_with_context(self, index: Dict, chunk_id: int, 
                          context_type: str = 'sequential', 
                          depth: int = 1) -> List[Dict]:
        """
        Retrieve a chunk with its context based on relationships
        
        Args:
            index: Document index
            chunk_id: Target chunk ID
            context_type: 'sequential', 'hierarchical', 'related', or 'all'
            depth: How many levels of context to include
        
        Returns:
            List of chunks including target and context
        """
        chunks = index['chunks']
        target_chunk = chunks[chunk_id]
        result = [target_chunk]
        visited = {chunk_id}
        
        if context_type in ['sequential', 'all']:
            # Add previous and next chunks
            rel = target_chunk['relationship_metadata']
            if rel['previous_chunk_id'] is not None and rel['previous_chunk_id'] not in visited:
                result.append(chunks[rel['previous_chunk_id']])
                visited.add(rel['previous_chunk_id'])
            if rel['next_chunk_id'] is not None and rel['next_chunk_id'] not in visited:
                result.append(chunks[rel['next_chunk_id']])
                visited.add(rel['next_chunk_id'])
        
        if context_type in ['hierarchical', 'all']:
            # Add parent and children
            rel = target_chunk['relationship_metadata']
            if rel['parent_chunk_id'] is not None and rel['parent_chunk_id'] not in visited:
                result.append(chunks[rel['parent_chunk_id']])
                visited.add(rel['parent_chunk_id'])
            for child_id in rel['child_chunk_ids'][:3]:  # Limit children
                if child_id not in visited:
                    result.append(chunks[child_id])
                    visited.add(child_id)
        
        if context_type in ['related', 'all']:
            # Add related chunks
            rel = target_chunk['relationship_metadata']
            for related_id in rel['related_chunk_ids'][:3]:  # Limit related
                if related_id not in visited:
                    result.append(chunks[related_id])
                    visited.add(related_id)
        
        # Sort by chunk_id to maintain order
        result.sort(key=lambda x: x['chunk_id'])
        
        return result


# Example usage
def main():
    # Initialize enhanced indexer
    indexer = EnhancedPDFIndexer(chunk_size=1000, chunk_overlap=200)
    
    # Process a PDF document
    pdf_path = "2024_policy_jacket.pdf"
    if os.path.exists(pdf_path):
        # Create comprehensive index
        document_index = indexer.process_document(pdf_path)
        
        # Save the index
        with open("enhanced_index.json", 'w', encoding='utf-8') as f:
            json.dump(document_index, f, indent=2)
        
        print(f"\nDocument processed successfully!")
        print(f"Total chunks: {document_index['statistics']['total_chunks']}")
        print(f"Sections found: {document_index['statistics']['sections_found']}")
        
        # Example: Retrieve chunk with context
        if document_index['chunks']:
            # Get chunk 5 with all its context
            context_chunks = indexer.query_with_context(
                document_index, 
                chunk_id=5, 
                context_type='all'
            )
            
            print(f"\nChunk 5 with context ({len(context_chunks)} chunks):")
            for chunk in context_chunks:
                print(f"  - Chunk {chunk['chunk_id']}: "
                      f"Pages {chunk['location_metadata']['page_numbers']}, "
                      f"Section: {chunk['location_metadata']['section']}")
        
        # Show navigation graph structure
        nav_graph = document_index['navigation_graph']
        print(f"\nNavigation Graph:")
        print(f"  Nodes (chunks): {len(nav_graph['nodes'])}")
        print(f"  Edges (relationships): {len(nav_graph['edges'])}")
        print(f"  Sections: {list(nav_graph['sections'].keys())}")


if __name__ == "__main__":
    main()