# run.py
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure all required environment variables are set
required_env_vars = [
    "WATSONX_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "MS_CLIENT_ID",
    "MS_CLIENT_SECRET",
    "MS_TENANT_ID",
    "MS_USER_EMAIL"
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    print(f"Error: The following environment variables are required: {', '.join(missing_vars)}")
    print("Please create a .env file with these variables or set them in your environment.")
    sys.exit(1)

# Run the Streamlit app
if __name__ == "__main__":
    import streamlit.cli
    sys.argv = ["streamlit", "run", "app.py"]
    streamlit.cli.main()