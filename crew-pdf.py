import streamlit as st
from ibm_watson_machine_learning.foundation_models import Model
from crewai_tools import PDFSearchTool
import tempfile
import json
import os
# No need for base64 since we removed the PDF viewer

st.title('Watsonx PDF Chatbot 🤖')
st.caption("🚀 A chatbot powered by watsonx.ai with PDF search capabilities")

# Session state initialization
if 'pdf_path' not in st.session_state:
    st.session_state.pdf_path = None

if 'pdf_search_tool' not in st.session_state:
    st.session_state.pdf_search_tool = None

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")
    watsonx_api_key = st.text_input("Watsonx API Key", key="watsonx_api_key", value="fmAt2BalY32PW9gJggnjwqn1wK3yjQ2oPLDxMG-U_crw", type="password")
    watsonx_url = st.text_input("Watsonx URL", key="watsonx_url", value="https://us-south.ml.cloud.ibm.com", type="default")   
    watsonx_model = st.selectbox(
        "Model", 
        ["meta-llama/llama-3-3-70b-instruct", "ibm/granite-20b-instruct-v2", "meta-llama/llama-2-70b-chat"],
        key="watsonx_model"
    )
    watsonx_model_params = st.text_area(
        "Model Parameters", 
        value='{"decoding_method":"sample", "max_new_tokens":500, "temperature":0.5}', 
        key="watsonx_model_params"
    )
    
    # PDF upload section
    st.header("PDF Upload")
    uploaded_file = st.file_uploader("Upload a PDF document", type="pdf")
    
    if uploaded_file is not None:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            st.session_state.pdf_path = tmp_file.name
        
        st.success(f"PDF uploaded: {uploaded_file.name}")
        # Initialize the PDF search tool
        try:
            st.session_state.pdf_search_tool = PDFSearchTool(pdf=st.session_state.pdf_path)
            st.success("PDF search tool initialized successfully")
        except Exception as e:
            st.error(f"Error initializing PDF search tool: {str(e)}")

# Initialize the WatsonX model
if watsonx_api_key:
    try:
        my_credentials = {
            "url": watsonx_url, 
            "apikey": watsonx_api_key
        }
        params = json.loads(watsonx_model_params)      
        project_id = "ea1bfd72-28d6-4a4d-8668-c1de89865515"
        space_id = None
        verify = False
        
        model = Model(watsonx_model, my_credentials, params, project_id, space_id, verify)
        st.sidebar.success(f"WatsonX model initialized: {watsonx_model}")
    except Exception as e:
        st.sidebar.error(f"Error initializing WatsonX model: {str(e)}")
        model = None
else:
    st.info("Please add your WatsonX API key to continue.")
    model = None

# Initialize chat history
if 'messages' not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "👋 Hello! Please upload a PDF document in the sidebar, then you can ask me questions about it or request a summary."}]

# Display chat messages
for message in st.session_state.messages:
    st.chat_message(message['role']).markdown(message['content'])

# Function to generate prompt with PDF context if available
def get_response_with_pdf_context(prompt):
    if st.session_state.pdf_search_tool is not None:
        try:
            # Handle "summarize" requests specially
            if "summarize" in prompt.lower() and any(word in prompt.lower() for word in ["pdf", "document", "file", "the"]):
                # For summarization, we want to get broader content from the PDF
                search_results = st.session_state.pdf_search_tool.search("main topics key points overview")
                
                augmented_prompt = f"""
                The user wants a summary of the PDF document.
                
                Here is content from the uploaded PDF document:
                {search_results}
                
                Please provide a comprehensive summary of this document covering the main points.
                """
            else:
                # Regular search for specific questions
                search_results = st.session_state.pdf_search_tool.search(prompt)
                
                augmented_prompt = f"""
                The user's question is: {prompt}
                
                Based on the uploaded PDF document, here is relevant information:
                {search_results}
                
                Using the above context from the PDF, please answer the user's question accurately.
                """
            
            # Generate response with the augmented prompt
            if model:
                response = model.generate_text(augmented_prompt)
            else:
                response = "Model not initialized. Here's what I found in the PDF: " + search_results
        except Exception as e:
            response = f"Error searching PDF: {str(e)}"
    else:
        # No PDF uploaded or search tool not initialized
        if model:
            response = model.generate_text(prompt)
        else:
            response = "Please upload a PDF document first to ask questions about it."
    
    return response

# Chat input
prompt = st.chat_input('Ask a question about the PDF or any other topic')

if prompt:
    # Display user message
    st.chat_message('user').markdown(prompt)
    st.session_state.messages.append({'role': 'user', 'content': prompt})
    
    # Get AI response
    response = get_response_with_pdf_context(prompt)
    
    # Display AI response
    st.chat_message('assistant').markdown(response)
    st.session_state.messages.append({'role': 'assistant', 'content': response})

# Show a simple indicator that PDF is loaded (instead of viewer)
if st.session_state.pdf_path and uploaded_file:
    st.success(f"PDF document loaded and ready: {uploaded_file.name}")
    st.info("You can now ask questions about the content of the PDF.")