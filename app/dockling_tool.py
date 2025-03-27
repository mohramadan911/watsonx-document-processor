# dockling_tool.py
from crewai.knowledge.source.crew_docling_source import CrewDoclingSource
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DocklingPDFTool:
    """PDF document tool using Dockling for integration with WatsonX"""
    
    def __init__(self, pdf_path, watsonx_model=None):
        """Initialize the Dockling PDF tool
        
        Args:
            pdf_path (str): Path to the PDF file
            watsonx_model: Optional WatsonX model for custom processing
        """
        self.pdf_path = pdf_path
        self.watsonx_model = watsonx_model
        
        # Log initialization
        logger.info(f"Initializing Dockling with PDF: {os.path.basename(pdf_path)}")
        
        # Create a document source
        try:
            self.content_source = CrewDoclingSource(
                file_paths=[self.pdf_path]
            )
            logger.info("Document processed successfully with Dockling")
            
            # Extract basic metadata
            self.metadata = self.extract_metadata()
        except Exception as e:
            logger.error(f"Error initializing Dockling: {str(e)}")
            raise
    
    def search(self, query):
        """Search the document for relevant content
        
        Args:
            query (str): The search query
            
        Returns:
            str: Relevant document content
        """
        try:
            # Log the search query
            logger.info(f"Searching document for: {query}")
            
            # Use the content source to retrieve information
            results = self.content_source.retrieve(query)
            
            if results:
                return results
            else:
                logger.warning("No results found for query")
                return "No relevant information found in the document."
                
        except Exception as e:
            logger.error(f"Error searching document: {str(e)}")
            return f"Error searching document: {str(e)}"
    
    def extract_metadata(self):
        """Extract basic metadata from the document
        
        Returns:
            dict: Document metadata
        """
        metadata = {
            "file_name": os.path.basename(self.pdf_path),
            "file_size": os.path.getsize(self.pdf_path),
            "title": "Unknown",
            "author": "Unknown",
            "date": "Unknown",
            "pages": 0
        }
        
        # Try to extract more metadata if available
        try:
            # Get title from first page content
            first_page = self.search("document title first page header")
            if self.watsonx_model and first_page:
                prompt = f"""
                Extract the document title from this text:
                {first_page[:1000]}
                
                Return ONLY the title, nothing else.
                """
                title_response = self.watsonx_model.generate_text(prompt)
                if title_response and len(title_response) < 200:  # Reasonable title length
                    metadata["title"] = title_response.strip()
            
            # Get summary of topics
            if self.watsonx_model:
                overview = self.search("main topics key points")
                prompt = f"""
                Identify 3-5 main topics covered in this document:
                {overview}
                
                Return ONLY a JSON array of topic strings, nothing else.
                """
                topics_response = self.watsonx_model.generate_text(prompt)
                
                try:
                    import json
                    # Clean the response to ensure it's valid JSON
                    cleaned_response = topics_response.strip()
                    if not cleaned_response.startswith('['):
                        cleaned_response = '[' + cleaned_response
                    if not cleaned_response.endswith(']'):
                        cleaned_response = cleaned_response + ']'
                    
                    topics = json.loads(cleaned_response)
                    if isinstance(topics, list):
                        metadata["topics"] = topics
                except Exception as e:
                    logger.warning(f"Could not parse topics: {e}")
                    
        except Exception as e:
            logger.warning(f"Error extracting advanced metadata: {e}")
        
        return metadata
    
    def get_metadata(self):
        """Get document metadata
        
        Returns:
            dict: Document metadata
        """
        return self.metadata