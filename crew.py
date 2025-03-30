import streamlit as st
from ibm_watson_machine_learning.foundation_models import Model
import json
import os

st.title('Watsonx Chatbot 🤖')
st.caption("🚀 A chatbot powered by watsonx.ai - rel 13")

with st.sidebar:
    watsonx_api_key = st.text_input("Watsonx API Key", key="watsonx_api_key", value="fmAt2BalY32PW9gJggnjwqn1wK3yjQ2oPLDxMG-U_crw", type="password")
    watsonx_url = st.text_input("Watsonx URL", key="watsonx_url", value="https://us-south.ml.cloud.ibm.com", type="default")   
    #TODO: change this to a select box with more than one model
    watsonx_model = st.text_input("Model", key="watsonx_model", value="meta-llama/llama-3-3-70b-instruct", type="default")   
    watsonx_model_params = st.text_input("Params", key="watsonx_model_params", value='{"decoding_method":"sample", "max_new_tokens":200, "temperature":0.5}', type="default" )
if not watsonx_api_key:
    st.info("Please add your watsonx API key to continue.")
else :
    st.info("setting up to use: " + watsonx_model)
    my_credentials = { 
        "url"    : watsonx_url, 
        "apikey" : watsonx_api_key
    }
    params = json.loads(watsonx_model_params)      
    project_id  = "ea1bfd72-28d6-4a4d-8668-c1de89865515"
    space_id    = None
    verify      = False
    model = Model( watsonx_model, my_credentials, params, project_id, space_id, verify )   
    if model :
        st.info("done")
 
if 'messages' not in st.session_state: 
    st.session_state.messages = [{"role": "assistant", "content": "How can I help you?"}] 

for message in st.session_state.messages: 
    st.chat_message(message['role']).markdown(message['content'])

prompt = st.chat_input('Pass Your Prompt here')

if prompt: 
    st.chat_message('user').markdown(prompt)
    st.session_state.messages.append({'role':'user', 'content':prompt})
    if model :
        response = model.generate_text(prompt)
    else :
        response = "You said: " + prompt
    
    st.chat_message('assistant').markdown(response)
    st.session_state.messages.append({'role':'assistant', 'content':response})
