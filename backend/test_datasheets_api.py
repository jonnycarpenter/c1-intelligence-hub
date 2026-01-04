"""Test the datasheets API endpoints using FastAPI TestClient."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_stats():
    """Test the /api/datasheets/stats endpoint."""
    print("\n=== Testing GET /api/datasheets/stats ===")
    response = client.get("/api/datasheets/stats")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Total datasheets: {data['total_datasheets']}")
        print(f"Total suppliers: {data['total_suppliers']}")
        print("\nSupplier breakdown:")
        for supplier in data['suppliers']:
            print(f"  - {supplier['supplier_name']}: {supplier['datasheet_count']} datasheets")
        print(f"\nCategories: {list(data['categories'].keys())}")
    else:
        print(f"Error: {response.text}")


def test_list():
    """Test the /api/datasheets endpoint."""
    print("\n=== Testing GET /api/datasheets ===")
    response = client.get("/api/datasheets", params={"limit": 5})
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Returned: {data['count']} / {data['total']} total")
        print(f"Available suppliers: {data['suppliers']}")
        print(f"Available categories: {data['categories']}")
        print("\nFirst 5 datasheets:")
        for ds in data['datasheets'][:5]:
            print(f"  - [{ds['supplier_name']}] {ds['title'][:60]}...")
    else:
        print(f"Error: {response.text}")


def test_search():
    """Test the /api/datasheets/search endpoint."""
    print("\n=== Testing GET /api/datasheets/search?q=carbon ===")
    response = client.get("/api/datasheets/search", params={"q": "carbon", "limit": 5})
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Found: {data['count']} results for '{data['query']}'")
        print("\nResults:")
        for ds in data['datasheets'][:5]:
            print(f"  - [{ds['supplier_name']}] {ds['title']}")
    else:
        print(f"Error: {response.text}")


def test_filter_by_supplier():
    """Test filtering by supplier."""
    print("\n=== Testing GET /api/datasheets?supplier=Hexcel ===")
    response = client.get("/api/datasheets", params={"supplier": "Hexcel", "limit": 5})
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Found: {data['count']} / {data['total']} Hexcel datasheets")
        for ds in data['datasheets'][:5]:
            print(f"  - {ds['title'][:60]}...")
    else:
        print(f"Error: {response.text}")


def test_get_single():
    """Test getting a single datasheet by ID."""
    # First get a datasheet ID
    response = client.get("/api/datasheets", params={"limit": 1})
    if response.status_code == 200 and response.json()['datasheets']:
        ds_id = response.json()['datasheets'][0]['datasheet_id']
        
        print(f"\n=== Testing GET /api/datasheets/{ds_id} ===")
        response = client.get(f"/api/datasheets/{ds_id}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Title: {data['title']}")
            print(f"Supplier: {data['supplier_name']}")
            print(f"Category: {data['material_category']}")
            print(f"File size: {data['file_size_bytes']} bytes")
            print(f"Extracted text length: {len(data.get('extracted_text', ''))} chars")
            print(f"Text preview: {data.get('text_preview', '')[:200]}...")
        else:
            print(f"Error: {response.text}")


if __name__ == "__main__":
    print("=" * 60)
    print("DATASHEETS API TEST")
    print("=" * 60)
    
    test_stats()
    test_list()
    test_search()
    test_filter_by_supplier()
    test_get_single()
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
