# monitors.py
import logging
import time
import threading
import os
import json
from datetime import datetime, timedelta
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DocumentMonitor:
    """Document monitoring system for autonomous agent operation"""
    
    def __init__(self, aws_s3_client, document_flow, watsonx_model):
        """Initialize the document monitor
        
        Args:
            aws_s3_client: AWS S3 client
            document_flow: DocumentProcessingFlow instance
            watsonx_model: WatsonX model instance
        """
        self.aws_s3_client = aws_s3_client
        self.document_flow = document_flow
        self.model = watsonx_model
        self.monitored_buckets = []
        self.processed_files = set()
        self.is_running = False
        self.monitor_thread = None
        self.processing_paused = False
        
        # Schedule tracking
        self.review_schedule = {}
        self.last_notification_check = datetime.now()
    
    def start_monitoring(self, buckets=None):
        """Start monitoring S3 buckets for new documents
        
        Args:
            buckets (list): List of bucket names to monitor
        """
        if buckets:
            self.monitored_buckets = buckets
        
        if not self.monitored_buckets:
            logger.warning("No buckets to monitor")
            return False
        
        if self.is_running:
            logger.info("Monitor already running")
            return True
        
        # Start monitoring thread
        self.is_running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info(f"Started monitoring {len(self.monitored_buckets)} buckets")
        return True
    
    def stop_monitoring(self):
        """Stop monitoring S3 buckets"""
        self.is_running = False
        logger.info("Stopping document monitoring")
    
    def pause_processing(self):
        """Pause document processing but continue monitoring"""
        self.processing_paused = True
        logger.info("Document processing paused")
    
    def resume_processing(self):
        """Resume document processing"""
        self.processing_paused = False
        logger.info("Document processing resumed")
    
    def _monitor_loop(self, interval=60):
        """Main monitoring loop
        
        Args:
            interval (int): Check interval in seconds
        """
        while self.is_running:
            try:
                # Check each monitored bucket
                for bucket in self.monitored_buckets:
                    self._check_bucket(bucket)
                
                # Check scheduled reviews
                self._check_review_schedule()
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {str(e)}")
            
            # Wait for next check
            time.sleep(interval)
    
    def _check_bucket(self, bucket_name):
        """Check a bucket for new documents
        
        Args:
            bucket_name (str): S3 bucket to check
        """
        try:
            # List PDF files in the bucket
            logger.info(f"Checking bucket {bucket_name} for new documents")
            pdfs = self.aws_s3_client.list_pdf_files(bucket_name)
            
            # Filter for PDFs that are not in folders
            root_pdfs = [pdf for pdf in pdfs if '/' not in pdf['path']]
            
            if root_pdfs:
                logger.info(f"Found {len(root_pdfs)} PDFs at root level in {bucket_name}")
                
                # Process each unorganized PDF
                for pdf in root_pdfs:
                    file_key = f"{bucket_name}:{pdf['path']}"
                    
                    if file_key not in self.processed_files:
                        logger.info(f"Processing new document: {pdf['path']}")
                        
                        # Process the document if not paused
                        if not self.processing_paused:
                            # Process with document flow
                            result = self.document_flow.process_new_document(bucket_name, pdf['path'])
                            
                            if result.get("success", False):
                                self.processed_files.add(file_key)
                                logger.info(f"Successfully processed document: {pdf['path']}")
                            else:
                                logger.error(f"Failed to process document: {pdf['path']}")
        except Exception as e:
            logger.error(f"Error checking bucket {bucket_name}: {str(e)}")
    
    def _check_for_critical_content(self, local_path, object_key):
        """Check document for critical content that requires immediate attention
        
        Args:
            local_path (str): Local path to document
            object_key (str): S3 object key
        """
        try:
            # Use WatsonX to check for critical content
            if not self.model:
                return
                
            from dockling_tool import DocklingPDFTool
            tool = DocklingPDFTool(local_path, self.model)
            
            # Search for urgent/critical content
            content = tool.search("urgent critical deadline compliance risk immediate action required")
            
            critical_prompt = f"""
            Analyze the following document content for critical items that require immediate attention.
            Look for deadlines, compliance issues, urgent requests, or high-priority action items.
            
            Document: {os.path.basename(object_key)}
            Content: {content}
            
            Return a JSON with these fields:
            - is_critical: boolean indicating if this is a critical document
            - reason: brief explanation of why it's critical or not
            - deadline: any deadline mentioned (or null)
            - action_required: what action is needed (or null)
            - suggested_recipients: array of roles who should be notified
            
            Respond only with the JSON.
            """
            
            response = self.model.generate_text(critical_prompt)
            
            try:
                # Parse the response
                critical_data = json.loads(response)
                
                if critical_data.get("is_critical", False):
                    logger.info(f"Critical document detected: {object_key}")
                    
                    # This would trigger notifications to appropriate parties
                    # based on critical_data["suggested_recipients"]
                    
                    # Add to review schedule if there's a deadline
                    if "deadline" in critical_data and critical_data["deadline"]:
                        try:
                            # Try to parse the deadline
                            deadline_date = datetime.strptime(critical_data["deadline"], "%Y-%m-%d")
                            
                            # Schedule review before the deadline
                            review_date = deadline_date - timedelta(days=5)
                            
                            self.review_schedule[object_key] = {
                                "document": object_key,
                                "review_date": review_date,
                                "reason": f"Deadline approaching: {critical_data['deadline']}",
                                "action": critical_data.get("action_required", "Review document")
                            }
                            
                            logger.info(f"Scheduled review for {object_key} on {review_date}")
                        except Exception as e:
                            logger.error(f"Error parsing deadline: {str(e)}")
            except json.JSONDecodeError:
                logger.error(f"Error parsing critical content response: {response[:100]}...")
        except Exception as e:
            logger.error(f"Error checking for critical content: {str(e)}")
    
    def _check_review_schedule(self):
        """Check for scheduled document reviews"""
        now = datetime.now()
        
        # Only check once per hour to avoid excessive processing
        if (now - self.last_notification_check).total_seconds() < 3600:
            return
            
        self.last_notification_check = now
        
        # Check each scheduled review
        reviews_to_process = []
        for doc_key, review_info in self.review_schedule.items():
            review_date = review_info["review_date"]
            
            if review_date <= now:
                logger.info(f"Review due for document: {doc_key}")
                reviews_to_process.append((doc_key, review_info))
        
        # Process due reviews
        for doc_key, review_info in reviews_to_process:
            try:
                # This would send notifications about the review
                logger.info(f"Sending review notification for {doc_key}: {review_info['reason']}")
                
                # Remove from schedule after processing
                del self.review_schedule[doc_key]
            except Exception as e:
                logger.error(f"Error processing review for {doc_key}: {str(e)}")

# integration_utils.py
def setup_document_monitoring(app_state):
    """Set up document monitoring based on app state
    
    Args:
        app_state: Streamlit session state
    """
    # Check if we have the necessary components
    if ('aws_s3_client' not in app_state or 
            'document_flow' not in app_state or 
            'pdf_agent' not in app_state):
        return False
    
    # Initialize document monitor if not already created
    if 'document_monitor' not in app_state:
        app_state.document_monitor = DocumentMonitor(
            app_state.aws_s3_client,
            app_state.document_flow,
            app_state.pdf_agent.model
        )
    
    # Start monitoring if buckets are configured
    if 'monitored_buckets' in app_state and app_state.monitored_buckets:
        return app_state.document_monitor.start_monitoring(app_state.monitored_buckets)
    
    return False

def trigger_scan_now(app_state):
    """Trigger an immediate scan of all monitored buckets
    
    Args:
        app_state: Streamlit session state
        
    Returns:
        bool: Success status
    """
    if 'document_monitor' not in app_state:
        return False
    
    # Create a thread to run the scan to avoid blocking the UI
    def scan_buckets():
        monitor = app_state.document_monitor
        for bucket in monitor.monitored_buckets:
            try:
                monitor._check_bucket(bucket)
            except Exception as e:
                logger.error(f"Error in manual scan of {bucket}: {str(e)}")
    
    # Start the scan in a thread
    scan_thread = threading.Thread(target=scan_buckets, daemon=True)
    scan_thread.start()
    
    return True

class WorkflowScheduler:
    """Scheduler for document workflows and reminders"""
    
    def __init__(self, ms_graph_client=None):
        """Initialize the workflow scheduler
        
        Args:
            ms_graph_client: Microsoft Graph client for email and calendar
        """
        self.ms_graph_client = ms_graph_client
        self.scheduled_workflows = {}
        self.review_reminders = {}
        self.next_workflow_id = 1
    
    def schedule_workflow(self, document_key, workflow_type, due_date, assignees=None, details=None):
        """Schedule a document workflow
        
        Args:
            document_key (str): Document identifier
            workflow_type (str): Type of workflow (review, approval, etc.)
            due_date (datetime): Due date for the workflow
            assignees (list): People assigned to the workflow
            details (dict): Additional workflow details
            
        Returns:
            int: Workflow ID
        """
        workflow_id = self.next_workflow_id
        self.next_workflow_id += 1
        
        self.scheduled_workflows[workflow_id] = {
            "id": workflow_id,
            "document_key": document_key,
            "workflow_type": workflow_type,
            "due_date": due_date,
            "assignees": assignees or [],
            "details": details or {},
            "status": "scheduled",
            "created_at": datetime.now()
        }
        
        logger.info(f"Scheduled workflow {workflow_id} for {document_key}: {workflow_type}")
        
        # Send workflow assignment notifications if Graph client available
        if self.ms_graph_client and assignees:
            for assignee in assignees:
                self._send_workflow_assignment(workflow_id, assignee)
        
        return workflow_id
    
    def complete_workflow(self, workflow_id, result=None):
        """Mark a workflow as complete
        
        Args:
            workflow_id (int): Workflow ID
            result (dict): Workflow completion results
            
        Returns:
            bool: Success status
        """
        if workflow_id not in self.scheduled_workflows:
            return False
        
        workflow = self.scheduled_workflows[workflow_id]
        workflow["status"] = "completed"
        workflow["completed_at"] = datetime.now()
        workflow["result"] = result
        
        logger.info(f"Workflow {workflow_id} marked as complete")
        
        # Send completion notifications if needed
        if self.ms_graph_client and workflow.get("assignees"):
            for assignee in workflow["assignees"]:
                self._send_workflow_completion(workflow_id, assignee, result)
        
        return True
    
    def schedule_review(self, document_key, review_date, reviewer_email, document_path=None):
        """Schedule a document review reminder
        
        Args:
            document_key (str): Document identifier
            review_date (datetime): Date when the review should occur
            reviewer_email (str): Email of the reviewer
            document_path (str): Path to the document
            
        Returns:
            str: Review ID
        """
        review_id = f"review_{document_key}_{int(datetime.now().timestamp())}"
        
        self.review_reminders[review_id] = {
            "id": review_id,
            "document_key": document_key,
            "review_date": review_date,
            "reviewer_email": reviewer_email,
            "document_path": document_path,
            "status": "scheduled",
            "created_at": datetime.now()
        }
        
        logger.info(f"Scheduled review {review_id} for {document_key} on {review_date}")
        
        return review_id
    
    def get_active_workflows(self):
        """Get all active workflows
        
        Returns:
            list: Active workflows
        """
        active = []
        for workflow_id, workflow in self.scheduled_workflows.items():
            if workflow["status"] == "scheduled":
                active.append(workflow)
        
        return active
    
    def get_upcoming_reviews(self, days_ahead=7):
        """Get upcoming reviews
        
        Args:
            days_ahead (int): Number of days to look ahead
            
        Returns:
            list: Upcoming reviews
        """
        upcoming = []
        cutoff_date = datetime.now() + timedelta(days=days_ahead)
        
        for review_id, review in self.review_reminders.items():
            if review["status"] == "scheduled" and review["review_date"] <= cutoff_date:
                upcoming.append(review)
        
        return upcoming
    
    def _send_workflow_assignment(self, workflow_id, assignee_email):
        """Send workflow assignment notification
        
        Args:
            workflow_id (int): Workflow ID
            assignee_email (str): Assignee email
        """
        if not self.ms_graph_client:
            return
            
        workflow = self.scheduled_workflows[workflow_id]
        document_key = workflow["document_key"]
        workflow_type = workflow["workflow_type"]
        due_date = workflow["due_date"].strftime("%A, %B %d, %Y")
        
        subject = f"Document Workflow Assignment: {workflow_type} for {document_key}"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333333;">
            <h2>Document Workflow Assignment</h2>
            <p>You have been assigned to a document workflow:</p>
            
            <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                <p><strong>Document:</strong> {document_key}</p>
                <p><strong>Workflow:</strong> {workflow_type}</p>
                <p><strong>Due Date:</strong> {due_date}</p>
            </div>
            
            <p>Please complete this workflow by the due date.</p>
            
            <hr>
            <p style="color: #666666; font-size: 0.9em;">This notification was generated automatically by the WatsonX PDF Agent.</p>
        </body>
        </html>
        """
        
        self.ms_graph_client.send_email(assignee_email, subject, body)
    
    def _send_workflow_completion(self, workflow_id, assignee_email, result):
        """Send workflow completion notification
        
        Args:
            workflow_id (int): Workflow ID
            assignee_email (str): Assignee email
            result (dict): Workflow result
        """
        # Implementation would be similar to _send_workflow_assignment
        pass