# pdf_agent.py
from crewai import Agent, Task, Crew, Process
import tempfile
import logging
import os

# Import the Dockling tool
from dockling_tool import DocklingPDFTool

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WatsonxPDFAgent:
    """PDF Agent powered by WatsonX and CrewAI"""
    
    def __init__(self, model, pdf_search_tool=None):
        """Initialize the WatsonX PDF Agent
        
        Args:
            model: WatsonX model instance
            pdf_search_tool: Tool for searching PDF content
        """
        self.model = model
        self.pdf_search_tool = pdf_search_tool
        self.create_agents_and_crew()
    
    def create_agents_and_crew(self):
        """Create the agent crew for document processing"""
        # Reader Agent - Specialized in extracting content
        self.reader_agent = Agent(
            name="Document Reader",
            role="Document Analyzer",
            goal="Extract and understand content from PDF documents",
            backstory="I am a specialized document reader that can extract key information from PDFs.",
            verbose=True,
            allow_delegation=False,
            tools=[]  # Remove tools to avoid compatibility issues
        )
        
        # Analyst Agent - Specialized in summarizing
        self.analyst_agent = Agent(
            name="Content Analyst",
            role="Information Analyzer",
            goal="Analyze and summarize document content in a comprehensive way",
            backstory="I am an expert analyst that can interpret document content and create meaningful summaries.",
            verbose=True,
            allow_delegation=False
        )
        
        # Create tasks
        self.read_document_task = Task(
            description="Read and extract key information from the provided PDF document. Focus on main topics, key points, and important details.",
            agent=self.reader_agent,
            expected_output="A comprehensive extraction of the document's content"
        )
        
        self.analyze_document_task = Task(
            description="Analyze the extracted content and provide a detailed summary. Identify main themes, key findings, and organize the information logically.",
            agent=self.analyst_agent,
            expected_output="A comprehensive summary of the document"
        )
        
        # Create crew
        self.crew = Crew(
            agents=[self.reader_agent, self.analyst_agent],
            tasks=[self.read_document_task, self.analyze_document_task],
            verbose=True,
            process=Process.sequential
        )
    
    def process_document(self, pdf_path, query=None):
        """Process document with Dockling and WatsonX
        
        Args:
            pdf_path (str): Path to the PDF file
            query (str, optional): Specific query about the document
            
        Returns:
            str: Processing result (summary or answer to query)
        """
        try:
            # Update the PDF search tool if needed
            if pdf_path and not self.pdf_search_tool:
                self.pdf_search_tool = DocklingPDFTool(pdf_path, self.model)
            elif pdf_path and self.pdf_search_tool and self.pdf_search_tool.pdf_path != pdf_path:
                self.pdf_search_tool = DocklingPDFTool(pdf_path, self.model)
            
            if not self.pdf_search_tool:
                return "No PDF document available for processing."
            
            # If there's a specific query, use direct model generation
            if query and query.strip():
                if "summarize" in query.lower() and any(word in query.lower() for word in ["pdf", "document", "file", "the"]):
                    search_results = self.pdf_search_tool.search("main topics key points overview executive summary")
                    
                    augmented_prompt = f"""
                    The user wants a summary of the PDF document.
                    
                    Here is content from the uploaded PDF document:
                    {search_results}
                    
                    Please provide a comprehensive summary of this document covering the main points.
                    """
                else:
                    search_results = self.pdf_search_tool.search(query)
                    
                    augmented_prompt = f"""
                    The user's question is: {query}
                    
                    Based on the uploaded PDF document, here is relevant information:
                    {search_results}
                    
                    Using the above context from the PDF, please answer the user's question accurately.
                    """
                
                return self.model.generate_text(augmented_prompt)
            else:
                # For full document processing, use Dockling directly
                search_results = self.pdf_search_tool.search("main topics key points overview executive summary")
                
                augmented_prompt = f"""
                You are a professional document analyst. 
                The user has uploaded a PDF document and wants a comprehensive summary.
                
                Here is relevant content from the document:
                {search_results}
                
                Please provide a detailed, well-structured summary covering:
                1. The main purpose of the document
                2. Key points and findings
                3. Important details and insights
                4. Conclusions or recommendations (if any)
                
                Organize the summary in a logical way with clear headings and sections.
                """
                
                return self.model.generate_text(augmented_prompt)
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return f"Error processing document: {str(e)}"
    
    def get_document_metadata(self, pdf_path):
        """Get document metadata
        
        Args:
            pdf_path (str): Path to the PDF file
            
        Returns:
            dict: Document metadata
        """
        if not pdf_path or not os.path.exists(pdf_path):
            return {"error": "PDF file not found"}
        
        try:
            # If we have a PDF search tool and it's for the current document,
            # get metadata from it
            if self.pdf_search_tool and self.pdf_search_tool.pdf_path == pdf_path:
                return self.pdf_search_tool.get_metadata()
            
            # Otherwise, create a temporary tool just to get metadata
            tool = DocklingPDFTool(pdf_path, self.model)
            return tool.get_metadata()
            
        except Exception as e:
            logger.error(f"Error getting document metadata: {str(e)}")
            return {
                "error": str(e),
                "file_name": os.path.basename(pdf_path),
                "file_size": os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0,
                "title": "Unknown",
                "author": "Unknown",
                "date": "Unknown",
                "pages": 0
            }