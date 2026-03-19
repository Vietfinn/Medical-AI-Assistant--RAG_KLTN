"""
Script để kiểm tra kết nối Qdrant Cloud
Chạy script này để verify credentials trước khi index data
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    """Test Qdrant Cloud connection"""
    
    print("=" * 70)
    print("QDRANT CLOUD CONNECTION TEST")
    print("=" * 70)
    print(f"\n📋 Configuration:")
    print(f"   Mode: {settings.QDRANT_MODE}")
    
    if settings.QDRANT_MODE == "cloud":
        print(f"   URL: {settings.QDRANT_CLOUD_URL}")
        print(f"   API Key: {settings.QDRANT_API_KEY[:20]}..." if settings.QDRANT_API_KEY else "   API Key: NOT SET")
    else:
        print(f"   Host: {settings.QDRANT_HOST}")
        print(f"   Port: {settings.QDRANT_PORT}")
    
    print("\n🔌 Testing connection...")
    
    try:
        # Get connection parameters
        params = settings.get_qdrant_client_params()
        
        # Create client
        client = QdrantClient(**params)
        
        # Test connection by getting collections
        collections = client.get_collections()
        
        print("✅ CONNECTION SUCCESSFUL!")
        print(f"\n📊 Server Info:")
        print(f"   Collections found: {len(collections.collections)}")
        
        if collections.collections:
            print(f"\n📁 Existing collections:")
            for collection in collections.collections:
                print(f"   - {collection.name}")
                
                # Get collection info
                try:
                    info = client.get_collection(collection.name)
                    print(f"     Points: {info.points_count}")
                    print(f"     Vectors: {info.vectors_count}")
                except Exception as e:
                    print(f"     (Could not get details: {e})")
        else:
            print("\n💡 No collections found yet. This is normal for a new cluster.")
        
        # Get cluster info (if available)
        try:
            cluster_info = client.get_cluster_info()
            print(f"\n🌐 Cluster Info:")
            print(f"   Status: {cluster_info.status}")
            print(f"   Peers: {len(cluster_info.peers)}")
        except:
            # Not all Qdrant versions support this
            pass
        
        print("\n" + "=" * 70)
        print("✅ ALL CHECKS PASSED - Ready to index data!")
        print("=" * 70)
        print("\n📝 Next step:")
        print("   python scripts/index_data.py")
        
        client.close()
        return True
        
    except Exception as e:
        print("\n❌ CONNECTION FAILED!")
        print(f"\n🔍 Error: {str(e)}")
        print("\n🛠️  TROUBLESHOOTING:")
        
        if settings.QDRANT_MODE == "cloud":
            print("\n1. Kiểm tra QDRANT_CLOUD_URL:")
            print(f"   Current: {settings.QDRANT_CLOUD_URL}")
            print("   Format: https://[cluster-id].[region].aws.cloud.qdrant.io:6333")
            print("   Đảm bảo có :6333 ở cuối")
            
            print("\n2. Kiểm tra QDRANT_API_KEY:")
            if not settings.QDRANT_API_KEY:
                print("   ❌ API Key CHƯA ĐƯỢC SET trong file .env")
            else:
                print("   ✅ API Key đã set")
                print(f"   Preview: {settings.QDRANT_API_KEY[:20]}...")
                print("   Đảm bảo copy đầy đủ API key từ Qdrant Cloud")
            
            print("\n3. Kiểm tra Cluster Status:")
            print("   - Truy cập https://cloud.qdrant.io/")
            print("   - Đảm bảo cluster đang ở trạng thái 'Running'")
            print("   - Nếu 'Stopped', click 'Start' và đợi 2-3 phút")
            
            print("\n4. Kiểm tra Network:")
            print("   - Đảm bảo có internet connection")
            print("   - Firewall có thể block connection")
            print("   - Thử từ network khác")
            
        else:
            print("\n1. Kiểm tra Qdrant Docker:")
            print("   docker ps | grep qdrant")
            print("\n2. Nếu không chạy, khởi động:")
            print("   docker run -d -p 6333:6333 qdrant/qdrant")
            
        print("\n" + "=" * 70)
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
