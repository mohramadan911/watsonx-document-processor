# app.py
import streamlit as st
from ibm_watson_machine_learning.foundation_models import Model
import tempfile
import json
import os
import logging
from datetime import datetime
import dotenv
from document_classifier import DocumentClassifier, DocumentCategory

# Load environment variables from .env file
dotenv.load_dotenv()

# Import custom modules
from aws_client import AWSS3Client
from ms_graph import MSGraphClient
from pdf_agent import WatsonxPDFAgent
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define a helper function to avoid circular imports
# Add this to your app.py file to replace the existing get_custom_pdf_tool function

def get_custom_pdf_tool(pdf_path, watsonx_model):
    """
    Dynamically import and initialize the CustomPDFSearchTool to avoid circular imports
    
    Args:
        pdf_path (str): Path to the PDF file
        watsonx_model: WatsonX model instance
        
    Returns:
        CustomPDFSearchTool: Initialized PDF search tool
    """
    import sys
    import os
    import logging
    
    # Get the local logger
    local_logger = logging.getLogger(__name__)
    
    # Make sure we're importing from the correct location
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    
    # Dynamic import to avoid circular references
    try:
        # First try normal import
        from custom_pdf_tool import CustomPDFSearchTool
        local_logger.info("Successfully imported CustomPDFSearchTool")
    except ImportError as e:
        local_logger.error(f"Import error: {str(e)}")
        # Try a more explicit import if the normal one fails
        import importlib.util
        try:
            module_path = os.path.join(app_dir, "custom_pdf_tool.py")
            local_logger.info(f"Trying to import from specific path: {module_path}")
            
            spec = importlib.util.spec_from_file_location("custom_pdf_tool", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            CustomPDFSearchTool = module.CustomPDFSearchTool
            local_logger.info("Successfully imported CustomPDFSearchTool using importlib")
        except Exception as e2:
            local_logger.error(f"Failed to import using importlib: {str(e2)}")
            raise ImportError(f"Could not import CustomPDFSearchTool: {str(e)} and then {str(e2)}")
    
    # Initialize and return the tool
    try:
        local_logger.info(f"Initializing CustomPDFSearchTool with path: {pdf_path}")
        return CustomPDFSearchTool(pdf_path, watsonx_model)
    except Exception as e:
        local_logger.error(f"Error initializing CustomPDFSearchTool: {str(e)}")
        raise
# Modify the classify_and_organize_document function in app.py to save classification results

def classify_and_organize_document(pdf_path, bucket_name=None, original_key=None):
    """Classify and organize a document
    
    Args:
        pdf_path (str): Path to the PDF file
        bucket_name (str, optional): S3 bucket name for organizing
        original_key (str, optional): Original S3 object key
        
    Returns:
        dict: Classification result
    """
    if not st.session_state.document_classifier:
        return {"success": False, "error": "Document classifier not initialized"}
    
    # Classify the document
    try:
        category, confidence, reasoning, custom_category_name = st.session_state.document_classifier.classify_document(pdf_path)
        
        # If a bucket is specified, organize the document in S3
        if bucket_name and st.session_state.aws_s3_client:
            result = st.session_state.document_classifier.organize_document(
                st.session_state.aws_s3_client,
                pdf_path,
                bucket_name,
                original_key
            )
            
            # Save classification results for email use
            if result.get("success", False):
                st.session_state.document_classification = result
            
            return result
        else:
            # Just return the classification without organizing
            if category == DocumentCategory.CUSTOM and custom_category_name:
                folder_name = custom_category_name
            else:
                folder_name = DocumentCategory.to_folder_name(category)
                
            result = {
                "success": True,
                "category": category.name,
                "custom_category": custom_category_name,
                "folder": folder_name,
                "confidence": confidence,
                "reasoning": reasoning,
                "organized": False,
                "is_custom_category": category == DocumentCategory.CUSTOM
            }
            
            # Save classification results for email use
            st.session_state.document_classification = result
            
            return result
    except Exception as e:
        logger.error(f"Error in classify_and_organize_document: {str(e)}")
        return {"success": False, "error": str(e)}
    
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

    if 'document_classifier' not in st.session_state:
        st.session_state.document_classifier = None
        
    if 'messages' not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": """
    👋 Welcome to the WatsonX PDF Agent! 

    This AI-powered assistant helps you analyze and interact with your PDF documents.

    **Getting Started:**
    1. Visit the **Configuration** tab to set up your WatsonX API key and connections
    2. Initialize the WatsonX model
    3. Return here to upload or select a PDF document from your computer or S3

    Once you've loaded a document, I can help you:
    - Answer questions about the document content
    - Generate comprehensive summaries
    - Provide recommendations based on the document
    - Send emails about the document (with Microsoft integration)
    - Set reminders for future review
    - Classify and organize your documents

    Need help? Click on the 'Chat Commands' section after loading a document to see available commands.
    """}]

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
                    
                    # Initialize MS Graph client if available
                    ms_graph_client = None
                    if (os.getenv("MS_CLIENT_ID") and os.getenv("MS_CLIENT_SECRET") and 
                        os.getenv("MS_TENANT_ID") and os.getenv("MS_USER_EMAIL")):
                        try:
                            ms_client_id = os.getenv("MS_CLIENT_ID")
                            ms_client_secret = os.getenv("MS_CLIENT_SECRET") 
                            ms_tenant_id = os.getenv("MS_TENANT_ID")
                            ms_user_email = os.getenv("MS_USER_EMAIL")
                            
                            ms_graph_client = MSGraphClient(
                                ms_client_id, ms_client_secret, ms_tenant_id, ms_user_email
                            )
                            
                            if ms_graph_client.get_token():
                                st.session_state.ms_graph_client = ms_graph_client
                                st.success("Auto-connected to Microsoft Graph API successfully")
                            else:
                                st.warning("Failed to auto-connect to Microsoft Graph API")
                                ms_graph_client = None
                        except Exception as e:
                            st.warning(f"Error auto-initializing Microsoft Graph client: {str(e)}")
                            ms_graph_client = None
                    
                    # Initialize PDF agent with MS Graph client
                    st.session_state.pdf_agent = WatsonxPDFAgent(
                        model, 
                        pdf_search_tool=None,
                        ms_graph_client=ms_graph_client
                    )

                    # Initialize the document classifier
                    st.session_state.document_classifier = DocumentClassifier(
                        model,  # This is the WatsonX model instance
                        pdf_search_tool=None
                    )
                    logger.info("Document classifier auto-initialized")
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
                            st.warning("No buckets found")
                    else:
                        st.error("Failed to auto-connect to AWS S3")
                except Exception as e:
                    st.error(f"Error auto-connecting to AWS S3: {str(e)}")
                    logger.error(f"Error auto-connecting to AWS S3: {str(e)}")
        
        # Auto-init Microsoft Graph client separately handled with the WatsonX model initialization above

    # Main layout with tabs
    tab1, tab2 = st.tabs(["Chat", "Configuration"])
    
    # Tab 1: Chat
    with tab1:
        # Document info section - show when document is loaded
        if st.session_state.pdf_path:
            file_name = os.path.basename(st.session_state.pdf_path)
            
            # Show document info bar at full width
            st.info(f"📄 Current document: {file_name}")
            
            # Create a row of three equally sized buttons below the info bar
            action_col1, action_col2, action_col3 = st.columns(3)
            
            with action_col1:
                if st.button("📝 Summarize", use_container_width=True):
                    # Add message to chat asking for summary
                    prompt = "Summarize this document"
                    st.chat_message('user').markdown(prompt)
                    st.session_state.messages.append({'role': 'user', 'content': prompt})
                    
                    # Process with PDF agent
                    if st.session_state.pdf_agent:
                        with st.spinner("Generating summary..."):
                            response = st.session_state.pdf_agent.process_document(st.session_state.pdf_path, prompt)
                        
                        # Display response
                        st.chat_message('assistant').markdown(response)
                        st.session_state.messages.append({'role': 'assistant', 'content': response})
                        st.rerun()
            
            with action_col2:
                if st.button("🧠 Recommend", use_container_width=True):
                    # Add message to chat asking for recommendations
                    prompt = "What are your recommendations based on this document?"
                    st.chat_message('user').markdown(prompt)
                    st.session_state.messages.append({'role': 'user', 'content': prompt})
                    
                    # Process with PDF agent
                    if st.session_state.pdf_agent:
                        with st.spinner("Generating recommendations..."):
                            response = st.session_state.pdf_agent.process_document(st.session_state.pdf_path, prompt)
                        
                        # Display response
                        st.chat_message('assistant').markdown(response)
                        st.session_state.messages.append({'role': 'assistant', 'content': response})
                        st.rerun()
            
            with action_col3:
                if st.button("🏷️ Classify", use_container_width=True):
                    # Show a spinner while classifying
                    with st.spinner("Classifying document..."):
                        # Get current bucket if document came from S3
                        current_bucket = st.session_state.get('selected_bucket', None)
                        original_key = None
                        
                        # Check if we have the original key stored
                        if hasattr(st.session_state, 'current_s3_key') and st.session_state.current_s3_key:
                            original_key = st.session_state.current_s3_key
                        
                        # Classify the document
                        result = classify_and_organize_document(
                            st.session_state.pdf_path,
                            bucket_name=current_bucket,
                            original_key=original_key
                        )
                        
                        # Add a message to chat with the classification result
                        if result.get("success", False):
                            prompt = f"This document has been classified as: {result['category']} (Confidence: {result['confidence']:.2f})"
                            if "target_key" in result:
                                prompt += f"\nThe document has been organized into the {result['folder']} folder."
                            prompt += f"\n\nReasoning: {result['reasoning']}"
                            
                            st.chat_message('user').markdown(prompt)
                            st.session_state.messages.append({'role': 'user', 'content': prompt})
                            
                            # Have the assistant acknowledge
                            response = f"✅ I've classified this document as **{result['category']}**."
                            if "target_key" in result:
                                response += f" It has been organized into the **{result['folder']}** folder in your S3 bucket."
                            response += f"\n\nConfidence: {result['confidence']:.2f}\n\n**Reasoning**: {result['reasoning']}"
                            
                            st.chat_message('assistant').markdown(response)
                            st.session_state.messages.append({'role': 'assistant', 'content': response})
                            st.rerun()
                        else:
                            # Handle error
                            error_msg = result.get("error", "Unknown error during classification")
                            st.error(f"Classification failed: {error_msg}")
                            
                            # Add error to chat
                            response = f"❌ I couldn't classify this document: {error_msg}"
                            st.chat_message('assistant').markdown(response)
                            st.session_state.messages.append({'role': 'assistant', 'content': response})
                            st.rerun()
            
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
        
        # Helper text for email and reminder features
        if st.session_state.pdf_path and st.session_state.ms_graph_client and st.session_state.pdf_agent:
            with st.expander("💡 Chat Commands"):
                st.markdown("""
                You can use these commands in the chat:
                - **Send email to: [email]** - Send an email with a summary of this document
                - **Remind me in [X] days/weeks** - Set a reminder to review this document later
                - **Summarize** - Get a comprehensive summary
                - **Recommend** or **Next steps** - Get recommendations based on the document
                """)
        
        # Display chat messages
        for message in st.session_state.messages:
            st.chat_message(message['role']).markdown(message['content'])
        
        # Chat input
        if st.session_state.pdf_path and st.session_state.pdf_agent:
            chat_placeholder = "Ask a question, request a summary, or type 'send email to: someone@example.com'"
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

        if prompt and "classify" in prompt.lower():
            # User wants to classify the document
            with st.spinner("Classifying document..."):
                # Get current bucket if document came from S3
                current_bucket = st.session_state.get('selected_bucket', None)
                original_key = None
                
                # Check if we have the original key stored
                if hasattr(st.session_state, 'current_s3_key') and st.session_state.current_s3_key:
                    original_key = st.session_state.current_s3_key
                
                # Classify the document
                result = classify_and_organize_document(
                    st.session_state.pdf_path,
                    bucket_name=current_bucket,
                    original_key=original_key
                )
                
                # Prepare response based on result
                if result.get("success", False):
                    # Check if it's a custom category
                    if result.get("is_custom_category", False) and result.get("custom_category"):
                        category_display = result.get("custom_category")
                    else:
                        category_display = result['category']
                        
                    response = f"✅ I've classified this document as **{category_display}**."
                    if "target_key" in result:
                        response += f" It has been organized into the **{result['folder']}** folder in your S3 bucket."
                        # If it's a custom category, add a note about folder creation
                        if result.get("is_custom_category", False):
                            response += f"\n\n*Note: I've created a new folder for this category since it didn't match any of the standard categories.*"
                    response += f"\n\nConfidence: {result['confidence']:.2f}\n\n**Reasoning**: {result['reasoning']}"
                else:
                    error_msg = result.get("error", "Unknown error during classification")
                    response = f"❌ I couldn't classify this document: {error_msg}"
                
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

        # Initialize/Configure WatsonX model
        if st.button("Initialize WatsonX Model"):
            try:
                my_credentials = {
                    "url": watsonx_url,
                    "apikey": watsonx_api_key
                }
                
                # Parse model parameters
                params = json.loads(watsonx_model_params)
                project_id = os.getenv("WATSONX_PROJECT_ID", "ea1bfd72-28d6-4a4d-8668-c1de89865515")
                space_id = None
                verify = False
                
                model = Model(watsonx_model, my_credentials, params, project_id, space_id, verify)
                
                # Initialize PDF agent with model and any existing MS Graph client
                ms_graph_client = st.session_state.ms_graph_client if 'ms_graph_client' in st.session_state else None
                
                # Get any existing PDF search tool
                pdf_search_tool = st.session_state.pdf_search_tool if 'pdf_search_tool' in st.session_state else None
                
                st.session_state.pdf_agent = WatsonxPDFAgent(
                    model, 
                    pdf_search_tool=pdf_search_tool,
                    ms_graph_client=ms_graph_client
                )
                
                # Initialize the document classifier
                st.session_state.document_classifier = DocumentClassifier(
                    model,  # This is the WatsonX model instance
                    pdf_search_tool=pdf_search_tool
                )
                logger.info("Document classifier initialized")
                
                st.success("WatsonX model initialized successfully!")
            except Exception as e:
                st.error(f"Error initializing WatsonX model: {str(e)}")
                logger.error(f"Error initializing WatsonX model: {str(e)}")
        
        # Main configuration columns
        col1, col2 = st.columns(2)
        
        # AWS S3 Configuration Column
        with col1:
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
            
            # If AWS S3 is connected, show PDF selection options
            # If AWS S3 is connected, show PDF selection with folder navigation
            if 'aws_s3_client' in st.session_state and st.session_state.aws_s3_client:
                if 'aws_buckets' in st.session_state and st.session_state.aws_buckets:
                    selected_bucket = st.selectbox(
                        "Select S3 Bucket", 
                        options=st.session_state.aws_buckets,
                        key="selected_bucket"
                    )
                    
                    if selected_bucket:
                        # Initialize or get the current folder path
                        if 'current_s3_folder' not in st.session_state:
                            st.session_state.current_s3_folder = ""
                        
                        # Show current path and provide a way to go up a level
                        if st.session_state.current_s3_folder:
                            # Use a horizontal layout instead of columns to avoid nesting issues
                            st.write(f"Current folder: /{st.session_state.current_s3_folder}" if st.session_state.current_s3_folder else "Root folder")
                            
                            if st.button("⬆️ Go Up"):
                                # Go up one level
                                path_parts = st.session_state.current_s3_folder.split('/')
                                if len(path_parts) > 1:
                                    st.session_state.current_s3_folder = '/'.join(path_parts[:-1])
                                else:
                                    st.session_state.current_s3_folder = ""
                                st.rerun()
                        
                        # List files and folders in the current directory
                        s3_items = st.session_state.aws_s3_client.list_pdfs(
                            selected_bucket, 
                            prefix=st.session_state.current_s3_folder
                        )
                        
                        if s3_items:
                            # Format the items into a nice display list
                            item_options = []
                            item_paths = {}
                            
                            for item in s3_items:
                                display_name = f"📁 {item['name']}" if item['type'] == 'folder' else f"📄 {item['name']}"
                                item_options.append(display_name)
                                if 'path' in item:
                                    item_paths[display_name] = item['path']
                                else:
                                    item_paths[display_name] = item['name']
                            
                            selected_item = st.selectbox(
                                "Select File or Folder", 
                                options=item_options,
                                key="selected_s3_item"
                            )
                            
                            if selected_item:
                                # Get the path of the selected item
                                selected_path = item_paths[selected_item]
                                
                                # Check if it's a folder or file
                                is_folder = selected_item.startswith("📁")
                                
                                # Handle folder navigation
                                if is_folder:
                                    if st.button(f"Open Folder: {selected_item[2:]}"):
                                        st.session_state.current_s3_folder = selected_path
                                        st.rerun()
                                # Handle file selection
                                else:
                                    if st.button(f"Load PDF: {selected_item[2:]}"):
                                        with st.spinner("Downloading PDF from S3..."):
                                            # Get the file path
                                            if st.session_state.current_s3_folder:
                                                object_key = f"{st.session_state.current_s3_folder}/{selected_path}"
                                            else:
                                                object_key = selected_path
                                            
                                            # Store the original key for future reference
                                            st.session_state.current_s3_key = object_key
                                            
                                            # Download the file code...
                                            # (Keeping the existing download code)
                                            # Create a temporary directory
                                            temp_dir = tempfile.mkdtemp()
                                            local_path = os.path.join(temp_dir, os.path.basename(selected_path))
                                            
                                            # Download the file
                                            try:
                                                if st.session_state.aws_s3_client.download_file(selected_bucket, object_key, local_path):
                                                    # Verification and processing code...
                                                    # (Keeping the existing processing code)
                                                    # Verify the file exists
                                                    if not os.path.exists(local_path):
                                                        st.error(f"File was downloaded but couldn't be found at {local_path}")
                                                        return
                                                        
                                                    # Store the absolute path
                                                    st.session_state.pdf_path = os.path.abspath(local_path)
                                                    
                                                    # Log the path for debugging
                                                    logger.info(f"PDF downloaded to: {st.session_state.pdf_path}")
                                                    st.info(f"PDF downloaded to: {st.session_state.pdf_path}")
                                                    
                                                    # Initialize PDF search tool code...
                                                    # (Keeping the existing PDF tool initialization code)
                                                    try:
                                                        if 'pdf_agent' in st.session_state and st.session_state.pdf_agent:
                                                            watsonx_model = st.session_state.pdf_agent.model
                                                            
                                                            safe_dir = tempfile.mkdtemp(prefix="safe_pdf_")
                                                            safe_file_path = os.path.join(safe_dir, os.path.basename(selected_path))
                                                            
                                                            import shutil
                                                            shutil.copy2(st.session_state.pdf_path, safe_file_path)
                                                            
                                                            logger.info(f"Using safe PDF path: {safe_file_path}")
                                                            
                                                            try:
                                                                st.session_state.pdf_search_tool = get_custom_pdf_tool(
                                                                    safe_file_path,
                                                                    watsonx_model
                                                                )
                                                                st.success(f"PDF loaded successfully: {os.path.basename(selected_path)}")
                                                            except Exception as e:
                                                                st.error(f"Error with PDF tool: {str(e)}")
                                                                logger.error(f"PDF tool error: {str(e)}")
                                                            
                                                            st.session_state.pdf_agent.pdf_search_tool = st.session_state.pdf_search_tool
                                                            
                                                            st.session_state.messages.append({
                                                                "role": "assistant", 
                                                                "content": f"📄 I've loaded '{os.path.basename(selected_path)}' from S3. What would you like to know about this document?"
                                                            })
                                                            
                                                            st.rerun()
                                                        else:
                                                            st.error("Please initialize WatsonX model first before loading PDF")
                                                    except Exception as e:
                                                        st.error(f"Error initializing PDF search tool: {str(e)}")
                                                        logger.error(f"Error initializing PDF search tool: {str(e)}")
                                                else:
                                                    st.error(f"Failed to download {selected_path} from S3")
                                            except Exception as e:
                                                st.error(f"Error processing PDF: {str(e)}")
                                                logger.error(f"Error processing PDF: {str(e)}")
                        else:
                            st.warning(f"No items found in the current folder")
        
        # Microsoft Graph API Configuration Column
        with col2:
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
            
            # Two buttons side by side without using nested columns
            ms_graph_col1, ms_graph_col2 = st.columns(2)
            
            with ms_graph_col1:
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
                            
                            if 'pdf_agent' in st.session_state and st.session_state.pdf_agent:
                                st.session_state.pdf_agent.ms_graph_client = st.session_state.ms_graph_client
                                st.success("PDF agent updated with email capabilities!")
                        else:
                            st.error("Failed to connect to Microsoft Graph API")
                    except Exception as e:
                        st.error(f"Error connecting to Microsoft Graph API: {str(e)}")
            
            with ms_graph_col2:
                if st.button("Reset Configuration"):
                    if 'ms_graph_client' in st.session_state:
                        del st.session_state.ms_graph_client
                    
                    dotenv.load_dotenv(override=True)
                    
                    st.success("Configuration reset successfully")
                    st.rerun()
        
        # Upload PDF directly section - outside the columns to avoid nesting issues
        st.subheader("Upload PDF")
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
        
        if uploaded_file:
            with st.spinner("Processing uploaded PDF..."):
                # Create a temporary file
                temp_dir = tempfile.mkdtemp()
                temp_file_path = os.path.join(temp_dir, uploaded_file.name)
                
                # Write the uploaded file to the temp file
                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Verify the file exists and get absolute path
                if not os.path.exists(temp_file_path):
                    st.error(f"Error: File was written but couldn't be found at {temp_file_path}")
                    return
                    
                # Save the absolute file path to session state
                st.session_state.pdf_path = os.path.abspath(temp_file_path)
                
                # Log the path for debugging
                logger.info(f"PDF uploaded to: {st.session_state.pdf_path}")
                st.info(f"PDF saved to: {st.session_state.pdf_path}")
                
                # PDF agent initialization after upload
                # (Keeping the existing initialization code)
                try:
                    if 'pdf_agent' in st.session_state and st.session_state.pdf_agent:
                        watsonx_model = st.session_state.pdf_agent.model
                        
                        safe_dir = tempfile.mkdtemp(prefix="safe_pdf_")
                        safe_file_path = os.path.join(safe_dir, uploaded_file.name)
                        
                        import shutil
                        shutil.copy2(st.session_state.pdf_path, safe_file_path)
                        
                        logger.info(f"Using safe PDF path: {safe_file_path}")
                        
                        try:
                            st.session_state.pdf_search_tool = get_custom_pdf_tool(
                                safe_file_path,
                                watsonx_model
                            )
                            
                            st.session_state.pdf_agent.pdf_search_tool = st.session_state.pdf_search_tool
                            
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": f"📄 I've loaded '{uploaded_file.name}'. What would you like to know about this document?"
                            })
                            
                            st.success(f"PDF uploaded successfully: {uploaded_file.name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error with PDF tool: {str(e)}")
                            logger.error(f"PDF tool error: {str(e)}")
                    else:
                        st.warning("Please initialize WatsonX model first")
                except Exception as e:
                    st.error(f"Error initializing PDF search tool: {str(e)}")
                    logger.error(f"Error initializing PDF search tool: {str(e)}")
        
        # Save configuration to .env
        st.subheader("Save Configuration")
        if st.button("Save Configuration to .env"):
            try:
                # Create the .env file content
                env_content = f"""# WatsonX Configuration
    WATSONX_API_KEY={watsonx_api_key}
    WATSONX_URL={watsonx_url}
    WATSONX_MODEL={watsonx_model}
    WATSONX_MODEL_PARAMS={watsonx_model_params}
    WATSONX_PROJECT_ID={os.getenv("WATSONX_PROJECT_ID", "ea1bfd72-28d6-4a4d-8668-c1de89865515")}

    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID={aws_access_key}
    AWS_SECRET_ACCESS_KEY={aws_secret_key}
    AWS_REGION={aws_region}

    # Microsoft Graph API Configuration
    MS_CLIENT_ID={ms_client_id}
    MS_CLIENT_SECRET={ms_client_secret}
    MS_TENANT_ID={ms_tenant_id}
    MS_USER_EMAIL={ms_user_email}

    # Auto-initialization
    AUTO_INITIALIZE=true
    """
                
                # Write to .env file
                with open(".env", "w") as f:
                    f.write(env_content)
                
                st.success("Configuration saved to .env file successfully!")
            except Exception as e:
                st.error(f"Error saving configuration: {str(e)}")

if __name__ == "__main__":
    main()