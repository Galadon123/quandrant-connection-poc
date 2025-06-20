## Terraform Configuration for Qdrant on AWS EC2

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
    }
    random = {
      source  = "hashicorp/random"
    }
  }

  required_version = ">= 1.3.0"
}

provider "aws" {
  region = "ap-southeast-1"
}

# Generate SSH Key Pair
resource "tls_private_key" "ssh_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "generated_key" {
  key_name   = "my-key"
  public_key = tls_private_key.ssh_key.public_key_openssh
}

resource "local_file" "private_key_pem" {
  content         = tls_private_key.ssh_key.private_key_pem
  filename        = "${path.module}/my-key.pem"
  file_permission = "0400"
}

# VPC
resource "aws_vpc" "my_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = {
    Name = "my-vpc"
  }
}

# Subnet
resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.my_vpc.id
  cidr_block              = "10.0.101.0/24"
  availability_zone       = "ap-southeast-1a"
  map_public_ip_on_launch = true
  tags = {
    Name = "public-subnet"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.my_vpc.id
  tags = {
    Name = "internet-gateway"
  }
}

# Route Table
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.my_vpc.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = {
    Name = "public-route-table"
  }
}

# Route Table Association
resource "aws_route_table_association" "public_association" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.public_rt.id
}

# Security Group
resource "aws_security_group" "ec2_sg" {
  name        = "ec2-security-group"
  description = "Security group for EC2 instance"
  vpc_id      = aws_vpc.my_vpc.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  # Allow all traffic
  ingress {
    from_port   = 6333
    to_port     = 6333
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 6334
    to_port     = 6334
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "ec2-security-group"
  }
}

# EC2 Instance
resource "aws_instance" "my_instance" {
  ami           = "ami-0672fd5b9210aa093"  # Ubuntu 22.04
  instance_type = "t3.small"
  subnet_id     = aws_subnet.public_subnet.id
  key_name      = aws_key_pair.generated_key.key_name
  vpc_security_group_ids = [aws_security_group.ec2_sg.id]

  tags = {
    Name = "my-ec2-instance"
  }
}

output "private_key_path" {
  value       = local_file.private_key_pem.filename
  description = "Private key file path"
}

output "instance_public_ip" {
  value       = aws_instance.my_instance.public_ip
  description = "Public IP of EC2 instance"
}
```

## Initilize and Apply Terraform

```bash
terraform init
terraform apply -auto-approve
```

## Configure the EC2 Instance

1. SSH into the EC2 instance using the key pair created during the Terraform setup.
   ```bash
   ssh -i my-key.pem ubuntu@$(terraform output -raw instance_public_ip)
   ```
2. Install Docker:
   ```bash
   sudo apt-get update
   sudo apt-get install -y docker.io
   sudo systemctl start docker
   sudo systemctl enable docker
   sudo usermod -aG docker $USER
   ```
3. Create Directory for Qdrant Data
   ```bash
   mkdir -p ~/qdrant_data
   ```
4. Deploy Qdrant Container
    ```bash
    docker run -d \
      --name qdrant \
      -p 6333:6333 \
      -p 6334:6334 \
      -v ~/qdrant_data:/qdrant/storage \
      --restart unless-stopped \
      qdrant/qdrant:latest
    ```
5. Verify Qdrant is Running
   Health Check:
   ```bash
   curl http://localhost:6333
   ```
   Check Collections:
   ```bash
   curl http://localhost:6333/collections
   ```
## Create a Collection

```bash
curl -X PUT http://YOUR-EC2-PUBLIC-IP:6333/collections/test_collection \
  -H 'Content-Type: application/json' \
  -d '{
    "vectors": {
      "size": 4,
      "distance": "Dot"
    }
  }'
```

## Insert Data into the Collection

```bash
curl -X PUT http://YOUR-EC2-PUBLIC-IP:6333/collections/test_collection/points \
  -H 'Content-Type: application/json' \
  -d '{
    "points": [
      {
        "id": 1,
        "vector": [0.05, 0.61, 0.76, 0.74],
        "payload": {"city": "Berlin", "country": "Germany"}
      },
      {
        "id": 2,
        "vector": [0.19, 0.81, 0.75, 0.11],
        "payload": {"city": "London", "country": "UK"}
      },
      {
        "id": 3,
        "vector": [0.36, 0.55, 0.47, 0.94],
        "payload": {"city": "Moscow", "country": "Russia"}
      }
    ]
  }'
```

## Search for Similar Vectors

```bash
curl -X POST http://YOUR-EC2-PUBLIC-IP:6333/collections/test_collection/points/search \
  -H 'Content-Type: application/json' \
  -d '{
    "vector": [0.2, 0.1, 0.9, 0.7],
    "limit": 3
  }'
```

## Python Client Setup

### Create virtual environment
```bash
python3 -m venv qdrant-env
source qdrant-env/bin/activate
```

### Install Qdrant Client
```bash
pip install qdrant-client numpy requests
```

### Python Connection Test

Export the environment variables for Qdrant connection:

```bash
export QDRANT_HOST=YOUR-EC2-PUBLIC-IP
```

```python
import os
import sys
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter
import numpy as np


class QdrantManager:
    """Simple Qdrant client manager"""
    
    def __init__(self):
        self.host = os.getenv('QDRANT_HOST')
        self.port = int(os.getenv('QDRANT_PORT', 6333))
        
        if not self.host:
            print("Error: Set QDRANT_HOST environment variable")
            print("Example: export QDRANT_HOST=13.250.25.109")
            sys.exit(1)
        
        try:
            self.client = QdrantClient(host=self.host, port=self.port)
            self.client.get_collections()  # Test connection
        except Exception as e:
            print(f"Connection failed: {e}")
            sys.exit(1)
    
    def list_collections(self):
        """List all collections"""
        collections = self.client.get_collections()
        if not collections.collections:
            print("No collections found")
            return []
        
        collection_names = []
        for collection in collections.collections:
            info = self.client.get_collection(collection.name)
            print(f"{collection.name}: {info.points_count} points")
            collection_names.append(collection.name)
        return collection_names
    
    def create_collection(self, name: str, vector_size: int, distance: str = "Cosine"):
        """Create a new collection"""
        distance_map = {
            "Cosine": Distance.COSINE,
            "Dot": Distance.DOT,
            "Euclidean": Distance.EUCLID
        }
        
        try:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=vector_size, 
                    distance=distance_map.get(distance, Distance.COSINE)
                )
            )
            print(f"Created collection: {name}")
        except Exception as e:
            print(f"Failed to create collection: {e}")
    
    def insert_points(self, collection_name: str, points: List[Dict[str, Any]]):
        """Insert points into collection"""
        qdrant_points = []
        for point in points:
            qdrant_point = PointStruct(
                id=point['id'],
                vector=point['vector'],
                payload=point.get('payload', {})
            )
            qdrant_points.append(qdrant_point)
        
        try:
            self.client.upsert(collection_name=collection_name, points=qdrant_points)
            print(f"Inserted {len(points)} points")
        except Exception as e:
            print(f"Failed to insert points: {e}")
    
    def search(self, collection_name: str, query_vector: List[float], 
               limit: int = 5, filter_condition: Optional[Dict] = None):
        """Search for similar vectors"""
        try:
            search_filter = Filter(**filter_condition) if filter_condition else None
            
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=search_filter,
                with_payload=True
            )
            # De
            search_results = []
            for result in results:
                search_results.append({
                    'id': result.id,
                    'score': result.score,
                    'payload': result.payload
                })
            
            return search_results
        except Exception as e:
            print(f"Search failed: {e}")
            return []
    
    def get_info(self, collection_name: str):
        """Get collection information"""
        try:
            info = self.client.get_collection(collection_name)
            return {
                'points_count': info.points_count,
                'vector_size': info.config.params.vectors.size,
                'distance': str(info.config.params.vectors.distance)
            }
        except Exception as e:
            print(f"Failed to get info: {e}")
            return None
    
    def delete_collection(self, collection_name: str):
        """Delete a collection"""
        try:
            self.client.delete_collection(collection_name)
            print(f"Deleted collection: {collection_name}")
        except Exception as e:
            print(f"Failed to delete collection: {e}")


def main():
    # Initialize connection
    qdrant = QdrantManager()
    
    # List existing collections
    print("Collections:")
    collections = qdrant.list_collections()
    
    # If test_collection exists, search it
    if 'test_collection' in collections:
        print("\nSearching test_collection:")
        results = qdrant.search('test_collection', [0.2, 0.1, 0.9, 0.7], limit=3)
        for i, result in enumerate(results, 1):
            print(f"{i}. ID: {result['id']}, Score: {result['score']:.3f}")
            if result['payload']:
                print(f"   {result['payload']}")
    
    # Demo: Create and use a new collection
    print("\nDemo - Creating new collection:")
    collection_name = "python_demo"
    
    # Create collection
    qdrant.create_collection(collection_name, vector_size=4, distance="Dot")
    
    # Insert sample data
    sample_data = [
        {
            'id': 1,
            'vector': [0.1, 0.2, 0.3, 0.4],
            'payload': {'name': 'item_1', 'category': 'A'}
        },
        {
            'id': 2,
            'vector': [0.5, 0.6, 0.7, 0.8],
            'payload': {'name': 'item_2', 'category': 'B'}
        },
        {
            'id': 3,
            'vector': [0.9, 0.1, 0.5, 0.2],
            'payload': {'name': 'item_3', 'category': 'A'}
        }
    ]
    
    qdrant.insert_points(collection_name, sample_data)
    
    # Search
    print(f"\nSearching {collection_name}:")
    results = qdrant.search(collection_name, [0.1, 0.2, 0.3, 0.4], limit=2)
    for i, result in enumerate(results, 1):
        print(f"{i}. ID: {result['id']}, Score: {result['score']:.3f}")
        print(f"   {result['payload']}")
    
    # Clean up
    qdrant.delete_collection(collection_name)


if __name__ == "__main__":
    main()
```

### Run the Python script
```bash
python app.py
```