"""Products API endpoints - Product catalog and product intelligence."""

from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.mcp.tools.product_intelligence import PRODUCT_CATALOG
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class ProductSpec(BaseModel):
    """Product specification model."""
    key: str
    value: str


class Product(BaseModel):
    """Product model for API responses."""
    id: str
    name: str
    supplier: str
    category: str
    subcategory: Optional[str] = None
    industries: List[str] = []
    specs: dict = {}
    in_c1_catalog: bool = False


class ProductsResponse(BaseModel):
    """Response model for products list."""
    count: int
    products: List[Product]
    categories: List[str]
    suppliers: List[str]


class ProductComparisonResponse(BaseModel):
    """Response model for product comparison."""
    products: List[Product]
    spec_keys: List[str]
    comparison_table: dict


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=ProductsResponse)
async def get_products(
    category: Optional[str] = Query(None, description="Filter by category"),
    supplier: Optional[str] = Query(None, description="Filter by supplier"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    query: Optional[str] = Query(None, description="Search query"),
    c1_only: bool = Query(False, description="Only show C1 catalog products"),
    limit: int = Query(100, le=500, description="Maximum products to return"),
):
    """
    Get products from the catalog with optional filtering.
    
    Supports filtering by:
    - category: carbon_fiber, glass_fiber, prepreg, resin, etc.
    - supplier: Hexcel, Toray, Owens Corning, etc.
    - industry: aerospace, automotive, marine, wind_energy, etc.
    - query: Free text search
    - c1_only: Only products in Composites One catalog
    """
    logger.info(f"GET /products: category={category}, supplier={supplier}, industry={industry}, query={query}")
    
    results = PRODUCT_CATALOG.copy()
    
    # Apply filters
    if category:
        results = [p for p in results if category.lower() in p.get("category", "").lower()]
    
    if supplier:
        results = [p for p in results if supplier.lower() in p.get("supplier", "").lower()]
    
    if industry:
        results = [p for p in results 
                   if industry.lower() in [i.lower() for i in p.get("industries", [])]]
    
    if query:
        q = query.lower()
        results = [p for p in results if 
                   q in p.get("name", "").lower() or
                   q in p.get("supplier", "").lower() or
                   q in p.get("category", "").lower() or
                   q in p.get("subcategory", "").lower() or
                   q in p.get("id", "").lower()]
    
    if c1_only:
        results = [p for p in results if p.get("in_c1_catalog", False)]
    
    # Apply limit
    results = results[:limit]
    
    # Get unique categories and suppliers for filtering UI
    all_categories = sorted(set(p.get("category", "") for p in PRODUCT_CATALOG if p.get("category")))
    all_suppliers = sorted(set(p.get("supplier", "") for p in PRODUCT_CATALOG if p.get("supplier")))
    
    # Format response
    products = [
        Product(
            id=p["id"],
            name=p["name"],
            supplier=p["supplier"],
            category=p.get("category", ""),
            subcategory=p.get("subcategory"),
            industries=p.get("industries", []),
            specs=p.get("specs", {}),
            in_c1_catalog=p.get("in_c1_catalog", False),
        )
        for p in results
    ]
    
    return ProductsResponse(
        count=len(products),
        products=products,
        categories=all_categories,
        suppliers=all_suppliers,
    )


@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: str):
    """Get a specific product by ID."""
    logger.info(f"GET /products/{product_id}")
    
    for p in PRODUCT_CATALOG:
        if p["id"] == product_id:
            return Product(
                id=p["id"],
                name=p["name"],
                supplier=p["supplier"],
                category=p.get("category", ""),
                subcategory=p.get("subcategory"),
                industries=p.get("industries", []),
                specs=p.get("specs", {}),
                in_c1_catalog=p.get("in_c1_catalog", False),
            )
    
    raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")


@router.get("/compare/{product_ids}")
async def compare_products(product_ids: str):
    """
    Compare multiple products side-by-side.
    
    Args:
        product_ids: Comma-separated list of product IDs
    """
    ids = [id.strip() for id in product_ids.split(",")]
    
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 products to compare")
    
    if len(ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 products for comparison")
    
    products = []
    for pid in ids:
        for p in PRODUCT_CATALOG:
            if p["id"] == pid:
                products.append(Product(
                    id=p["id"],
                    name=p["name"],
                    supplier=p["supplier"],
                    category=p.get("category", ""),
                    subcategory=p.get("subcategory"),
                    industries=p.get("industries", []),
                    specs=p.get("specs", {}),
                    in_c1_catalog=p.get("in_c1_catalog", False),
                ))
                break
    
    if len(products) < 2:
        raise HTTPException(status_code=404, detail="Could not find enough products to compare")
    
    # Get all spec keys
    all_spec_keys = set()
    for p in products:
        all_spec_keys.update(p.specs.keys())
    
    # Build comparison table
    comparison_table = {}
    for key in sorted(all_spec_keys):
        comparison_table[key] = {
            p.id: p.specs.get(key, "N/A") for p in products
        }
    
    return ProductComparisonResponse(
        products=products,
        spec_keys=sorted(all_spec_keys),
        comparison_table=comparison_table,
    )


@router.get("/categories/list")
async def get_categories():
    """Get list of all product categories with counts."""
    category_counts = {}
    for p in PRODUCT_CATALOG:
        cat = p.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    return {
        "categories": [
            {"id": cat, "label": cat.replace("_", " ").title(), "count": count}
            for cat, count in sorted(category_counts.items())
        ],
        "total": len(PRODUCT_CATALOG),
    }


@router.get("/suppliers/list")
async def get_suppliers():
    """Get list of all suppliers with counts."""
    supplier_counts = {}
    for p in PRODUCT_CATALOG:
        supplier = p.get("supplier", "Unknown")
        supplier_counts[supplier] = supplier_counts.get(supplier, 0) + 1
    
    return {
        "suppliers": [
            {"name": supplier, "count": count}
            for supplier, count in sorted(supplier_counts.items())
        ],
        "total": len(PRODUCT_CATALOG),
    }


@router.get("/gaps/{category}")
async def get_product_gaps(
    category: str,
    industry: Optional[str] = Query(None, description="Filter by industry"),
):
    """
    Get product gap analysis - what competitors offer that C1 doesn't.
    
    Args:
        category: Product category to analyze
        industry: Optional industry filter
    """
    logger.info(f"GET /products/gaps/{category}")
    
    # Filter products
    results = [p for p in PRODUCT_CATALOG if category.lower() in p.get("category", "").lower()]
    
    if industry:
        results = [p for p in results 
                   if industry.lower() in [i.lower() for i in p.get("industries", [])]]
    
    if not results:
        raise HTTPException(status_code=404, detail=f"No products found in category: {category}")
    
    we_carry = [p for p in results if p.get("in_c1_catalog", False)]
    gaps = [p for p in results if not p.get("in_c1_catalog", False)]
    
    # Group gaps by supplier
    gaps_by_supplier = {}
    for p in gaps:
        supplier = p["supplier"]
        if supplier not in gaps_by_supplier:
            gaps_by_supplier[supplier] = []
        gaps_by_supplier[supplier].append({
            "id": p["id"],
            "name": p["name"],
            "industries": p.get("industries", []),
        })
    
    coverage_pct = (len(we_carry) / len(results) * 100) if results else 0
    
    return {
        "category": category,
        "industry_filter": industry,
        "summary": {
            "total_products": len(results),
            "we_carry": len(we_carry),
            "gaps": len(gaps),
            "coverage_percent": round(coverage_pct, 1),
        },
        "products_we_carry": [
            {"id": p["id"], "name": p["name"], "supplier": p["supplier"]}
            for p in we_carry
        ],
        "gaps_by_supplier": gaps_by_supplier,
    }
