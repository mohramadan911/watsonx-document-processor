# pdf_agent.py
from crewai import Agent, Task, Crew, Process
import tempfile
import logging
import os
import json

# Import the Dockling tool
from dockling_tool import DocklingPDFTool

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WatsonxPDFAgent:
    """PDF Agent powered by WatsonX and CrewAI"""
    
    def __init__(self, model, pdf_search_tool=None, ms_graph_client=None):
        """Initialize the WatsonX PDF Agent
        
        Args:
            model: WatsonX model instance
            pdf_search_tool: Tool for searching PDF content
            ms_graph_client: Microsoft Graph client for email functionality
        """
        self.model = model
        self.pdf_search_tool = pdf_search_tool
        self.ms_graph_client = ms_graph_client
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
        
        # New Recommendation Agent - Specialized in providing next steps
        self.recommender_agent = Agent(
            name="Action Recommender",
            role="Recommendation Specialist",
            goal="Provide practical next steps and recommendations based on document content",
            backstory="I am a recommendation specialist with expertise in identifying actionable insights and suggesting practical next steps.",
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
        
        self.recommend_actions_task = Task(
            description="Based on the document analysis, recommend practical next steps for the user. Consider if follow-ups, reviews, or sharing with others would be valuable. Provide 2-3 specific, actionable recommendations.",
            agent=self.recommender_agent,
            expected_output="A list of practical recommendations and next steps"
        )
        
        # Create crew
        self.crew = Crew(
            agents=[self.reader_agent, self.analyst_agent, self.recommender_agent],
            tasks=[self.read_document_task, self.analyze_document_task, self.recommend_actions_task],
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
            
            # If there's a specific query, handle different query types
            if query and query.strip():
                # Check for email sending command
                if "send email" in query.lower() or "email" in query.lower():
                    return self.handle_email_request(query, pdf_path)
                
                # Check for reminder setting
                elif "remind" in query.lower() or "reminder" in query.lower() or "schedule" in query.lower():
                    return self.handle_reminder_request(query, pdf_path)
                
                # Check for recommendations request
                elif any(word in query.lower() for word in ["recommend", "next steps", "what should i do", "action"]):
                    search_results = self.pdf_search_tool.search("main points key findings recommendations")
                    
                    augmented_prompt = f"""
                    The user wants recommendations or next steps based on this document.
                    
                    Here is content from the uploaded PDF document:
                    {search_results}
                    
                    Please provide 3-5 specific, practical recommendations or next actions based on this document. For each recommendation:
                    1. Describe the specific action
                    2. Explain why it's important
                    3. Suggest a timeline if applicable
                    
                    Include both document-specific actions (like follow-ups on content) and general actions (like sharing with colleagues or setting a review date).
                    """
                    
                    return self.model.generate_text(augmented_prompt)
                
                # Standard summarization request
                elif "summarize" in query.lower() and any(word in query.lower() for word in ["pdf", "document", "file", "the"]):
                    search_results = self.pdf_search_tool.search("main topics key points overview executive summary")
                    
                    augmented_prompt = f"""
                    The user wants a summary of the PDF document.
                    
                    Here is content from the uploaded PDF document:
                    {search_results}
                    
                    Please provide a comprehensive summary of this document covering the main points.
                    """
                else:
                    # General question about the document
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
                The user has uploaded a PDF document and wants a comprehensive summary with recommendations.
                
                Here is relevant content from the document:
                {search_results}
                
                Please provide a detailed, well-structured response with the following sections:
                
                ## Summary
                Provide a detailed summary covering:
                - The main purpose of the document
                - Key points and findings
                - Important details and insights
                
                ## Recommendations
                Based on the document content, provide 3-5 practical recommendations or next steps, such as:
                - Specific actions to take based on the document content
                - Suggestions for sharing this document with relevant parties
                - Recommended follow-up activities
                - Timeline for reviewing this information again
                
                Be specific and actionable in your recommendations.
                """
                
                return self.model.generate_text(augmented_prompt)
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return f"Error processing document: {str(e)}"
    
    def handle_email_request(self, query, pdf_path):
        """Handle a request to send an email about the document
        
        Args:
            query (str): The user's email request
            pdf_path (str): Path to the PDF file
            
        Returns:
            str: Response to the email request
        """
        if not self.ms_graph_client:
            return "I can't send emails at the moment because the Microsoft Graph client is not configured. Please set up email in the Configuration tab first."
        
        # Extract email information from the query
        recipient = None
        subject = os.path.basename(pdf_path)
        include_summary = True
        attach_pdf = True
        
        # Try to extract recipient
        if "to:" in query.lower():
            parts = query.lower().split("to:")
            if len(parts) > 1:
                recipient_part = parts[1].strip()
                # Extract email address if it's in a typical format
                import re
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', recipient_part)
                if email_match:
                    recipient = email_match.group(0)
        
        if not recipient:
            return "I'd be happy to help you send an email about this document. Please provide the recipient's email address by saying something like 'Send email to: example@email.com'"
        
        # Generate a summary for the email
        if include_summary:
            search_results = self.pdf_search_tool.search("main topics key points overview executive summary")
            
            summary_prompt = f"""
            Create a professional email summary about this document:
            {search_results}
            
            The email should be concise but informative, highlighting:
            1. The main purpose of the document
            2. 2-3 key points
            3. Any important deadlines or action items
            
            Format it as an email body that could be sent to a colleague.
            """
            
            email_body = self.model.generate_text(summary_prompt)
        else:
            email_body = f"Please find attached the document: {subject}"
        
        # Send the email
        attachments = [pdf_path] if attach_pdf else None
        
        try:
            if self.ms_graph_client.create_email_with_summary(
                recipient, 
                subject, 
                email_body, 
                pdf_path=attachments[0] if attachments else None
            ):
                return f"✅ Email sent successfully to {recipient} with a summary of the document."
            else:
                return f"❌ Failed to send email to {recipient}. Please check the email configuration and try again."
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return f"❌ Error sending email: {str(e)}"
    
    def handle_reminder_request(self, query, pdf_path):
        """Handle a request to create a reminder for the document
        
        Args:
            query (str): The user's reminder request
            pdf_path (str): Path to the PDF file
            
        Returns:
            str: Response to the reminder request
        """
        if not self.ms_graph_client:
            return "I can't set reminders at the moment because the Microsoft Graph client is not configured. Please set up email in the Configuration tab first."
        
        # Try to extract a date from the query
        import re
        from datetime import datetime, timedelta
        
        # Look for "in X days/weeks/months" patterns
        time_patterns = {
            'day': re.compile(r'in\s+(\d+)\s+day', re.IGNORECASE),
            'week': re.compile(r'in\s+(\d+)\s+week', re.IGNORECASE),
            'month': re.compile(r'in\s+(\d+)\s+month', re.IGNORECASE)
        }
        
        reminder_date = None
        for unit, pattern in time_patterns.items():
            match = pattern.search(query)
            if match:
                amount = int(match.group(1))
                if unit == 'day':
                    reminder_date = datetime.now() + timedelta(days=amount)
                elif unit == 'week':
                    reminder_date = datetime.now() + timedelta(weeks=amount)
                elif unit == 'month':
                    reminder_date = datetime.now() + timedelta(days=amount*30)  # Approximation
                break
        
        if not reminder_date:
            # Default to 1 week if no specific time found
            reminder_date = datetime.now() + timedelta(weeks=1)
        
        # Format date for display
        formatted_date = reminder_date.strftime("%A, %B %d, %Y")
        
        # Get document name
        doc_name = os.path.basename(pdf_path)
        
        # Create a reminder email (could be integrated with calendar in future versions)
        subject = f"Reminder to review: {doc_name}"
        
        search_results = self.pdf_search_tool.search("main topics key points")
        reminder_prompt = f"""
        Create a brief reminder email about this document:
        {search_results}
        
        The reminder should include:
        1. The name of the document: {doc_name}
        2. A brief recap of what the document contains (1-2 sentences)
        3. Why it's important to review it again
        
        Format it as a friendly reminder email.
        """
        
        email_body = self.model.generate_text(reminder_prompt)
        
        # Add the reminder date to the email
        email_body = f"⏰ REMINDER SET FOR: {formatted_date}\n\n" + email_body
        
        # Get the user's email
        user_email = self.ms_graph_client.user_email
        
        try:
            if self.ms_graph_client.create_email_with_summary(
                user_email, 
                subject, 
                email_body, 
                pdf_path=pdf_path
            ):
                return f"✅ Reminder email scheduled for {formatted_date}. I'll send a reminder to review '{doc_name}' to {user_email}."
            else:
                return f"❌ Failed to create reminder email. Please check the email configuration and try again."
        except Exception as e:
            logger.error(f"Error creating reminder: {str(e)}")
            return f"❌ Error creating reminder: {str(e)}"
    
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