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
    
    # Modify your process_document method in the WatsonxPDFAgent class to save results

    def process_document(self, pdf_path, query):
        """Process a document with a query using Watsonx
        
        Args:
            pdf_path (str): Path to the document
            query (str): User query or command
            
        Returns:
            str: Response text
        """
        try:
            # Special command handling - needs to happen before sending to search
            
            # Email command format: "send email to: example@example.com"
            if "send email to:" in query.lower():
                # Extract the email address
                email_parts = query.lower().split("send email to:", 1)
                if len(email_parts) > 1:
                    email_address = email_parts[1].strip()
                    
                    # Validate it's a proper email address (simple check)
                    if "@" in email_address and "." in email_address:
                        logger.info(f"Sending email to: {email_address}")
                        
                        if self.ms_graph_client:
                            # Use our enhanced email function
                            result = self.send_document_email(pdf_path, email_address)
                            
                            if result.get("success", False):
                                included_items = []
                                if result.get("included_summary", False):
                                    included_items.append("summary")
                                if result.get("included_recommendations", False):
                                    included_items.append("recommendations")
                                if result.get("included_classification", False):
                                    included_items.append("classification")
                                
                                if included_items:
                                    included_text = ", ".join(included_items)
                                    return f"✅ Email sent successfully to {email_address} including the document and {included_text}."
                                else:
                                    return f"✅ Email sent successfully to {email_address} with just the document attached."
                            else:
                                error_msg = result.get('error', 'Unknown error')
                                logger.error(f"Email sending failed: {error_msg}")
                                return f"❌ Failed to send email: {error_msg}"
                        else:
                            return "❌ Microsoft Graph client not configured. Please set up Microsoft Graph API in the Configuration tab."
                    else:
                        return f"❌ Invalid email address format: {email_address}"
            
            # Reminder command format: "remind me in X days/weeks"
            elif "remind me in" in query.lower():
                # Process reminder logic...
                pass
            
            # Check for summarization request
            elif "summarize" in query.lower() or "summary" in query.lower():
                summary_prompt = f"""
                Please provide a comprehensive summary of the document. Cover key points, main findings, 
                and any important details that would be relevant to someone who hasn't read the document.
                """
                
                # Search the document and generate the summary
                content = self.pdf_search_tool.search("document summary key points main topics")
                prompt = f"""
                Based on the following document content, please provide a comprehensive summary:
                
                {content}
                
                {summary_prompt}
                """
                
                response = self.model.generate_text(prompt)
                
                # Save the summary in session state for potential email use
                import streamlit as st
                st.session_state.document_summary = response
                
                return response
            
            # Check for recommendations request
            elif "recommend" in query.lower() or "recommendation" in query.lower() or "next steps" in query.lower():
                recommendation_prompt = f"""
                Based on this document, what recommendations would you make? What are the next steps 
                or actions that should be taken? Please provide specific and actionable recommendations.
                """
                
                # Search the document and generate recommendations
                content = self.pdf_search_tool.search("key findings recommendations next steps actions")
                prompt = f"""
                Based on the following document content, please provide recommendations and next steps:
                
                {content}
                
                {recommendation_prompt}
                """
                
                response = self.model.generate_text(prompt)
                
                # Save the recommendations in session state for potential email use
                import streamlit as st
                st.session_state.document_recommendations = response
                
                return response
                
            # For regular queries, use the PDF search tool
            if self.pdf_search_tool:
                content = self.pdf_search_tool.search(query)
                
                prompt = f"""
                Based on the following document content, please answer the query:
                
                Document content:
                {content}
                
                Query: {query}
                
                Please provide a detailed and accurate response.
                """
                
                return self.model.generate_text(prompt)
            else:
                return "Error: PDF search tool not initialized. Please try uploading the document again."
                
        except Exception as e:
            logger.error(f"Error in process_document: {str(e)}")
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
    # Add this method to your WatsonxPDFAgent class in pdf_agent.py

    def send_document_email(self, pdf_path, to_email):
        """Send an email with document analysis based on available information
        
        Args:
            pdf_path (str): Path to the PDF file
            to_email (str): Recipient email address
            
        Returns:
            dict: Result of the email sending operation
        """
        import streamlit as st
        
        if not self.ms_graph_client:
            return {
                "success": False, 
                "error": "Microsoft Graph client not configured"
            }
        
        try:
            # Get document name
            document_name = os.path.basename(pdf_path)
            
            # Check if we have a summary for this document in session state
            summary = None
            recommendations = None
            classification = None
            
            # Look for summary in session state or generate one
            if hasattr(st.session_state, 'document_summary') and st.session_state.document_summary:
                logger.info("Using existing document summary from session state")
                summary = st.session_state.document_summary
            else:
                # Generate a quick summary on the fly
                logger.info("Generating new document summary")
                content = self.pdf_search_tool.search("key points main topics executive summary")
                summary_prompt = f"""
                Based on the following document content, please provide a brief executive summary (3-5 key points):
                
                {content}
                """
                summary = self.model.generate_text(summary_prompt)
                st.session_state.document_summary = summary
            
            # Look for recommendations in session state
            if hasattr(st.session_state, 'document_recommendations') and st.session_state.document_recommendations:
                logger.info("Using existing document recommendations from session state")
                recommendations = st.session_state.document_recommendations
            
            # Look for classification in session state
            if hasattr(st.session_state, 'document_classification') and st.session_state.document_classification:
                logger.info("Using existing document classification from session state")
                classification = st.session_state.document_classification
            
            # Send the email with all available information
            logger.info(f"Sending email to {to_email} with document: {document_name}")
            result = self.ms_graph_client.create_email_with_summary(
                to_email=to_email,
                document_name=document_name,
                summary=summary,
                pdf_path=pdf_path,
                recommendations=recommendations,
                classification=classification
            )
            
            if result:
                logger.info(f"Email sent successfully to {to_email}")
                return {
                    "success": True,
                    "message": f"Email sent successfully to {to_email}",
                    "document": document_name,
                    "included_summary": summary is not None,
                    "included_recommendations": recommendations is not None,
                    "included_classification": classification is not None
                }
            else:
                logger.error(f"Failed to send email to {to_email}")
                return {
                    "success": False,
                    "error": "Failed to send email"
                }
        except Exception as e:
            logger.error(f"Error in send_document_email: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }