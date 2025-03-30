# custom_pdf_tool.py
import logging
import os
import tempfile
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CustomPDFSearchTool:
    """Custom PDF search tool wrapping DocklingPDFTool"""
    
    def __init__(self, pdf_path, watsonx_model):
        """Initialize the PDF search tool
        
        Args:
            pdf_path (str): Path to the PDF file
            watsonx_model: WatsonX model instance for enhanced processing
        """
        # Make sure we have an absolute path
        if not os.path.isabs(pdf_path):
            pdf_path = os.path.abspath(pdf_path)
        
        # Log path information for debugging
        logger.info(f"CustomPDFSearchTool initializing with original path: {pdf_path}")
        
        # Verify the file exists
        if not os.path.exists(pdf_path):
            error_msg = f"PDF file not found at: {pdf_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        # Store the original path
        self.original_pdf_path = pdf_path
        self.watsonx_model = watsonx_model
        
        # Import DocklingPDFTool here to avoid circular imports
        try:
            from dockling_tool import DocklingPDFTool
            logger.info("Successfully imported DocklingPDFTool")
        except ImportError as e:
            logger.error(f"Failed to import DocklingPDFTool: {str(e)}")
            raise
        
        # Create the Dockling PDF tool with the original path
        try:
            self.dockling_tool = DocklingPDFTool(pdf_path=pdf_path, watsonx_model=watsonx_model)
            logger.info(f"Successfully initialized DocklingPDFTool for {os.path.basename(pdf_path)}")
            
            # Save the path that DocklingPDFTool is using
            self.pdf_path = self.dockling_tool.pdf_path
            logger.info(f"Using Dockling path: {self.pdf_path}")
        except Exception as e:
            logger.error(f"Error initializing DocklingPDFTool: {str(e)}")
            raise
    
    def search(self, query):
        """Search the PDF document content
        
        Args:
            query (str): The search query
            
        Returns:
            str: Relevant content from the PDF
        """
        logger.info(f"Searching for query: {query}")
        result = self.dockling_tool.search(query)
        return result
    
    def get_metadata(self):
        """Get document metadata
        
        Returns:
            dict: Document metadata
        """
        return self.dockling_tool.get_metadata()