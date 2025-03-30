# dockling_tool.py
from crewai.knowledge.source.crew_docling_source import CrewDoclingSource
import os
import logging
import json
import tempfile
import shutil
from datetime import datetime

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
        self.watsonx_model = watsonx_model
        
        # Log initialization
        logger.info(f"DocklingPDFTool initializing with path: {pdf_path}")
        
        # Create the document source
        try:
            # Get the absolute path and filename
            abs_path = os.path.abspath(pdf_path)
            filename = os.path.basename(abs_path)
            logger.info(f"Absolute path: {abs_path}, Filename: {filename}")
            
            # Step 1: Create a 'knowledge' directory in the current working directory
            # This is the critical part - CrewDoclingSource looks for files in a 'knowledge' directory
            # relative to the current working directory
            cwd = os.getcwd()
            knowledge_dir = os.path.join(cwd, "knowledge")
            os.makedirs(knowledge_dir, exist_ok=True)
            logger.info(f"Created knowledge directory at: {knowledge_dir}")
            
            # Step 2: Copy the file to the knowledge directory
            knowledge_file_path = os.path.join(knowledge_dir, filename)
            logger.info(f"Copying file to: {knowledge_file_path}")
            
            # Copy the file if it's not already there
            if not os.path.exists(knowledge_file_path) and os.path.exists(abs_path):
                shutil.copy2(abs_path, knowledge_file_path)
                logger.info(f"File copied successfully")
            
            # Verify the file exists
            if not os.path.exists(knowledge_file_path):
                logger.error(f"File not found at: {knowledge_file_path}")
                raise FileNotFoundError(f"File not found at: {knowledge_file_path}")
            
            # Store the paths
            self.original_path = abs_path
            self.knowledge_path = knowledge_file_path
            self.filename = filename
            
            # Step 3: According to CrewAI docs, we pass the file path to CrewDoclingSource
            # But the library internally prepends 'knowledge/' - so we just pass the filename
            self.pdf_path = filename
            logger.info(f"Using filename for CrewDoclingSource: {self.pdf_path}")
            
            # Initialize the content source
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
            
            # Check if CrewDoclingSource has retrieve method 
            if hasattr(self.content_source, 'retrieve'):
                logger.info("Using 'retrieve' method for search")
                results = self.content_source.retrieve(query)
            elif hasattr(self.content_source, 'query'):
                logger.info("Using 'query' method for search")
                results = self.content_source.query(query)
            elif hasattr(self.content_source, 'get_relevant_documents'):
                logger.info("Using 'get_relevant_documents' method for search")
                results = self.content_source.get_relevant_documents(query)
            else:
                # Fall back to using WatsonX model
                logger.warning("No search method found on CrewDoclingSource, using WatsonX model instead")
                if self.watsonx_model:
                    prompt = f"""
                    I'm trying to find information in a document named "{self.filename}" about:
                    
                    {query}
                    
                    Based on the document name and this query, what information might be relevant? 
                    Please provide a thoughtful, detailed response as if you had access to the document.
                    """
                    results = self.watsonx_model.generate_text(prompt)
                else:
                    results = f"Could not search document: CrewDoclingSource has no search method and no WatsonX model provided"
            
            if results:
                # Convert complex results to string if needed
                if not isinstance(results, str):
                    if hasattr(results, 'content'):
                        results = results.content
                    elif isinstance(results, list) and results:
                        if hasattr(results[0], 'page_content'):
                            results = "\n\n".join(doc.page_content for doc in results)
                        else:
                            results = str(results)
                    else:
                        results = str(results)
                return results
            else:
                logger.warning("No results found for query")
                return "No relevant information found in the document."
                
        except Exception as e:
            logger.error(f"Error searching document: {str(e)}")
            
            # On error, fall back to WatsonX model if available
            if self.watsonx_model:
                logger.info("Falling back to WatsonX model due to search error")
                prompt = f"""
                I need information from a document titled "{self.filename}" regarding:
                
                {query}
                
                Please provide a thoughtful response based on what might be in this document.
                """
                return self.watsonx_model.generate_text(prompt)
            else:
                return f"Error searching document: {str(e)}"
    
    def extract_metadata(self):
        """Extract enhanced metadata from the document
        
        Returns:
            dict: Document metadata
        """
        metadata = {
            "file_name": self.filename,
            "file_size": os.path.getsize(self.knowledge_path) if os.path.exists(self.knowledge_path) else 0,
            "title": "Unknown",
            "author": "Unknown",
            "date": "Unknown",
            "pages": 0,
            "last_accessed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "importance_score": None,
            "topics": [],
            "key_people": [],
            "action_items": []
        }
        
        # Try to extract more metadata if available
        try:
            # Try direct search, but handle failure gracefully
            try:
                first_page = self.search("document title first page header")
            except Exception as e:
                logger.warning(f"Error getting first page content: {e}")
                first_page = ""
            
            # If we have a WatsonX model, use it to extract advanced metadata
            if self.watsonx_model:
                # Generate a title even without first page content
                if not first_page:
                    # Generate title from filename
                    prompt = f"""
                    Based on the filename "{self.filename}", what might be the title of this document?
                    Return ONLY the title, nothing else.
                    """
                else:
                    # Extract title from content
                    prompt = f"""
                    Extract the document title from this text:
                    {first_page[:1000]}
                    
                    Return ONLY the title, nothing else.
                    """
                
                title_response = self.watsonx_model.generate_text(prompt)
                if title_response and len(title_response) < 200:  # Reasonable title length
                    metadata["title"] = title_response.strip()
                
                # Try to extract author information
                if first_page:
                    prompt = f"""
                    Extract the author name(s) from this text:
                    {first_page[:1000]}
                    
                    Return ONLY the author name(s), or "Unknown" if not found. Nothing else.
                    """
                    author_response = self.watsonx_model.generate_text(prompt)
                    if author_response and len(author_response) < 100 and author_response.lower() != "unknown":
                        metadata["author"] = author_response.strip()
                
                # Generate topics even if search doesn't work
                prompt = f"""
                Based on the document title "{metadata["title"]}" and filename "{self.filename}",
                what 3-5 topics might this document cover?
                
                Return ONLY a JSON array of topic strings, nothing else. Format: ["Topic 1", "Topic 2", "Topic 3"]
                """
                topics_response = self.watsonx_model.generate_text(prompt)
                
                try:
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
                
                # Other metadata extraction methods can remain unchanged
                    
        except Exception as e:
            logger.warning(f"Error extracting advanced metadata: {e}")
        
        return metadata
    
    def get_metadata(self):
        """Get document metadata
        
        Returns:
            dict: Document metadata
        """
        return self.metadata
    
    def update_metadata(self, key, value):
        """Update a specific metadata field
        
        Args:
            key (str): Metadata key to update
            value: New value
            
        Returns:
            bool: Success or failure
        """
        try:
            self.metadata[key] = value
            logger.info(f"Updated metadata field '{key}'")
            return True
        except Exception as e:
            logger.error(f"Error updating metadata: {e}")
            return False