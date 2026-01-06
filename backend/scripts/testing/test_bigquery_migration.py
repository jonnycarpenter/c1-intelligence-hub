"""
Quick test to verify BigQuery migration is working correctly.
"""
import asyncio
import sys
sys.path.insert(0, 'backend')

from app.db.gcp_storage import get_storage


async def test_migration():
    """Test that we can fetch all master data from BigQuery."""
    print("Testing BigQuery Migration...")
    print("=" * 60)
    
    storage = await get_storage()
    
    # Test companies
    print("\n1. Testing get_companies()...")
    companies = await storage.get_companies()
    print(f"   ✓ Loaded {len(companies)} companies")
    if companies:
        sample = companies[0]
        print(f"   Sample company: {sample.get('name')}")
        print(f"   Fields: {list(sample.keys())}")
        # Check for new columns
        new_fields = ['website', 'is_c1_supplier', 'supplier_categories', 'supplier_source']
        has_new = [f for f in new_fields if f in sample]
        print(f"   New columns present: {has_new}")
    
    # Test materials
    print("\n2. Testing get_materials()...")
    materials = await storage.get_materials()
    print(f"   ✓ Loaded {len(materials)} materials")
    if materials:
        sample = materials[0]
        print(f"   Sample material: {sample.get('name')}")
        print(f"   Fields: {list(sample.keys())}")
    
    # Test industries
    print("\n3. Testing get_industries()...")
    industries = await storage.get_industries()
    print(f"   ✓ Loaded {len(industries)} industries")
    if industries:
        sample = industries[0]
        print(f"   Sample industry: {sample.get('name')}")
        print(f"   Fields: {list(sample.keys())}")
    
    # Test caching
    print("\n4. Testing cache (second call should be instant)...")
    import time
    start = time.time()
    companies2 = await storage.get_companies()
    elapsed = time.time() - start
    print(f"   ✓ Second call took {elapsed:.4f}s (cached: {elapsed < 0.1})")
    
    print("\n" + "=" * 60)
    print("✅ Migration test complete!")
    print(f"\nSummary:")
    print(f"  - Companies: {len(companies)} (with {len(has_new)} new fields)")
    print(f"  - Materials: {len(materials)}")
    print(f"  - Industries: {len(industries)}")
    print(f"  - Caching: {'Working' if elapsed < 0.1 else 'Not working'}")


if __name__ == "__main__":
    asyncio.run(test_migration())
