# document_flow.py
from crewai import Agent, Task, Crew
from crewai.flows import Flow, Task as FlowTask
import logging
import os
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        
        # Create flow tasks
        discover_document = FlowTask(
            agent=self.scout_agent,
            task_id="discover_document",
            task="Monitor for new document arrivals in AWS S3 and notify when detected",
            context="Look for new documents in monitored S3 buckets and trigger processing",
            output_file="document_detection.json"
        )
        
        extract_content = FlowTask(
            agent=self.reader_agent,
            task_id="extract_content",
            task="Extract key content and metadata from the document",
            context="Read the document thoroughly to understand its structure and content",
            output_file="document_content.json"
        )
        
        analyze_document = FlowTask(
            agent=self.analyst_agent,
            task_id="analyze_document",
            task="Analyze document content and generate summary and insights",
            context="Create a comprehensive summary and extract key insights",
            output_file="document_analysis.json"
        )
        
        classify_document = FlowTask(
            agent=self.classifier_agent,
            task_id="classify_document",
            task="Categorize the document and determine where it should be stored",
            context="Classify the document into appropriate categories and organize it in S3",
            output_file="document_classification.json"
        )
        
        determine_workflow = FlowTask(
            agent=self.workflow_agent,
            task_id="determine_workflow",
            task="Determine appropriate workflows and actions based on document type",
            context="Decide what actions should be taken, from notifications to review scheduling",
            output_file="document_workflow.json"
        )
        
        # Create the flow with task dependencies
        self.document_flow = Flow(
            name="Autonomous Document Processing",
            description="Process documents automatically from detection through classification and workflow",
            tasks=[
                discover_document,
                extract_content,
                analyze_document,
                classify_document,
                determine_workflow
            ],
            dependencies={
                "extract_content": ["discover_document"],
                "analyze_document": ["extract_content"],
                "classify_document": ["extract_content"],
                "determine_workflow": ["analyze_document", "classify_document"]
            }
        )
    
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
            temp_dir = os.path.join(tempfile.gettempdir(), "pdf_agent")
            os.makedirs(temp_dir, exist_ok=True)
            local_path = os.path.join(temp_dir, os.path.basename(object_key))
            
            if self.aws_s3_client.download_file(bucket_name, object_key, local_path):
                # Create initial inputs for the flow
                inputs = {
                    "bucket_name": bucket_name,
                    "object_key": object_key,
                    "local_path": local_path,
                    "file_name": os.path.basename(object_key)
                }
                
                # Execute the flow
                results = self.document_flow.run(inputs=inputs)
                
                # Process results and take actions
                self._process_flow_results(results, local_path)
                
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
    
    def _process_flow_results(self, results, document_path):
        """Process flow results and take appropriate actions
        
        Args:
            results (dict): Flow results
            document_path (str): Path to the document
        """
        try:
            # Extract results from each task
            document_analysis = results.get("document_analysis", {})
            document_classification = results.get("document_classification", {})
            document_workflow = results.get("document_workflow", {})
            
            # Organize document if classification is available
            if document_classification and "category" in document_classification:
                from document_classifier import DocumentCategory
                category = DocumentCategory.from_string(document_classification["category"])
                
                # Import document classifier if needed
                from document_classifier import DocumentClassifier
                classifier = DocumentClassifier(self.model)
                
                # Get bucket name and organize document
                bucket_name = results.get("document_detection", {}).get("bucket_name")
                if bucket_name and self.aws_s3_client:
                    classifier.organize_document(
                        self.aws_s3_client,
                        document_path,
                        bucket_name,
                        results.get("document_detection", {}).get("object_key")
                    )
            
            # Process workflow actions
            if document_workflow:
                # Handle notifications
                if "notify" in document_workflow and document_workflow["notify"]:
                    recipients = document_workflow.get("recipients", [])
                    for recipient in recipients:
                        self._send_notification(
                            recipient,
                            document_path,
                            document_analysis.get("summary"),
                            document_classification
                        )
                
                # Handle reminders
                if "set_reminder" in document_workflow and document_workflow["set_reminder"]:
                    reminder_days = document_workflow.get("reminder_days", 7)
                    self._schedule_reminder(
                        document_path,
                        reminder_days,
                        document_workflow.get("reminder_note")
                    )
        except Exception as e:
            logger.error(f"Error processing flow results: {str(e)}")
    
    def _send_notification(self, recipient, document_path, summary, classification):
        """Send notification email
        
        Args:
            recipient (str): Email recipient
            document_path (str): Path to document
            summary (str): Document summary
            classification (dict): Classification information
        """
        if self.ms_graph_client:
            document_name = os.path.basename(document_path)
            self.ms_graph_client.create_email_with_summary(
                recipient,
                document_name,
                summary,
                document_path,
                classification=classification
            )
    
    def _schedule_reminder(self, document_path, days, note=None):
        """Schedule a reminder
        
        Args:
            document_path (str): Path to document
            days (int): Days until reminder
            note (str, optional): Optional reminder note
        """
        if self.ms_graph_client:
            # Implementation would depend on MS Graph calendar integration
            pass

# Integration with your existing app.py
def integrate_document_flow():
    """Create function to integrate with your existing Streamlit app"""
    import streamlit as st
    
    # Initialize the document flow if not already in session state
    if 'document_flow' not in st.session_state and 'pdf_agent' in st.session_state:
        watsonx_model = st.session_state.pdf_agent.model
        aws_s3_client = st.session_state.aws_s3_client if 'aws_s3_client' in st.session_state else None
        ms_graph_client = st.session_state.ms_graph_client if 'ms_graph_client' in st.session_state else None
        
        st.session_state.document_flow = DocumentProcessingFlow(
            watsonx_model,
            aws_s3_client,
            ms_graph_client
        )
        
        st.success("Autonomous document processing flow initialized!")
    
    # Add this to your S3 file listing to enable automatic processing
    # if st.button("Enable Autonomous Processing"):
    #     if 'document_flow' in st.session_state and 'selected_bucket' in st.session_state:
    #         bucket = st.session_state.selected_bucket
    #         st.session_state.autonomous_processing = True
    #         st.success(f"Autonomous processing enabled for bucket: {bucket}")
    #         
    #         # Start monitoring thread
    #         import threading
    #         threading.Thread(
    #             target=monitor_s3_bucket,
    #             args=(st.session_state.document_flow, bucket),
    #             daemon=True
    #         ).start()

def monitor_s3_bucket(document_flow, bucket_name, interval=60):
    """Monitor an S3 bucket for new documents
    
    Args:
        document_flow: Document processing flow
        bucket_name (str): S3 bucket to monitor
        interval (int): Check interval in seconds
    """
    import time
    
    # Track processed files
    processed_files = set()
    
    while True:
        try:
            # List PDF files in the bucket
            pdfs = document_flow.aws_s3_client.list_pdf_files(bucket_name)
            
            # Check for new files
            for pdf in pdfs:
                if pdf['path'] not in processed_files:
                    logger.info(f"New document detected: {pdf['path']}")
                    
                    # Process the document
                    result = document_flow.process_new_document(bucket_name, pdf['path'])
                    
                    if result.get("success", False):
                        processed_files.add(pdf['path'])
                        logger.info(f"Successfully processed new document: {pdf['path']}")
                    else:
                        logger.error(f"Failed to process document: {pdf['path']}")
        except Exception as e:
            logger.error(f"Error monitoring S3 bucket: {str(e)}")
        
        # Wait for next check
        time.sleep(interval)