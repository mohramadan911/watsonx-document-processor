provider "aws" {
  region = var.aws_region
}

# S3 bucket for PDF storage
resource "aws_s3_bucket" "pdf_storage" {
  bucket = var.bucket_name

  tags = {
    Name        = "PDF Storage"
    Environment = var.environment
    Project     = "WatsonX PDF Agent"
  }
}

# S3 bucket access control
resource "aws_s3_bucket_ownership_controls" "pdf_storage_ownership" {
  bucket = aws_s3_bucket.pdf_storage.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "pdf_storage_acl" {
  depends_on = [aws_s3_bucket_ownership_controls.pdf_storage_ownership]

  bucket = aws_s3_bucket.pdf_storage.id
  acl    = "private"
}

# Bucket versioning for safety
resource "aws_s3_bucket_versioning" "pdf_storage_versioning" {
  bucket = aws_s3_bucket.pdf_storage.id

  versioning_configuration {
    status = "Enabled"
  }
}

# IAM user for application access to the bucket
resource "aws_iam_user" "app_user" {
  name = "${var.bucket_name}-app-user"

  tags = {
    Name        = "PDF Agent Application User"
    Environment = var.environment
    Project     = "WatsonX PDF Agent"
  }
}

resource "aws_iam_access_key" "app_user_key" {
  user = aws_iam_user.app_user.name
}

# IAM policy for the application user
resource "aws_iam_user_policy" "app_user_policy" {
  name = "${var.bucket_name}-app-policy"
  user = aws_iam_user.app_user.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Effect   = "Allow"
        Resource = aws_s3_bucket.pdf_storage.arn
      },
      {
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListMultipartUploadParts",
          "s3:AbortMultipartUpload"
        ]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.pdf_storage.arn}/*"
      }
    ]
  })
}

# Output the access keys for the application user
output "app_user_access_key" {
  value     = aws_iam_access_key.app_user_key.id
  sensitive = false
}

output "app_user_secret_key" {
  value     = aws_iam_access_key.app_user_key.secret
  sensitive = true
}

output "s3_bucket_name" {
  value = aws_s3_bucket.pdf_storage.bucket
}

output "s3_bucket_region" {
  value = var.aws_region
}