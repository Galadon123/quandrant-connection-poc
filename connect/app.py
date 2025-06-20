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