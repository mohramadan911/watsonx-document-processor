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
        st.session_state.messages = [{"role": "assistant", "content": "👋 Hello! Please upload or select a PDF document, then you can ask questions, request a summary, or get recommendations. I can also help you send emails about the document or set reminders for later review."}]

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
            
            # Create columns for document info and action buttons
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.info(f"📄 Current document: {file_name}")
            
            with col2:
                # Add quick action buttons for common tasks
                action_col1, action_col2 = st.columns(2)
                with action_col1:
                    if st.button("📝 Summarize"):
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
                    if st.button("🧠 Recommend"):
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
            
            # If AWS S3 is connected, show PDF selection options
            if 'aws_s3_client' in st.session_state and st.session_state.aws_s3_client:
                if 'aws_buckets' in st.session_state and st.session_state.aws_buckets:
                    selected_bucket = st.selectbox(
                        "Select S3 Bucket", 
                        options=st.session_state.aws_buckets,
                        key="selected_bucket"
                    )
                    
                    if selected_bucket:
                        # List PDFs in the selected bucket
                        pdfs = st.session_state.aws_s3_client.list_pdfs(selected_bucket)
                        
                        if pdfs:
                            selected_pdf = st.selectbox(
                                "Select PDF from S3", 
                                options=pdfs,
                                key="selected_s3_pdf"
                            )
                            
                            if selected_pdf and st.button("Load PDF from S3"):
                                with st.spinner("Downloading PDF from S3..."):
                                    # Create temp file
                                    temp_dir = tempfile.mkdtemp()
                                    local_path = os.path.join(temp_dir, selected_pdf)
                                    
                                    # Download the file
                                    try:
                                        # Get the full object key by searching for the filename
                                        objects = st.session_state.aws_s3_client.list_objects(selected_bucket)
                                        obj_key = None
                                        for obj in objects:
                                            if obj['name'] == selected_pdf:
                                                obj_key = obj['key']
                                                break
                                        
                                        if not obj_key:
                                            st.error(f"Could not find the full path for {selected_pdf} in bucket {selected_bucket}")
                                            return
                                            
                                        # Create a temporary directory
                                        temp_dir = tempfile.mkdtemp()
                                        local_path = os.path.join(temp_dir, selected_pdf)
                                        
                                        if st.session_state.aws_s3_client.download_file(selected_bucket, obj_key, local_path):
                                            # Verify the file exists
                                            if not os.path.exists(local_path):
                                                st.error(f"File was downloaded but couldn't be found at {local_path}")
                                                return
                                                
                                            # Store the absolute path
                                            st.session_state.pdf_path = os.path.abspath(local_path)
                                            
                                            # Log the path for debugging
                                            logger.info(f"PDF downloaded to: {st.session_state.pdf_path}")
                                            st.info(f"PDF downloaded to: {st.session_state.pdf_path}")
                                            
                                            # Initialize PDF search tool and update the agent
                                            try:
                                                # Check if we have a watsonx model initialized
                                                if 'pdf_agent' in st.session_state and st.session_state.pdf_agent:
                                                    # Get the model from the PDF agent
                                                    watsonx_model = st.session_state.pdf_agent.model
                                                    
                                                    # Make a local copy of the file in a directory without "knowledge/" prefix issues
                                                    # Create a temporary directory with a safe name
                                                    safe_dir = tempfile.mkdtemp(prefix="safe_pdf_")
                                                    safe_file_path = os.path.join(safe_dir, selected_pdf)
                                                    
                                                    # Copy the file to the safe location
                                                    import shutil
                                                    shutil.copy2(st.session_state.pdf_path, safe_file_path)
                                                    
                                                    # Log the safe path
                                                    logger.info(f"Using safe PDF path: {safe_file_path}")
                                                    
                                                    # Initialize PDF search tool with the model
                                                    try:
                                                        # Use helper function to avoid circular imports
                                                        st.session_state.pdf_search_tool = get_custom_pdf_tool(
                                                            safe_file_path,
                                                            watsonx_model
                                                        )
                                                        st.success(f"PDF loaded successfully: {selected_pdf}")
                                                    except Exception as e:
                                                        st.error(f"Error with PDF tool: {str(e)}")
                                                        logger.error(f"PDF tool error: {str(e)}")
                                                    
                                                    # Update the PDF agent with the search tool
                                                    st.session_state.pdf_agent.pdf_search_tool = st.session_state.pdf_search_tool
                                                    st.success(f"PDF loaded successfully: {selected_pdf}")
                                                    
                                                    # Add system message
                                                    st.session_state.messages.append({
                                                        "role": "assistant", 
                                                        "content": f"📄 I've loaded '{selected_pdf}' from S3. What would you like to know about this document?"
                                                    })
                                                    
                                                    st.rerun()
                                                else:
                                                    st.error("Please initialize WatsonX model first before loading PDF")
                                            except Exception as e:
                                                st.error(f"Error initializing PDF search tool: {str(e)}")
                                                logger.error(f"Error initializing PDF search tool: {str(e)}")
                                        else:
                                            st.error(f"Failed to download {selected_pdf} from S3")
                                    except Exception as e:
                                        st.error(f"Error processing PDF: {str(e)}")
                                        logger.error(f"Error processing PDF: {str(e)}")
                        else:
                            st.warning(f"No PDF files found in bucket {selected_bucket}")
        
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
                            
                            # Update the PDF agent with the MS Graph client if it exists
                            if 'pdf_agent' in st.session_state and st.session_state.pdf_agent:
                                st.session_state.pdf_agent.ms_graph_client = st.session_state.ms_graph_client
                                st.success("PDF agent updated with email capabilities!")
                        else:
                            st.error("Failed to connect to Microsoft Graph API")
                    except Exception as e:
                        st.error(f"Error connecting to Microsoft Graph API: {str(e)}")
            
            with col2b:
                # Add the Reset Configuration button here
                if st.button("Reset Configuration"):
                    # Clear existing connections
                    if 'ms_graph_client' in st.session_state:
                        del st.session_state.ms_graph_client
                    
                    # Reload environment variables
                    dotenv.load_dotenv(override=True)
                    
                    st.success("Configuration reset successfully")
                    st.rerun()
        
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
                
                st.success("WatsonX model initialized successfully!")
            except Exception as e:
                st.error(f"Error initializing WatsonX model: {str(e)}")
                logger.error(f"Error initializing WatsonX model: {str(e)}")
        
        # Upload PDF directly
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
                
                try:
                    # Check if we have a watsonx model initialized
                    if 'pdf_agent' in st.session_state and st.session_state.pdf_agent:
                        # Get the model from the PDF agent
                        watsonx_model = st.session_state.pdf_agent.model
                        
                        # Make a local copy of the file in a directory without "knowledge/" prefix issues
                        # Create a temporary directory with a safe name
                        safe_dir = tempfile.mkdtemp(prefix="safe_pdf_")
                        safe_file_path = os.path.join(safe_dir, uploaded_file.name)
                        
                        # Copy the file to the safe location
                        import shutil
                        shutil.copy2(st.session_state.pdf_path, safe_file_path)
                        
                        # Log the safe path
                        logger.info(f"Using safe PDF path: {safe_file_path}")
                        
                        try:
                            # Use helper function to avoid circular imports
                            st.session_state.pdf_search_tool = get_custom_pdf_tool(
                                safe_file_path,
                                watsonx_model
                            )
                            
                            # Update the PDF agent with the search tool
                            st.session_state.pdf_agent.pdf_search_tool = st.session_state.pdf_search_tool
                            
                            # Add system message
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": f"📄 I've loaded '{uploaded_file.name}'. What would you like to know about this document?"
                            })
                            
                            st.success(f"PDF uploaded successfully: {uploaded_file.name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error with PDF tool: {str(e)}")
                            logger.error(f"PDF tool error: {str(e)}")
                        
                        # Update the PDF agent with the search tool
                        st.session_state.pdf_agent.pdf_search_tool = st.session_state.pdf_search_tool
                        
                        # Add system message
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": f"📄 I've loaded '{uploaded_file.name}'. What would you like to know about this document?"
                        })
                        
                        st.success(f"PDF uploaded successfully: {uploaded_file.name}")
                        st.rerun()
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