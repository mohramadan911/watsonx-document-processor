# document_classifier.py
import logging
import os
import json
from enum import Enum, auto
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DocumentCategory(Enum):
    """Enum representing document categories"""
    TECHNICAL = auto()
    FINANCIAL = auto()
    HR = auto()
    LOGISTICS = auto()  # Added Logistics category
    LEGAL = auto()      # Added Legal category
    MARKETING = auto()  # Added Marketing category
    OPERATIONS = auto() # Added Operations category
    GENERAL = auto()
    CUSTOM = auto()     # Special category for dynamic classifications
    
    @classmethod
    def to_folder_name(cls, category):
        """Convert category to folder name"""
        mapping = {
            cls.TECHNICAL: "IT",
            cls.FINANCIAL: "Financial",
            cls.HR: "HR",
            cls.LOGISTICS: "Logistics",
            cls.LEGAL: "Legal",
            cls.MARKETING: "Marketing",
            cls.OPERATIONS: "Operations",
            cls.GENERAL: "General",
            cls.CUSTOM: None  # Will be handled separately for dynamic categories
        }
        return mapping.get(category, "General")
        
    @classmethod
    def from_string(cls, category_str):
        """Convert string to category enum"""
        try:
            return cls[category_str.upper()]
        except (KeyError, AttributeError):
            return cls.CUSTOM

class DocumentClassifier:
    """Document classifier using WatsonX AI model"""
    
    def __init__(self, watsonx_model, pdf_search_tool=None):
        """Initialize document classifier
        
        Args:
            watsonx_model: WatsonX model instance for classification
            pdf_search_tool: Optional tool for searching PDF content
        """
        self.model = watsonx_model
        self.pdf_search_tool = pdf_search_tool
        
    def classify_document(self, pdf_path, detect_custom_categories=True):
        """Classify a document using the WatsonX model with enhanced prompt and error handling
        
        Args:
            pdf_path (str): Path to the PDF file
            detect_custom_categories (bool): Whether to detect custom categories beyond predefined ones
            
        Returns:
            tuple: (DocumentCategory, confidence_score, details, custom_category_name)
        """
        try:
            # Update PDF search tool if needed
            if self.pdf_search_tool is None or self.pdf_search_tool.pdf_path != pdf_path:
                from dockling_tool import DocklingPDFTool
                self.pdf_search_tool = DocklingPDFTool(pdf_path, self.model)
            
            # Extract content for classification
            content = self.pdf_search_tool.search("document purpose main topics key sections")
            
            # Get metadata which might contain additional useful information
            metadata = self.pdf_search_tool.get_metadata()
            
            # More specific prompt for financial documents
            if detect_custom_categories:
                # Prompt that allows for custom category detection with enhanced financial recognition
                classification_prompt = f"""
                You are a document classification specialist. Carefully analyze the following document content and classify it into the most appropriate department category.
                
                Document filename: {os.path.basename(pdf_path)}
                Document title: {metadata.get('title', 'Unknown')}
                Document content excerpt:
                {content}
                
                First, consider these common departments:
                1. TECHNICAL - IT-related documents, technical guidelines, system documentation, code documentation, IT procedures
                2. FINANCIAL - Financial reports, budgets, invoices, financial analyses, expense reports, income statements, balance sheets, cash flow statements, accounting documents
                3. HR - CVs/Resumes, HR policies, job descriptions, performance reviews, employee handbooks
                4. LOGISTICS - Supply chain, shipping, inventory, transportation, warehouse documentation
                5. LEGAL - Contracts, compliance documents, legal opinions, regulations, policies
                6. MARKETING - Marketing plans, branding, advertising, market research
                7. OPERATIONS - Standard operating procedures, process documents, operations manuals
                8. GENERAL - General documents that don't fit into specific categories
                
                However, if the document clearly belongs to another department not listed above, you should specify that department name instead.
                
                IMPORTANT: If you see financial statements, income statements, balance sheets, profit and loss statements, cash flow statements, or other accounting/financial reports, you MUST classify them as FINANCIAL.
                
                Return your answer in a structured JSON format with the following fields:
                - category: The department category (use the predefined ones above if applicable, or specify a custom department)
                - standard_category: Is this one of the standard departments listed above? (true/false)
                - confidence: a number between 0 and 1 indicating classification confidence
                - reasoning: brief explanation for this classification
                
                Format your response as a valid JSON object and nothing else. Example:
                {{"category": "FINANCIAL", "confidence": 0.95, "reasoning": "This document contains income statements, balance sheets, and financial analysis."}}
                """
            else:
                # Original prompt with fixed categories but with enhanced financial recognition
                classification_prompt = f"""
                You are a document classification specialist. Carefully analyze the following document content and classify it into exactly ONE of these categories:
                
                Document filename: {os.path.basename(pdf_path)}
                Document title: {metadata.get('title', 'Unknown')}
                Document content excerpt:
                {content}
                
                1. TECHNICAL - IT-related documents, technical guidelines, system documentation, code documentation, IT procedures
                2. FINANCIAL - Financial reports, budgets, invoices, financial analyses, expense reports, income statements, balance sheets, cash flow statements, accounting documents
                3. HR - CVs/Resumes, HR policies, job descriptions, performance reviews, employee handbooks
                4. LOGISTICS - Supply chain, shipping, inventory, transportation, warehouse documentation
                5. LEGAL - Contracts, compliance documents, legal opinions, regulations, policies
                6. MARKETING - Marketing plans, branding, advertising, market research
                7. OPERATIONS - Standard operating procedures, process documents, operations manuals
                8. GENERAL - General documents that don't fit into the above categories
                
                IMPORTANT: If you see financial statements, income statements, balance sheets, profit and loss statements, cash flow statements, or other accounting/financial reports, you MUST classify them as FINANCIAL.
                
                Return your answer in a structured JSON format with the following fields:
                - category: ONE of "TECHNICAL", "FINANCIAL", "HR", "LOGISTICS", "LEGAL", "MARKETING", "OPERATIONS", or "GENERAL"
                - confidence: a number between 0 and 1 indicating classification confidence
                - reasoning: brief explanation for this classification
                
                Format your response as a valid JSON object and nothing else. Example:
                {{"category": "FINANCIAL", "confidence": 0.95, "reasoning": "This document contains income statements, balance sheets, and financial analysis."}}
                """
            
            # Get classification response
            classification_response = self.model.generate_text(classification_prompt)
            logger.info(f"Raw classification response: {classification_response}")
            
            # Parse the JSON response with better error handling
            try:
                # Clean the response to ensure valid JSON
                cleaned_response = classification_response.strip()
                
                # Handle cases where the response might contain extra text
                if '{' in cleaned_response:
                    start = cleaned_response.find('{')
                    end = cleaned_response.rfind('}') + 1
                    cleaned_response = cleaned_response[start:end]
                
                # Fallback parser if the JSON is malformed
                if not self._is_valid_json(cleaned_response):
                    # Attempt to extract category directly if JSON parsing fails
                    category_match = self._extract_category_from_text(classification_response)
                    if category_match:
                        return (category_match, 0.8, f"Category extracted from text: {classification_response[:100]}...", None)
                    else:
                        # Fall back to content-based heuristics
                        return self._classify_by_heuristics(content, pdf_path)
                        
                classification_data = json.loads(cleaned_response)
                
                category_str = classification_data.get("category", "GENERAL").upper()
                confidence = float(classification_data.get("confidence", 0.5))
                reasoning = classification_data.get("reasoning", "No reasoning provided")
                is_standard = classification_data.get("standard_category", True)
                
                # Check if this is a standard category or custom
                custom_category_name = None
                
                if is_standard is False or (detect_custom_categories and category_str not in [
                    "TECHNICAL", "FINANCIAL", "HR", "LOGISTICS", "LEGAL", "MARKETING", "OPERATIONS", "GENERAL"
                ]):
                    # This is a custom category
                    category = DocumentCategory.CUSTOM
                    custom_category_name = classification_data.get("category")
                    # Make sure first letter is capitalized for folder name consistency
                    if custom_category_name and len(custom_category_name) > 0:
                        custom_category_name = custom_category_name[0].upper() + custom_category_name[1:]
                else:
                    # Map string to standard enum
                    category_map = {
                        "TECHNICAL": DocumentCategory.TECHNICAL,
                        "FINANCIAL": DocumentCategory.FINANCIAL,
                        "HR": DocumentCategory.HR,
                        "LOGISTICS": DocumentCategory.LOGISTICS,
                        "LEGAL": DocumentCategory.LEGAL,
                        "MARKETING": DocumentCategory.MARKETING,
                        "OPERATIONS": DocumentCategory.OPERATIONS,
                        "GENERAL": DocumentCategory.GENERAL
                    }
                    category = category_map.get(category_str, DocumentCategory.GENERAL)
                
                logger.info(f"Document classified as {category} with confidence {confidence}")
                if custom_category_name:
                    logger.info(f"Custom category detected: {custom_category_name}")
                
                return (category, confidence, reasoning, custom_category_name)
                
            except json.JSONDecodeError as je:
                logger.error(f"Error parsing classification JSON: {je}")
                logger.error(f"Raw response: {classification_response}")
                
                # Apply heuristic-based classification as a fallback
                return self._classify_by_heuristics(content, pdf_path)
                
        except Exception as e:
            logger.error(f"Error classifying document: {str(e)}")
            return (DocumentCategory.GENERAL, 0.0, f"Classification error: {str(e)}", None)
    
    def _is_valid_json(self, json_str):
        """Check if a string is valid JSON"""
        try:
            json.loads(json_str)
            return True
        except:
            return False

    def _extract_category_from_text(self, text):
        """Extract category directly from response text if JSON parsing fails"""
        text = text.upper()
        categories = {
            "TECHNICAL": DocumentCategory.TECHNICAL,
            "FINANCIAL": DocumentCategory.FINANCIAL,
            "HR": DocumentCategory.HR,
            "LOGISTICS": DocumentCategory.LOGISTICS,
            "LEGAL": DocumentCategory.LEGAL,
            "MARKETING": DocumentCategory.MARKETING,
            "OPERATIONS": DocumentCategory.OPERATIONS,
            "GENERAL": DocumentCategory.GENERAL
        }
        
        # Check for category mentions
        for category_name, category_enum in categories.items():
            if f'CATEGORY": "{category_name}"' in text or f'CATEGORY":"{category_name}"' in text or f'"CATEGORY": {category_name}' in text:
                return category_enum
            elif f'CATEGORY IS {category_name}' in text or f'CLASSIFIED AS {category_name}' in text:
                return category_enum
            # Look for financial terms explicitly
            elif category_name == "FINANCIAL" and any(term in text for term in ["BALANCE SHEET", "INCOME STATEMENT", "FINANCIAL STATEMENT", "CASH FLOW"]):
                return category_enum
        
        return None

    def _classify_by_heuristics(self, content, pdf_path):
        """Classify document based on content patterns when LLM classification fails"""
        filename = os.path.basename(pdf_path).lower()
        content_lower = content.lower()
        
        # Financial document indicators
        financial_terms = [
            "income statement", "balance sheet", "cash flow", "profit and loss", 
            "financial statement", "revenue", "earnings", "asset", "liability",
            "equity", "depreciation", "amortization", "fiscal", "dividend",
            "retained earnings", "accounts payable", "accounts receivable"
        ]
        
        # Count financial terms
        financial_term_count = sum(1 for term in financial_terms if term in content_lower)
        
        # Check filename for financial indicators
        financial_filename = any(term in filename for term in ["financial", "finance", "account", "budget", "invoice", "statement"])
        
        if financial_term_count >= 2 or financial_filename:
            confidence = min(0.6 + (financial_term_count * 0.05), 0.9)
            reasoning = f"Detected {financial_term_count} financial terms in document content"
            if financial_filename:
                reasoning += " and filename suggests financial content"
            return (DocumentCategory.FINANCIAL, confidence, reasoning, None)
        
        # Technical document indicators
        technical_terms = [
            "code", "software", "hardware", "system", "network", 
            "protocol", "algorithm", "function", "class", "method",
            "api", "interface", "database", "server", "client",
            "programming", "development", "deployment", "architecture"
        ]
        
        technical_term_count = sum(1 for term in technical_terms if term in content_lower)
        technical_filename = any(term in filename for term in ["tech", "code", "api", "system", "program", "software"])
        
        if technical_term_count >= 3 or technical_filename:
            confidence = min(0.6 + (technical_term_count * 0.05), 0.9)
            reasoning = f"Detected {technical_term_count} technical terms in document content"
            if technical_filename:
                reasoning += " and filename suggests technical content"
            return (DocumentCategory.TECHNICAL, confidence, reasoning, None)
        
        # HR document indicators
        hr_terms = [
            "employee", "resume", "cv", "career", "performance review", 
            "benefits", "hr policy", "hiring", "recruitment", "personnel",
            "salary", "compensation", "training", "development", "handbook"
        ]
        
        hr_term_count = sum(1 for term in hr_terms if term in content_lower)
        hr_filename = any(term in filename for term in ["hr", "employee", "resume", "cv", "career", "recruitment"])
        
        if hr_term_count >= 3 or hr_filename:
            confidence = min(0.6 + (hr_term_count * 0.05), 0.9)
            reasoning = f"Detected {hr_term_count} HR terms in document content"
            if hr_filename:
                reasoning += " and filename suggests HR content"
            return (DocumentCategory.HR, confidence, reasoning, None)
        
        # Default fallback
        return (DocumentCategory.GENERAL, 0.3, "Classification based on fallback heuristics - limited confidence", None)
    
    def organize_document(self, aws_s3_client, pdf_path, bucket_name, original_key=None):
        """Classify and organize a document in AWS S3
        
        Args:
            aws_s3_client: AWS S3 client instance
            pdf_path (str): Path to the PDF file
            bucket_name (str): S3 bucket name
            original_key (str, optional): Original S3 object key
            
        Returns:
            dict: Result of the organization operation
        """
        try:
            # 1. Classify the document
            category, confidence, reasoning, custom_category_name = self.classify_document(pdf_path, detect_custom_categories=True)
            
            # 2. Determine target folder
            if category == DocumentCategory.CUSTOM and custom_category_name:
                folder_name = custom_category_name
                
                # Ensure the folder name is valid for S3
                # Replace spaces with underscores and remove special characters
                folder_name = "".join(c if c.isalnum() or c == '_' else '_' for c in folder_name.replace(' ', '_'))
            else:
                folder_name = DocumentCategory.to_folder_name(category)
            
            # 3. Generate target key in S3
            file_name = os.path.basename(pdf_path)
            
            # If original_key is provided, use its path structure but replace the folder
            if original_key:
                # Extract the path without the filename
                path_parts = original_key.split('/')
                
                if len(path_parts) > 1:
                    # If there's a path structure, replace the category folder
                    # Get all possible category folders - both standard and any custom folders
                    # We'll check if the path contains any of these folders
                    standard_folders = ["IT", "Financial", "HR", "Logistics", "Legal", "Marketing", "Operations", "General"]
                    
                    # For custom folders, we'd need to either maintain a list or check for a certain pattern
                    # For now, we'll just use known standard folders
                    
                    # Look for any existing category folder in the path
                    category_index = -1
                    for i, part in enumerate(path_parts[:-1]):  # Skip the filename
                        if part in standard_folders:
                            category_index = i
                            break
                    
                    if category_index >= 0:
                        # Replace the existing category
                        path_parts[category_index] = folder_name
                    else:
                        # Insert the category before the filename
                        path_parts = path_parts[:-1] + [folder_name] + [path_parts[-1]]
                    
                    target_key = '/'.join(path_parts)
                else:
                    # Simple case - just add the folder
                    target_key = f"{folder_name}/{file_name}"
            else:
                # Simple case with no original structure
                target_key = f"{folder_name}/{file_name}"
                
            # Check if the folder exists in S3 and create it if it doesn't
            try:
                # The simplest way to "create" a folder in S3 is to create an empty object with a / suffix
                folder_key = f"{folder_name}/"
                
                # Check if folder exists by listing objects with this prefix
                response = aws_s3_client.s3_client.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix=folder_key,
                    MaxKeys=1
                )
                
                # If the folder doesn't exist or is empty
                if 'Contents' not in response or len(response['Contents']) == 0:
                    logger.info(f"Creating new folder '{folder_key}' in bucket {bucket_name}")
                    # Create an empty object with the folder key to establish the "folder"
                    aws_s3_client.s3_client.put_object(
                        Bucket=bucket_name,
                        Key=folder_key,
                        Body=''
                    )
                    logger.info(f"Successfully created folder '{folder_key}'")
            except Exception as e:
                logger.warning(f"Error checking/creating folder '{folder_name}': {str(e)}")
                # Continue with the upload even if folder creation fails
            
            # 4. Upload to target location in S3
            if aws_s3_client.upload_file(pdf_path, bucket_name, target_key):
                logger.info(f"Document organized successfully to {target_key}")
                
                # 5. If this was a re-organization, delete the original file
                if original_key and original_key != target_key:
                    try:
                        aws_s3_client.s3_client.delete_object(Bucket=bucket_name, Key=original_key)
                        logger.info(f"Deleted original file at {original_key}")
                    except Exception as e:
                        logger.warning(f"Failed to delete original file: {str(e)}")
                
                # Return success result
                return {
                    "success": True,
                    "category": category.name,
                    "custom_category": custom_category_name,
                    "folder": folder_name,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "target_key": target_key,
                    "original_key": original_key,
                    "is_custom_category": category == DocumentCategory.CUSTOM
                }
            else:
                logger.error(f"Failed to upload to S3 at {target_key}")
                return {
                    "success": False,
                    "error": "Failed to upload to S3",
                    "category": category.name,
                    "custom_category": custom_category_name,
                    "folder": folder_name,
                    "is_custom_category": category == DocumentCategory.CUSTOM
                }
                
        except Exception as e:
            logger.error(f"Error organizing document: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_classification_stats(self):
        """Get statistics about previous classifications
        
        Returns:
            dict: Classification statistics
        """
        # This would be expanded to track classification history
        # For now, just return a placeholder
        return {
            "total_classified": 0,
            "by_category": {
                "TECHNICAL": 0,
                "FINANCIAL": 0,
                "HR": 0,
                "GENERAL": 0
            }
        }