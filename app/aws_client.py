# aws_client.py
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import logging
import os
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AWSS3Client:
    """AWS S3 Client for handling PDF documents"""
    
    def __init__(self, aws_access_key, aws_secret_key, region_name):
        """Initialize the AWS S3 client
        
        Args:
            aws_access_key (str): AWS access key ID
            aws_secret_key (str): AWS secret access key
            region_name (str): AWS region name (e.g., 'us-east-1')
        """
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.region_name = region_name
        self.s3_client = None
    
    def connect(self):
        """Connect to AWS S3
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.region_name
            )
            # Test connection by listing buckets
            self.s3_client.list_buckets()
            logger.info("Successfully connected to AWS S3")
            return True
        except NoCredentialsError:
            logger.error("AWS credentials not available")
            return False
        except ClientError as e:
            logger.error(f"AWS S3 connection error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unknown error connecting to AWS S3: {str(e)}")
            return False
    
    def list_buckets(self):
        """List all S3 buckets
        
        Returns:
            list: List of bucket names
        """
        if not self.s3_client:
            if not self.connect():
                return []
        
        try:
            response = self.s3_client.list_buckets()
            buckets = [bucket['Name'] for bucket in response['Buckets']]
            logger.info(f"Found {len(buckets)} buckets")
            return buckets
        except Exception as e:
            logger.error(f"Error listing buckets: {str(e)}")
            return []
    
    def list_objects(self, bucket_name, prefix="", max_keys=100):
        """List objects in a bucket with optional prefix
        
        Args:
            bucket_name (str): Name of the S3 bucket
            prefix (str, optional): Prefix to filter objects. Defaults to "".
            max_keys (int, optional): Maximum number of keys to return. Defaults to 100.
            
        Returns:
            list: List of objects with metadata
        """
        if not self.s3_client:
            if not self.connect():
                return []
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            if 'Contents' not in response:
                logger.info(f"No objects found in bucket {bucket_name} with prefix {prefix}")
                return []
                
            objects = []
            for obj in response['Contents']:
                # Only include PDF files
                if obj['Key'].lower().endswith('.pdf'):
                    objects.append({
                        'key': obj['Key'],
                        'name': os.path.basename(obj['Key']),
                        'size': obj['Size'],
                        'last_modified': obj['LastModified']
                    })
            logger.info(f"Found {len(objects)} PDF objects in bucket {bucket_name}")
            return objects
        except Exception as e:
            logger.error(f"Error listing objects in bucket {bucket_name}: {str(e)}")
            return []
    
    def download_file(self, bucket_name, object_key, output_path=None):
        """Download a file from S3 to local filesystem
        
        Args:
            bucket_name (str): Name of the S3 bucket
            object_key (str): Key of the object to download
            output_path (str, optional): Local path to save the file. If None, a temporary file is created.
            
        Returns:
            str: Path to the downloaded file if successful, None otherwise
        """
        if not self.s3_client:
            if not self.connect():
                return None
        
        try:
            # If no output path provided, create a temporary file
            if output_path is None:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                output_path = temp_file.name
                temp_file.close()
            
            self.s3_client.download_file(bucket_name, object_key, output_path)
            logger.info(f"Successfully downloaded {object_key} to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error downloading file {object_key} from bucket {bucket_name}: {str(e)}")
            return None
    
    def upload_file(self, file_path, bucket_name, object_key=None):
        """Upload a file to S3
        
        Args:
            file_path (str): Local path of the file to upload
            bucket_name (str): Name of the S3 bucket
            object_key (str, optional): Key to use for the object. If None, the filename is used.
            
        Returns:
            bool: True if upload successful, False otherwise
        """
        if not self.s3_client:
            if not self.connect():
                return False
        
        try:
            # If no object key provided, use the filename
            if object_key is None:
                object_key = os.path.basename(file_path)
            
            self.s3_client.upload_file(file_path, bucket_name, object_key)
            logger.info(f"Successfully uploaded {file_path} to {bucket_name}/{object_key}")
            return True
        except Exception as e:
            logger.error(f"Error uploading file {file_path} to bucket {bucket_name}: {str(e)}")
            return False