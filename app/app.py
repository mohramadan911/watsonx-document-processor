# app.py
import streamlit as st
from ibm_watson_machine_learning.foundation_models import Model
import tempfile
import json
import os
import logging
from datetime import datetime
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()

# Import custom modules
from aws_client import AWSS3Client
from ms_graph import MSGraphClient
from pdf_agent import WatsonxPDFAgent
from custom_pdf_tool import CustomPDFSearchTool
# from crewai_tools import PDFSearchTool

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# App title and configuration
st.set_page_config(
    page_title="WatsonX PDF Agent",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    st.title('WatsonX PDF Agent 🤖')
    st.caption("🚀 An enhanced agent powered by WatsonX.ai with AWS S3 & Microsoft 365 Email capabilities")

    # Session state initialization
    if 'pdf_path' not in st.session_state:
        st.session_state.pdf_path = None

    if 'pdf_search_tool' not in st.session_state:
        st.session_state.pdf_search_tool = None
        
    if 'pdf_agent' not in st.session_state:
        st.session_state.pdf_agent = None
        
    if 'aws_s3_client' not in st.session_state:
        st.session_state.aws_s3_client = None
        
    if 'ms_graph_client' not in st.session_state:
        st.session_state.ms_graph_client = None
        
    if 'messages' not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "👋 Hello! Please upload or select a PDF document, then you can ask questions, request a summary, or email it."}]

    # Auto-initialize connections if enabled
    if os.getenv("AUTO_INITIALIZE", "false").lower() == "true":
        # Auto-init WatsonX model
        if os.getenv("WATSONX_API_KEY") and 'pdf_agent' not in st.session_state:
            with st.spinner("Auto-initializing WatsonX model..."):
                try:
                    my_credentials = {
                        "url": os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
                        "apikey": os.getenv("WATSONX_API_KEY")
                    }
                    model_name = os.getenv("WATSONX_MODEL", "meta-llama/llama-3-3-70b-instruct")
                    params = json.loads(os.getenv("WATSONX_MODEL_PARAMS", 
                                              '{"decoding_method":"sample", "max_new_tokens":500, "temperature":0.5}'))
                    project_id = os.getenv("WATSONX_PROJECT_ID", "ea1bfd72-28d6-4a4d-8668-c1de89865515")
                    space_id = None
                    verify = False
                    
                    model = Model(model_name, my_credentials, params, project_id, space_id, verify)
                    st.session_state.pdf_agent = WatsonxPDFAgent(model)
                    st.success("WatsonX model auto-initialized successfully")
                except Exception as e:
                    st.error(f"Error auto-initializing WatsonX model: {str(e)}")
                    logger.error(f"Error auto-initializing WatsonX model: {str(e)}")
        
        # Auto-init AWS S3 client
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY") and 'aws_s3_client' not in st.session_state:
            with st.spinner("Auto-connecting to AWS S3..."):
                try:
                    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
                    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
                    aws_region = os.getenv("AWS_REGION", "us-east-1")
                    
                    s3_client = AWSS3Client(aws_access_key, aws_secret_key, aws_region)
                    
                    if s3_client.connect():
                        st.session_state.aws_s3_client = s3_client
                        
                        # Get available buckets
                        buckets = s3_client.list_buckets()
                        if buckets:
                            st.session_state.aws_buckets = buckets
                            st.success(f"Auto-connected to AWS S3: Found {len(buckets)} buckets")
                        else:
                            st.warning("Connected to AWS S3 but no buckets found")
                    else:
                        st.error("Failed to auto-connect to AWS S3")
                except Exception as e:
                    st.error(f"Error auto-connecting to AWS S3: {str(e)}")
                    logger.error(f"Error auto-connecting to AWS S3: {str(e)}")
        
        # Auto-init Microsoft Graph client
        if (os.getenv("MS_CLIENT_ID") and os.getenv("MS_CLIENT_SECRET") and 
            os.getenv("MS_TENANT_ID") and os.getenv("MS_USER_EMAIL") and 
            'ms_graph_client' not in st.session_state):
            with st.spinner("Auto-connecting to Microsoft Graph API..."):
                try:
                    ms_client_id = os.getenv("MS_CLIENT_ID")
                    ms_client_secret = os.getenv("MS_CLIENT_SECRET")
                    ms_tenant_id = os.getenv("MS_TENANT_ID")
                    ms_user_email = os.getenv("MS_USER_EMAIL")
                    
                    ms_graph_client = MSGraphClient(ms_client_id, ms_client_secret, ms_tenant_id, ms_user_email)
                    
                    if ms_graph_client.get_token():
                        st.session_state.ms_graph_client = ms_graph_client
                        st.success("Auto-connected to Microsoft Graph API successfully")
                    else:
                        st.error("Failed to auto-connect to Microsoft Graph API")
                except Exception as e:
                    st.error(f"Error auto-connecting to Microsoft Graph API: {str(e)}")
                    logger.error(f"Error auto-connecting to Microsoft Graph API: {str(e)}")

    # Main layout with tabs
    tab1, tab2, tab3 = st.tabs(["Chat", "Configuration", "Email"])
    
    # Tab 1: Chat
    with tab1:
        # Document info section - show when document is loaded
        if st.session_state.pdf_path:
            file_name = os.path.basename(st.session_state.pdf_path)
            st.info(f"📄 Current document: {file_name}")
            
            # Get document metadata if we have a PDF agent
            if st.session_state.pdf_agent:
                with st.expander("Document Details"):
                    metadata = st.session_state.pdf_agent.get_document_metadata(st.session_state.pdf_path)
                    
                    if "error" not in metadata:
                        st.write(f"**Title:** {metadata.get('title', 'Unknown')}")
                        st.write(f"**Author:** {metadata.get('author', 'Unknown')}")
                        st.write(f"**Date:** {metadata.get('date', 'Unknown')}")
                        st.write(f"**Size:** {metadata.get('file_size', 0) / 1024:.1f} KB")
                        
                        if "topics" in metadata and metadata["topics"]:
                            st.write("**Main Topics:**")
                            for topic in metadata["topics"]:
                                st.write(f"- {topic}")
        
        # Display chat messages
        for message in st.session_state.messages:
            st.chat_message(message['role']).markdown(message['content'])
        
        # Chat input
        if st.session_state.pdf_path and st.session_state.pdf_agent:
            chat_placeholder = "Ask a question about the document or type 'summarize' to get a summary"
        else:
            chat_placeholder = "Please upload or select a document first"
            
        prompt = st.chat_input(chat_placeholder, disabled=not st.session_state.pdf_path)
        
        if prompt:
            # Display user message
            st.chat_message('user').markdown(prompt)
            st.session_state.messages.append({'role': 'user', 'content': prompt})
            
            # Process the query with the PDF agent
            with st.spinner("Processing your request..."):
                response = st.session_state.pdf_agent.process_document(st.session_state.pdf_path, prompt)
            
            # Display AI response
            st.chat_message('assistant').markdown(response)
            st.session_state.messages.append({'role': 'assistant', 'content': response})
    
    # Tab 2: Configuration
    with tab2:
        st.header("Configuration")
        
        # WatsonX Configuration
        st.subheader("WatsonX Configuration")
        watsonx_api_key = st.text_input("WatsonX API Key", key="watsonx_api_key", 
                                     value=os.getenv("WATSONX_API_KEY", ""), type="password")
        watsonx_url = st.text_input("WatsonX URL", key="watsonx_url", 
                                  value=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"), 
                                  type="default")   
        watsonx_model = st.selectbox(
            "Model", 
            ["meta-llama/llama-3-3-70b-instruct", "ibm/granite-20b-instruct-v2", "meta-llama/llama-2-70b-chat"],
            key="watsonx_model"
        )
        watsonx_model_params = st.text_area(
            "Model Parameters", 
            value=os.getenv("WATSONX_MODEL_PARAMS", '{"decoding_method":"sample", "max_new_tokens":500, "temperature":0.5}'), 
            key="watsonx_model_params"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            # AWS S3 Configuration
            st.subheader("AWS S3 Configuration")
            aws_access_key = st.text_input("AWS Access Key", key="aws_access_key", 
                                        value=os.getenv("AWS_ACCESS_KEY_ID", ""))
            aws_secret_key = st.text_input("AWS Secret Key", key="aws_secret_key", 
                                        value=os.getenv("AWS_SECRET_ACCESS_KEY", ""), 
                                        type="password")
            aws_region = st.text_input("AWS Region", key="aws_region", 
                                    value=os.getenv("AWS_REGION", "us-east-1"))
            
            if st.button("Connect to AWS S3"):
                try:
                    st.session_state.aws_s3_client = AWSS3Client(
                        aws_access_key,
                        aws_secret_key,
                        aws_region
                    )
                    
                    if st.session_state.aws_s3_client.connect():
                        st.success("Connected to AWS S3 successfully!")
                        
                        # Get available buckets
                        buckets = st.session_state.aws_s3_client.list_buckets()
                        if buckets:
                            st.session_state.aws_buckets = buckets
                            st.success(f"Found {len(buckets)} buckets")
                        else:
                            st.warning("No buckets found")
                    else:
                        st.error("Failed to connect to AWS S3")
                except Exception as e:
                    st.error(f"Error connecting to AWS S3: {str(e)}")
        
        # In the Configuration tab, under Microsoft Graph API Configuration
    with col2:
        # Microsoft Graph API Configuration
        st.subheader("Microsoft Graph API Configuration")
        ms_client_id = st.text_input("Microsoft App Client ID", key="ms_client_id", 
                                value=os.getenv("MS_CLIENT_ID", ""))
        ms_client_secret = st.text_input("Microsoft App Client Secret", key="ms_client_secret", 
                                    value=os.getenv("MS_CLIENT_SECRET", ""), 
                                    type="password")
        ms_tenant_id = st.text_input("Microsoft Tenant ID", key="ms_tenant_id", 
                                value=os.getenv("MS_TENANT_ID", ""))
        ms_user_email = st.text_input("Microsoft User Email", key="ms_user_email", 
                                value=os.getenv("MS_USER_EMAIL", ""))
        
        col2a, col2b = st.columns(2)
        
        with col2a:
            if st.button("Configure Microsoft Graph"):
                try:
                    st.session_state.ms_graph_client = MSGraphClient(
                        ms_client_id,
                        ms_client_secret,
                        ms_tenant_id,
                        ms_user_email
                    )
                    
                    if st.session_state.ms_graph_client.get_token():
                        st.success("Connected to Microsoft Graph API successfully!")
                    else:
                        st.error("Failed to connect to Microsoft Graph API")
                except Exception as e:
                    st.error(f"Error connecting to Microsoft Graph API: {str(e)}")
        
        with col2b:
            # Add the Reset Configuration button here
            if st.button("Reset Configuration"):
                # Clear existing connection
                if 'ms_graph_client' in st.session_state:
                    del st.session_state.ms_graph_client
                
                # Reload environment variables
                dotenv.load_dotenv(override=True)
                
                st.success("Configuration reset successfully")
                st.rerun()  # Updated from st.experimental_rerun()
        
        
        # Initialize the WatsonX model
        if watsonx_api_key and st.button("Initialize WatsonX Model"):
            try:
                my_credentials = {
                    "url": watsonx_url, 
                    "apikey": watsonx_api_key
                }
                params = json.loads(watsonx_model_params)      
                project_id = os.getenv("WATSONX_PROJECT_ID", "ea1bfd72-28d6-4a4d-8668-c1de89865515")
                space_id = None
                verify = False
                
                model = Model(watsonx_model, my_credentials, params, project_id, space_id, verify)
                st.success(f"WatsonX model initialized: {watsonx_model}")
                
                # Initialize PDF agent
                if 'pdf_search_tool' in st.session_state and st.session_state.pdf_search_tool:
                    st.session_state.pdf_agent = WatsonxPDFAgent(model, st.session_state.pdf_search_tool)
                else:
                    st.session_state.pdf_agent = WatsonxPDFAgent(model)
                
                # Test model with a simple query
                with st.spinner("Testing model..."):
                    test_response = model.generate_text("Hello, please confirm if you're working correctly.")
                    st.success("Model test successful!")
                    st.write("Test response:", test_response)
                    
            except Exception as e:
                st.error(f"Error initializing WatsonX model: {str(e)}")
        
        # Document source selection
        st.subheader("Document Source")
        doc_source = st.radio("Select document source", ["Upload PDF", "AWS S3"])
        
        if doc_source == "Upload PDF":
            # Upload PDF directly
            uploaded_file = st.file_uploader("Upload a PDF document", type="pdf")
            
            if uploaded_file is not None:
                # Create a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    st.session_state.pdf_path = tmp_file.name
                
                st.success(f"PDF uploaded: {uploaded_file.name}")
                
                # Process with Dockling if model is initialized
                if 'pdf_agent' in st.session_state and st.session_state.pdf_agent:
                    try:
                        with st.spinner("Processing document with Dockling..."):
                            st.session_state.pdf_agent.process_document(st.session_state.pdf_path)
                        st.success("Document processed successfully")
                    except Exception as e:
                        st.error(f"Error processing document: {str(e)}")
        
        elif doc_source == "AWS S3" and st.session_state.aws_s3_client:
            # Get list of buckets
            if 'aws_buckets' in st.session_state and st.session_state.aws_buckets:
                selected_bucket = st.selectbox(
                    "Select S3 Bucket", 
                    options=st.session_state.aws_buckets,
                    index=0 if os.getenv("S3_BUCKET_NAME") not in st.session_state.aws_buckets else 
                          st.session_state.aws_buckets.index(os.getenv("S3_BUCKET_NAME"))
                )
                
                if st.button("List PDFs"):
                    with st.spinner("Fetching PDFs..."):
                        pdf_objects = st.session_state.aws_s3_client.list_objects(selected_bucket)
                        
                        if pdf_objects:
                            st.session_state.pdf_objects = pdf_objects
                            st.success(f"Found {len(pdf_objects)} PDF documents")
                        else:
                            st.warning("No PDF documents found in this bucket")
                
                # Show list of PDFs if available
                if 'pdf_objects' in st.session_state and st.session_state.pdf_objects:
                    selected_pdf = st.selectbox(
                        "Select PDF Document",
                        options=[obj['name'] for obj in st.session_state.pdf_objects],
                        format_func=lambda x: x
                    )
                    
                    if st.button("Download Selected PDF"):
                        # Find the selected PDF object
                        pdf_obj = next((obj for obj in st.session_state.pdf_objects if obj['name'] == selected_pdf), None)
                        
                        if pdf_obj:
                            with st.spinner("Downloading PDF..."):
                                # Create a temporary file
                                temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                                temp_pdf.close()
                                
                                # Download the PDF
                                if st.session_state.aws_s3_client.download_file(selected_bucket, pdf_obj['key'], temp_pdf.name):
                                    st.session_state.pdf_path = temp_pdf.name
                                    st.success(f"Downloaded PDF: {selected_pdf}")
                                    
                                    # Initialize the PDF search tool
                                    try:
                                        if 'pdf_agent' in st.session_state and st.session_state.pdf_agent:
                                            # Get the model from the existing PDF agent
                                            watsonx_model = st.session_state.pdf_agent.model
                                            st.session_state.pdf_search_tool = CustomPDFSearchTool(
                                                pdf=st.session_state.pdf_path,
                                                watsonx_model=watsonx_model
                                            )
                                        else:
                                            # If there's no PDF agent yet, we can't initialize the tool
                                            st.error("Please initialize WatsonX model first before downloading a PDF")
                                            st.stop()
                                            
                                        st.success("PDF search tool initialized successfully")
                                        
                                        # Initialize the PDF agent if model is already set up
                                        if 'pdf_agent' in st.session_state and st.session_state.pdf_agent:
                                            st.session_state.pdf_agent.pdf_search_tool = st.session_state.pdf_search_tool
                                            st.session_state.pdf_agent.create_agents_and_crew()
                                    except Exception as e:
                                        st.error(f"Error initializing PDF search tool: {str(e)}")
                                else:
                                    st.error(f"Failed to download PDF: {selected_pdf}")
    
    # Tab 3: Email
    with tab3:
        st.header("Email Document Summary")
        
        if not st.session_state.pdf_path:
            st.warning("Please upload or select a PDF document first")
        elif not st.session_state.ms_graph_client:
            st.warning("Please configure Microsoft Graph API in the Configuration tab")
        elif not st.session_state.pdf_agent:
            st.warning("Please initialize the WatsonX model in the Configuration tab")
        else:
            # Email form
            recipient_email = st.text_input("Recipient Email", key="recipient_email")
            cc_email = st.text_input("CC Email (optional)", key="cc_email")
            
            summarize_options = st.radio(
                "Summary Type",
                ["Executive Summary (Short)", "Comprehensive Summary (Long)", "Custom"]
            )
            
            if summarize_options == "Custom":
                custom_prompt = st.text_area(
                    "Custom Summary Instructions",
                    value="Please provide a detailed summary of the document focusing on...",
                    height=100
                )
            
            # Get file name
            file_name = os.path.basename(st.session_state.pdf_path)
            
            if st.button("Generate and Send Summary"):
                if not recipient_email:
                    st.error("Please enter a recipient email address")
                else:
                    with st.spinner("Generating summary and sending email..."):
                        # Generate the summary
                        if summarize_options == "Executive Summary (Short)":
                            query = "Generate a concise executive summary of this document highlighting the key points."
                        elif summarize_options == "Comprehensive Summary (Long)":
                            query = "Generate a comprehensive detailed summary of this document covering all major sections and important details."
                        else:  # Custom
                            query = custom_prompt
                        
                        # Process the document with the query
                        summary = st.session_state.pdf_agent.process_document(st.session_state.pdf_path, query)
                        
                        # Send email
                        if summary:
                            attach_pdf = st.checkbox("Attach original PDF to email", value=True)
                            attachments = [st.session_state.pdf_path] if attach_pdf else None
                            
                            # Send email with summary
                            if st.session_state.ms_graph_client.create_email_with_summary(
                                recipient_email, 
                                file_name, 
                                summary, 
                                pdf_path=attachments[0] if attachments else None
                            ):
                                st.success(f"Email sent successfully to {recipient_email}")
                                
                                # Show the summary
                                with st.expander("View Generated Summary", expanded=True):
                                    st.markdown(summary)
                            else:
                                st.error("Failed to send email")
                        else:
                            st.error("Failed to generate document summary")

if __name__ == "__main__":
    main()