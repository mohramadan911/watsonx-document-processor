# custom_pdf_tool.py
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
import hashlib
import numpy as np

class WatsonxEmbeddings(Embeddings):
    """Wrapper for WatsonX embedding model"""
    def __init__(self, watsonx_model):
        self.watsonx_model = watsonx_model
    
    def embed_documents(self, texts):
        """Embed search docs."""
        embeddings = []
        for text in texts:
            # Create deterministic dummy embeddings based on text hash
            # Ensure the seed is within valid range (0 to 2^32 - 1)
            hash_obj = hashlib.md5(text.encode())
            # Take just the first 4 bytes of the hash and convert to int
            seed = int.from_bytes(hash_obj.digest()[:4], byteorder='big')
            np.random.seed(seed)
            embeddings.append(np.random.rand(768))
        return embeddings

    def embed_query(self, text):
        """Embed query text."""
        return self.embed_documents([text])[0]

class CustomPDFSearchTool:
    """Simple tool for searching PDF documents using WatsonX"""
    
    def __init__(self, pdf, watsonx_model):
        self.pdf_path = pdf
        self.watsonx_model = watsonx_model
        
        # Load and process the PDF
        self.loader = PyPDFLoader(self.pdf_path)
        self.documents = self.loader.load()
        
        # Create embeddings
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        self.splits = text_splitter.split_documents(self.documents)
        
        # Initialize embeddings with WatsonX
        embeddings = WatsonxEmbeddings(watsonx_model)
        
        # Create vector store
        self.vector_store = FAISS.from_documents(self.splits, embeddings)
    
    def search(self, query):
        """Search the PDF for relevant information"""
        # Search for similar documents
        docs = self.vector_store.similarity_search(query, k=4)
        
        # Extract and return the text from the similar documents
        results = "\n\n".join([doc.page_content for doc in docs])
        return results