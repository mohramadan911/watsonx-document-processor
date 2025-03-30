# document_flow.py
from crewai.flow.flow import Flow, listen, start  # Updated import path
from crewai import Agent, Task, Crew
import logging
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class DocumentProcessingFlow:
    """Autonomous document processing flow using CrewAI"""
    
    def __init__(self, watsonx_model, aws_s3_client=None, ms_graph_client=None):
        """Initialize the document processing flow
        
        Args:
            watsonx_model: WatsonX model instance
            aws_s3_client: AWS S3 client for storage
            ms_graph_client: Microsoft Graph client for email
        """
        self.model = watsonx_model
        self.aws_s3_client = aws_s3_client
        self.ms_graph_client = ms_graph_client
        
        # Initialize agents and flow
        self.initialize_agents()
        self.create_flow()
    
    def initialize_agents(self):
        """Initialize the specialized agents"""
        
        # Scout Agent - Monitors for new documents
        self.scout_agent = Agent(
            role="Document Scout",
            goal="Monitor repositories for new documents and trigger processing",
            backstory="I continuously watch for new documents appearing in repositories and email attachments, ensuring nothing is missed.",
            verbose=True,
            allow_delegation=True
        )
        
        # Reader Agent - Extracts content and metadata
        self.reader_agent = Agent(
            role="Document Reader",
            goal="Extract and understand document content and metadata",
            backstory="I thoroughly read documents to understand their structure, content, and purpose.",
            verbose=True,
            allow_delegation=True
        )
        
        # Analyst Agent - Analyzes content
        self.analyst_agent = Agent(
            role="Content Analyst",
            goal="Analyze document content and generate summaries and insights",
            backstory="I analyze documents to identify key information, main topics, and create comprehensive summaries.",
            verbose=True,
            allow_delegation=True
        )
        
        # Classifier Agent - Classifies documents
        self.classifier_agent = Agent(
            role="Document Classifier",
            goal="Categorize documents and organize them appropriately",
            backstory="I accurately classify documents into appropriate categories and ensure they're stored correctly.",
            verbose=True,
            allow_delegation=True
        )
        
        # Workflow Agent - Determines next steps
        self.workflow_agent = Agent(
            role="Workflow Manager",
            goal="Determine and initiate appropriate workflows based on document type",
            backstory="I decide what actions should be taken for each document, from sending notifications to scheduling reviews.",
            verbose=True,
            allow_delegation=True
        )
    

    def create_flow(self):
        """Create the document processing flow"""
        
        # Define specific tasks for each agent
        scout_task = Task(
            description="Monitor for new documents and identify them for processing",
            agent=self.scout_agent,
            expected_output="List of documents ready for processing"
        )
        
        reader_task = Task(
            description="Extract content and metadata from the document",
            agent=self.reader_agent,
            expected_output="Extracted document content and metadata"
        )
        
        analyst_task = Task(
            description="Analyze document content and generate summaries",
            agent=self.analyst_agent,
            expected_output="Document analysis and summary"
        )
        
        classifier_task = Task(
            description="Classify document into appropriate category",
            agent=self.classifier_agent,
            expected_output="Document classification and category"
        )
        
        workflow_task = Task(
            description="Determine next actions based on document type",
            agent=self.workflow_agent,
            expected_output="Workflow actions for the document"
        )
        
        # Create the flow with tasks
        self.document_flow = Flow(
            name="Autonomous Document Processing",
            description="Process documents automatically from detection through classification and workflow",
            agents=[
                self.scout_agent,
                self.reader_agent, 
                self.analyst_agent,
                self.classifier_agent,
                self.workflow_agent
            ],
            tasks=[
                scout_task,
                reader_task,
                analyst_task,
                classifier_task,
                workflow_task
            ]
        )
        
        # Add flow steps/nodes here if required by your Flow implementation
    
    def process_new_document(self, bucket_name, object_key):
        """Process a newly detected document
        
        Args:
            bucket_name (str): S3 bucket name
            object_key (str): S3 object key
            
        Returns:
            dict: Results of document processing
        """
        try:
            # Download the document
            import tempfile
            temp_dir = os.path.join(tempfile.gettempdir(), "pdf_agent")
            os.makedirs(temp_dir, exist_ok=True)
            local_path = os.path.join(temp_dir, os.path.basename(object_key))
            
            if self.aws_s3_client.download_file(bucket_name, object_key, local_path):
                logger.info(f"Successfully downloaded {object_key} to {local_path}")
                
                # Create initial document context
                document_context = {
                    "bucket_name": bucket_name,
                    "object_key": object_key,
                    "local_path": local_path,
                    "file_name": os.path.basename(object_key)
                }
                
                # Execute direct processing - bypassing the flow for now
                results = self._process_document_directly(local_path, bucket_name, object_key)
                
                return {
                    "success": True,
                    "message": f"Document processed successfully: {object_key}",
                    "results": results
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to download document: {object_key}"
                }
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def scan_bucket(self, bucket_name):
        """Scan a bucket for documents to process
        
        Args:
            bucket_name (str): S3 bucket name
            
        Returns:
            dict: Results of the scan operation
        """
        if not self.aws_s3_client:
            return {"success": False, "error": "AWS S3 client not initialized"}
        
        try:
            logger.info(f"Scanning bucket: {bucket_name}")
            
            # List all PDF files in the bucket (at root level)
            s3_items = self.aws_s3_client.list_pdfs(bucket_name)
            
            if not s3_items:
                logger.info(f"No items found in bucket {bucket_name}")
                return {"success": True, "message": "No documents found", "documents": []}
            
            # Filter for PDF files
            pdf_files = [item for item in s3_items if 
                        isinstance(item, dict) and 
                        'name' in item and 
                        item['name'].lower().endswith('.pdf')]
            
            if not pdf_files:
                logger.info(f"No PDF files found in bucket {bucket_name}")
                return {"success": True, "message": "No PDF documents found", "documents": []}
            
            logger.info(f"Found {len(pdf_files)} PDF files in bucket {bucket_name}")
            
            # Process each PDF file
            processed_documents = []
            for pdf_file in pdf_files:
                object_key = pdf_file.get('path', pdf_file['name'])
                
                # Skip files that are already in category folders
                if '/' in object_key:
                    # This is likely already organized
                    continue
                    
                logger.info(f"Processing document: {object_key}")
                
                # Process the document
                result = self.process_new_document(bucket_name, object_key)
                
                if result.get("success", False):
                    processed_documents.append({
                        "name": pdf_file['name'],
                        "key": object_key,
                        "result": result
                    })
                    
                    # Increment the counter in session state if using Streamlit
                    import streamlit as st
                    if 'processed_document_count' in st.session_state:
                        st.session_state.processed_document_count += 1
                else:
                    logger.error(f"Failed to process document {object_key}: {result.get('error', 'Unknown error')}")
            
            return {
                "success": True,
                "message": f"Processed {len(processed_documents)} documents",
                "documents": processed_documents
            }
        except Exception as e:
            logger.error(f"Error scanning bucket {bucket_name}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}

    # Add this method to implement scan across all monitored buckets
    def scan_all_buckets(self):
        """Scan all monitored buckets for documents
        
        Returns:
            dict: Results from all bucket scans
        """
        # This would be called from the "Scan Now" button
        import streamlit as st
        
        if 'monitored_buckets' not in st.session_state or not st.session_state.monitored_buckets:
            return {"success": False, "error": "No buckets configured for monitoring"}
        
        results = {}
        for bucket in st.session_state.monitored_buckets:
            results[bucket] = self.scan_bucket(bucket)
        
        return {"success": True, "bucket_results": results}
    
    def _process_document_directly(self, document_path, bucket_name, object_key):
        """Direct document processing as fallback if flow execution fails
        
        Args:
            document_path (str): Path to the document
            bucket_name (str): S3 bucket name
            object_key (str): S3 object key
            
        Returns:
            dict: Processing results
        """
        results = {}
        
        try:
            # Classification
            logger.info(f"Directly classifying document: {document_path}")
            
            # Initialize document classifier if needed
            from document_classifier import DocumentClassifier, DocumentCategory
            classifier = DocumentClassifier(self.model)
            
            # Classify the document
            category, confidence, reasoning, custom_category = classifier.classify_document(document_path)
            
            # Record classification results
            results["classification"] = {
                "category": category.name if hasattr(category, "name") else str(category),
                "confidence": confidence,
                "reasoning": reasoning,
                "custom_category": custom_category
            }
            
            # Determine the target folder name
            if category == DocumentCategory.CUSTOM and custom_category:
                folder_name = custom_category
            else:
                folder_name = DocumentCategory.to_folder_name(category)
            
            # Actually organize the document in S3
            logger.info(f"Organizing document in S3: {object_key} to folder {folder_name}")
            
            # Determine target key
            base_name = os.path.basename(object_key)
            target_key = f"{folder_name}/{base_name}"
            
            # Create folder and move file
            try:
                # First create folder
                folder_marker = f"{folder_name}/"
                self.aws_s3_client.s3_client.put_object(
                    Bucket=bucket_name,
                    Key=folder_marker,
                    Body=''
                )
                
                # Copy the object to new location
                copy_source = {'Bucket': bucket_name, 'Key': object_key}
                self.aws_s3_client.s3_client.copy_object(
                    CopySource=copy_source,
                    Bucket=bucket_name,
                    Key=target_key
                )
                
                # Delete the original
                self.aws_s3_client.s3_client.delete_object(
                    Bucket=bucket_name,
                    Key=object_key
                )
                
                results["organization"] = {
                    "success": True,
                    "source_key": object_key,
                    "target_key": target_key,
                    "folder": folder_name
                }
            except Exception as org_error:
                logger.error(f"Error organizing document: {str(org_error)}")
                results["organization"] = {
                    "success": False,
                    "error": str(org_error)
                }
            
            return results
        
        except Exception as e:
            logger.error(f"Error in _process_document_directly: {str(e)}")
            results["error"] = str(e)
            return results

def integrate_document_flow():
    """Create function to integrate with your existing Streamlit app"""
    import streamlit as st
    
    # Initialize the document flow if not already in session state
    if 'document_flow' not in st.session_state:
        # First check if pdf_agent exists and has a model attribute
        if 'pdf_agent' in st.session_state and st.session_state.pdf_agent is not None and hasattr(st.session_state.pdf_agent, 'model'):
            watsonx_model = st.session_state.pdf_agent.model
            aws_s3_client = st.session_state.aws_s3_client if 'aws_s3_client' in st.session_state else None
            ms_graph_client = st.session_state.ms_graph_client if 'ms_graph_client' in st.session_state else None
            
            try:
                st.session_state.document_flow = DocumentProcessingFlow(
                    watsonx_model,
                    aws_s3_client,
                    ms_graph_client
                )
                st.success("Autonomous document processing flow initialized!")
            except Exception as e:
                st.error(f"Error initializing document flow: {str(e)}")
                # Create a simpler version that doesn't depend on CrewAI Flow
                try:
                    from document_classifier import DocumentClassifier
                    st.session_state.classifier = DocumentClassifier(watsonx_model)
                    st.success("Document classifier initialized (simplified mode)")
                except Exception as e2:
                    st.error(f"Could not initialize simplified classifier: {str(e2)}")
        else:
            st.error("Cannot initialize document flow: WatsonX model not properly initialized. Please initialize the WatsonX model first.")