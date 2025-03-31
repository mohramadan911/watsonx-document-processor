# Autonomous Document Processing System



A fully autonomous document processing system powered by IBM watsonx.ai and CrewAI. This solution automatically monitors document repositories, intelligently classifies documents based on content, organizes them into appropriate folders, and triggers relevant workflows—all with zero human intervention.

## 🚀 Features

- **Autonomous Monitoring**: Continuously monitors S3 buckets for new document arrivals
- **Intelligent Classification**: Uses watsonx.ai to understand document content and classify appropriately
- **Dynamic Organization**: Automatically creates and maintains folder structures in S3
- **Smart Summarization**: Generates comprehensive document summaries
- **Personalized Recommendations**: Provides relevant next steps based on document content
- **Email Integration**: Sends notifications and can process email attachments
- **Workflow Automation**: Schedules reviews and follow-ups for critical documents

## 🏗️ Architecture

Our autonomous document processing system uses a multi-agent architecture:


- **Document Scout Agent**: Monitors repositories for new documents
- **Document Reader Agent**: Extracts content and metadata
- **Content Analyst Agent**: Analyzes and summarizes document content
- **Document Classifier Agent**: Categorizes documents based on content
- **Workflow Manager Agent**: Determines appropriate actions and workflows

## 💻 Technologies Used

- **IBM watsonx.ai**: Foundation model for document understanding and analysis
- **CrewAI**: Framework for autonomous agent orchestration
- **AWS S3**: Document storage and organization
- **Microsoft Graph API**: Email and calendar integration
- **Streamlit**: User interface
- **Dockling**: PDF processing and content extraction
- **Python 3.9**: Core programming language

## 🛠️ Setup and Installation

### Prerequisites

- Python 3.9+
- AWS account with S3 access
- IBM watsonx.ai API credentials
- (Optional) Microsoft 365 credentials for email capabilities

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/autonomous-document-processor.git
   cd autonomous-document-processor
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

## 🚀 Usage

### Starting the Application

```bash
streamlit run ./app/app.py
```

### Configuration

1. On first run, navigate to the "Configuration" tab
2. Enter your WatsonX, AWS, and (optional) Microsoft credentials
3. Click "Initialize WatsonX Model" and "Connect to AWS S3"
4. Select buckets to monitor for documents

### Processing Documents

The system offers two modes:

1. **Manual Upload**: Upload documents directly through the UI
2. **Autonomous Monitoring**: Documents in monitored S3 buckets are processed automatically

## 📁 Project Structure

- `document_flow.py`: Core document processing flow using CrewAI
- `monitors.py`: Document monitoring system for S3 buckets
- `app.py`: Streamlit UI and application entry point
- `aws_client.py`: AWS S3 client for document storage operations
- `pdf_agent.py`: WatsonX-powered document agent
- `dockling_tool.py`: PDF document extraction and search tool
- `document_classifier.py`: Document classification system

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request



## 🙏 Acknowledgements

- IBM watsonx.ai team for the powerful foundation model
- CrewAI for the agent orchestration framework
- All contributors who have helped shape this project

---

Built with ❤️ by [PandasTeam]

[This readme has been written by cursor conected to Sonnet3.7]



