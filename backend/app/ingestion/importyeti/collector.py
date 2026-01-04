"""
ImportYeti Data Collector
=========================

Collects trade data from ImportYeti API and transforms to data models.
Handles the bi-weekly pull cycle.
"""

import os
import json
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field

from .client import ImportYetiClient, APIResponse
from .models import (
    Snapshot,
    SupplierProfile,
    CompanyProfile,
    SupplierCustomerRelationship,
    CompanySupplierRelationship,
    ProductMarketResult,
    ChangeEvent,
    ChangeEventType,
    Significance,
    SupplierTier,
    normalize_key,
    normalize_name,
)
from .config import (
    TrackedSupplier,
    TrackedOEM,
    get_all_tracked_suppliers,
    get_all_tracked_oems,
    PRODUCT_SEARCHES,
)

logger = logging.getLogger(__name__)


@dataclass
class CollectionStats:
    """Statistics from a collection run."""
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Counts
    suppliers_fetched: int = 0
    companies_fetched: int = 0
    supplier_customer_relationships: int = 0
    company_supplier_relationships: int = 0
    product_market_results: int = 0
    
    # Credits
    credits_used: int = 0
    credits_remaining: Optional[int] = None
    
    # Errors
    errors: List[str] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0


@dataclass
class CollectionResult:
    """Results from a full collection run."""
    stats: CollectionStats
    snapshots: List[Snapshot] = field(default_factory=list)
    suppliers: List[SupplierProfile] = field(default_factory=list)
    companies: List[CompanyProfile] = field(default_factory=list)
    supplier_customers: List[SupplierCustomerRelationship] = field(default_factory=list)
    company_suppliers: List[CompanySupplierRelationship] = field(default_factory=list)
    product_market: List[ProductMarketResult] = field(default_factory=list)
    change_events: List[ChangeEvent] = field(default_factory=list)


class ImportYetiCollector:
    """
    Collects and transforms ImportYeti trade data.
    
    Usage:
        collector = ImportYetiCollector()
        result = await collector.run_full_collection()
        
        # Access results
        for supplier in result.suppliers:
            print(f"{supplier.supplier_name}: {supplier.total_us_customers} customers")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        client: Optional[ImportYetiClient] = None,
        tracked_suppliers: Optional[Dict[str, TrackedSupplier]] = None,
        tracked_oems: Optional[Dict[str, TrackedOEM]] = None,
    ):
        self.client = client or ImportYetiClient(api_key=api_key)
        self.tracked_suppliers = tracked_suppliers or get_all_tracked_suppliers()
        self.tracked_oems = tracked_oems or get_all_tracked_oems()
        
        # C1's company key in ImportYeti
        self.c1_company_key = "composites-one"
        
        # Cache for relationship tracking
        self._previous_supplier_customers: Dict[str, Set[str]] = {}
        self._previous_company_suppliers: Dict[str, Set[str]] = {}
    
    async def check_database_updated(self) -> Optional[datetime]:
        """
        Check when ImportYeti database was last updated.
        
        Returns:
            Last update datetime, or None if check failed
        """
        response = await self.client.get_database_updated()
        if response.success and response.data:
            date_str = response.data.get("last_updated")
            if date_str:
                try:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    pass
        return None
    
    async def run_full_collection(
        self,
        include_oems: bool = True,
        include_products: bool = False,  # Quarterly only
        max_suppliers: Optional[int] = None,
        max_oems: Optional[int] = None,
        max_credits: Optional[int] = None,
    ) -> CollectionResult:
        """
        Run a full bi-weekly collection cycle.
        
        Args:
            include_oems: Fetch OEM profiles for competitive intel
            include_products: Run product market searches (quarterly)
            max_suppliers: Limit suppliers to fetch (for testing)
            max_oems: Limit OEMs to fetch (for testing)
            
        Returns:
            CollectionResult with all collected data
        """
        stats = CollectionStats()
        result = CollectionResult(stats=stats)
        snapshot_date = date.today()
        
        try:
            async with self.client:
                # 1. Fetch tracked suppliers
                logger.info(f"Fetching {len(self.tracked_suppliers)} tracked suppliers...")
                suppliers_to_fetch = list(self.tracked_suppliers.values())
                if max_suppliers:
                    suppliers_to_fetch = suppliers_to_fetch[:max_suppliers]
                
                for supplier in suppliers_to_fetch:
                    # Check credit limit
                    if max_credits and self.client.credits_used_session >= max_credits:
                        logger.warning(f"Credit limit reached: {self.client.credits_used_session}")
                        break

                    try:
                        supplier_data, relationships = await self._fetch_supplier(
                            supplier, snapshot_date
                        )
                        if supplier_data:
                            result.suppliers.append(supplier_data)
                            result.supplier_customers.extend(relationships)
                            stats.suppliers_fetched += 1
                            stats.supplier_customer_relationships += len(relationships)
                    except Exception as e:
                        logger.error(f"Failed to fetch supplier {supplier.name}: {e}")
                        stats.errors.append(f"Supplier {supplier.name}: {str(e)[:100]}")
                
                # 2. Fetch C1's company profile
                logger.info("Fetching Composites One profile...")
                try:
                    c1_data, c1_suppliers = await self._fetch_company(
                        self.c1_company_key, "Composites One", snapshot_date
                    )
                    if c1_data:
                        c1_data.is_c1_customer = False  # C1 is not a customer, it's the subject
                        result.companies.append(c1_data)
                        result.company_suppliers.extend(c1_suppliers)
                        stats.companies_fetched += 1
                        stats.company_supplier_relationships += len(c1_suppliers)
                except Exception as e:
                    logger.error(f"Failed to fetch C1 profile: {e}")
                    stats.errors.append(f"C1 profile: {str(e)[:100]}")
                
                # 3. Fetch OEM profiles (competitive intel)
                if include_oems:
                    logger.info(f"Fetching {len(self.tracked_oems)} OEM profiles...")
                    oems_to_fetch = list(self.tracked_oems.values())
                    if max_oems:
                        oems_to_fetch = oems_to_fetch[:max_oems]
                    
                    for oem in oems_to_fetch:
                        # Check credit limit
                        if max_credits and self.client.credits_used_session >= max_credits:
                            logger.warning(f"Credit limit reached: {self.client.credits_used_session}")
                            break

                        try:
                            oem_data, oem_suppliers = await self._fetch_company(
                                oem.search_key, oem.name, snapshot_date
                            )
                            if oem_data:
                                oem_data.company_type = CompanyType.OEM
                                oem_data.industries = [oem.industry]
                                result.companies.append(oem_data)
                                result.company_suppliers.extend(oem_suppliers)
                                stats.companies_fetched += 1
                                stats.company_supplier_relationships += len(oem_suppliers)
                        except Exception as e:
                            logger.error(f"Failed to fetch OEM {oem.name}: {e}")
                            stats.errors.append(f"OEM {oem.name}: {str(e)[:100]}")
                
                # 4. Product market searches (quarterly)
                if include_products:
                    logger.info(f"Running {len(PRODUCT_SEARCHES)} product searches...")
                    for product in PRODUCT_SEARCHES:
                        try:
                            product_results = await self._fetch_product_market(
                                product, snapshot_date
                            )
                            result.product_market.extend(product_results)
                            stats.product_market_results += len(product_results)
                        except Exception as e:
                            logger.error(f"Failed product search '{product}': {e}")
                            stats.errors.append(f"Product {product}: {str(e)[:100]}")
                
                # Update credit tracking
                stats.credits_used = self.client.credits_used_session
                stats.credits_remaining = self.client.credits_remaining
        
        except Exception as e:
            logger.error(f"Collection run failed: {e}")
            stats.errors.append(f"Collection failed: {str(e)[:200]}")
        
        finally:
            stats.completed_at = datetime.utcnow()
        
        logger.info(
            f"Collection complete: {stats.suppliers_fetched} suppliers, "
            f"{stats.companies_fetched} companies, "
            f"{stats.supplier_customer_relationships} relationships, "
            f"{stats.credits_used} credits used"
        )
        
        return result
    
    async def _fetch_supplier(
        self,
        supplier: TrackedSupplier,
        snapshot_date: date,
    ) -> Tuple[Optional[SupplierProfile], List[SupplierCustomerRelationship]]:
        """
        Fetch a supplier profile and extract customer relationships.
        
        Returns:
            Tuple of (SupplierProfile, list of relationships)
        """
        response = await self.client.get_supplier(supplier.search_key)
        
        if not response.success:
            logger.warning(f"Failed to fetch supplier {supplier.name}: {response.error}")
            return None, []
        
        data = response.data
        if not data:
            return None, []
        
        # Create supplier profile
        profile = SupplierProfile.from_api_response(data, snapshot_date)
        
        # Set tracked flags
        profile.is_c1_supplier = supplier.company_id.startswith('c1_') or any(
            'composites one' in normalize_name(c.get('company_name', ''))
            for c in data.get('companies_table', [])
        )
        profile.is_tracked_competitor = True  # All tracked suppliers are competitors
        profile.is_tracked_competitor = True  # All tracked suppliers are competitors
        try:
            profile.supplier_tier = SupplierTier(supplier.tier) if supplier.tier else None
        except ValueError:
            logger.warning(f"Invalid supplier tier '{supplier.tier}' for {supplier.name}")
            profile.supplier_tier = None
        
        # Extract customer relationships
        relationships = []
        for customer_row in data.get('companies_table', []):
            rel = SupplierCustomerRelationship.from_supplier_companies_table(
                supplier_data=data,
                customer_row=customer_row,
                snapshot_date=snapshot_date,
            )
            relationships.append(rel)
        
        return profile, relationships
    
    async def _fetch_company(
        self,
        company_key: str,
        company_name: str,
        snapshot_date: date,
    ) -> Tuple[Optional[CompanyProfile], List[CompanySupplierRelationship]]:
        """
        Fetch a company profile and extract supplier relationships.
        
        Returns:
            Tuple of (CompanyProfile, list of relationships)
        """
        response = await self.client.get_company(company_key)
        
        if not response.success:
            logger.warning(f"Failed to fetch company {company_name}: {response.error}")
            return None, []
        
        data = response.data
        if not data:
            return None, []
        
        # Create company profile
        profile = CompanyProfile.from_api_response(data, snapshot_date)
        
        # Extract supplier relationships
        relationships = []
        for supplier_row in data.get('suppliers_table', []):
            rel = CompanySupplierRelationship.from_company_suppliers_table(
                company_data=data,
                supplier_row=supplier_row,
                snapshot_date=snapshot_date,
            )
            relationships.append(rel)
        
        return profile, relationships
    
    async def _fetch_product_market(
        self,
        product: str,
        snapshot_date: date,
    ) -> List[ProductMarketResult]:
        """
        Fetch product market data (suppliers and companies for a product).
        
        Returns:
            List of ProductMarketResult
        """
        results = []
        
        # Fetch suppliers for this product
        supplier_response = await self.client.get_product_suppliers(product)
        if supplier_response.success and supplier_response.data:
            for item in supplier_response.data.get('results', []):
                results.append(ProductMarketResult(
                    record_id="",  # Will be auto-generated
                    snapshot_date=snapshot_date,
                    product_search_term=product,
                    result_type='supplier',
                    entity_name=item.get('name', ''),
                    entity_link=item.get('link'),
                    entity_country=item.get('country'),
                    entity_country_code=item.get('country_code'),
                    matching_shipments=item.get('matching_shipments'),
                    specialization_pct=item.get('specialization_pct'),
                    total_shipments=item.get('total_shipments'),
                    experience_years=item.get('experience_years'),
                    total_weight_kg=item.get('total_weight'),
                    related_entities=item.get('customers', [])[:10],
                    total_related_count=item.get('total_customers'),
                ))
        
        # Fetch companies for this product
        company_response = await self.client.get_product_companies(product)
        if company_response.success and company_response.data:
            for item in company_response.data.get('results', []):
                results.append(ProductMarketResult(
                    record_id="",
                    snapshot_date=snapshot_date,
                    product_search_term=product,
                    result_type='company',
                    entity_name=item.get('name', ''),
                    entity_link=item.get('link'),
                    entity_country=item.get('country', 'United States'),
                    entity_country_code=item.get('country_code', 'US'),
                    entity_address=item.get('address'),
                    matching_shipments=item.get('matching_shipments'),
                    specialization_pct=item.get('specialization_pct'),
                    total_shipments=item.get('total_shipments'),
                    total_weight_kg=item.get('total_weight'),
                    related_entities=item.get('suppliers', [])[:10],
                    total_related_count=item.get('total_suppliers'),
                ))
        
        return results
    
    # =========================================================================
    # Change Detection
    # =========================================================================
    
    def detect_changes(
        self,
        current_relationships: List[SupplierCustomerRelationship],
        previous_relationships: List[SupplierCustomerRelationship],
        volume_threshold_pct: float = 0.25,
    ) -> List[ChangeEvent]:
        """
        Detect changes between two snapshots.
        
        Args:
            current_relationships: Current snapshot relationships
            previous_relationships: Previous snapshot relationships
            volume_threshold_pct: Threshold for volume change alerts (0.25 = 25%)
            
        Returns:
            List of detected ChangeEvent
        """
        events = []
        detected_date = datetime.utcnow()
        
        # Group by supplier
        current_by_supplier: Dict[str, Dict[str, SupplierCustomerRelationship]] = {}
        previous_by_supplier: Dict[str, Dict[str, SupplierCustomerRelationship]] = {}
        
        for rel in current_relationships:
            if rel.supplier_id not in current_by_supplier:
                current_by_supplier[rel.supplier_id] = {}
            current_by_supplier[rel.supplier_id][rel.customer_name_normalized] = rel
        
        for rel in previous_relationships:
            if rel.supplier_id not in previous_by_supplier:
                previous_by_supplier[rel.supplier_id] = {}
            previous_by_supplier[rel.supplier_id][rel.customer_name_normalized] = rel
        
        # Detect changes for each supplier
        all_suppliers = set(current_by_supplier.keys()) | set(previous_by_supplier.keys())
        
        for supplier_id in all_suppliers:
            current_customers = current_by_supplier.get(supplier_id, {})
            previous_customers = previous_by_supplier.get(supplier_id, {})
            
            current_set = set(current_customers.keys())
            previous_set = set(previous_customers.keys())
            
            # Get supplier name from any relationship
            supplier_name = ""
            if current_customers:
                supplier_name = list(current_customers.values())[0].supplier_name
            elif previous_customers:
                supplier_name = list(previous_customers.values())[0].supplier_name
            
            # New customers
            for customer_norm in (current_set - previous_set):
                rel = current_customers[customer_norm]
                shipments = rel.total_shipments_to_customer or 0
                
                events.append(ChangeEvent(
                    event_id="",
                    detected_date=detected_date,
                    event_type=ChangeEventType.NEW_CUSTOMER,
                    event_category='customer_change',
                    primary_entity_type='supplier',
                    primary_entity_id=supplier_id,
                    primary_entity_name=supplier_name,
                    secondary_entity_name=rel.customer_name,
                    new_value=float(shipments),
                    summary=f"{supplier_name} added new customer: {rel.customer_name} ({shipments} shipments)",
                    significance=Significance.HIGH if shipments > 20 else Significance.MEDIUM,
                ))
            
            # Lost customers
            for customer_norm in (previous_set - current_set):
                rel = previous_customers[customer_norm]
                shipments = rel.total_shipments_to_customer or 0
                
                events.append(ChangeEvent(
                    event_id="",
                    detected_date=detected_date,
                    event_type=ChangeEventType.LOST_CUSTOMER,
                    event_category='customer_change',
                    primary_entity_type='supplier',
                    primary_entity_id=supplier_id,
                    primary_entity_name=supplier_name,
                    secondary_entity_name=rel.customer_name,
                    previous_value=float(shipments),
                    summary=f"{supplier_name} lost customer: {rel.customer_name}",
                    significance=Significance.HIGH if shipments > 20 else Significance.MEDIUM,
                ))
            
            # Volume changes for existing customers
            for customer_norm in (current_set & previous_set):
                current_rel = current_customers[customer_norm]
                previous_rel = previous_customers[customer_norm]
                
                prev_shipments = previous_rel.shipments_12m or 0
                curr_shipments = current_rel.shipments_12m or 0
                
                if prev_shipments > 0:
                    change_pct = (curr_shipments - prev_shipments) / prev_shipments
                    
                    if abs(change_pct) >= volume_threshold_pct:
                        direction = 'increase' if change_pct > 0 else 'decrease'
                        event_type = (
                            ChangeEventType.VOLUME_INCREASE if change_pct > 0
                            else ChangeEventType.VOLUME_DECREASE
                        )
                        
                        events.append(ChangeEvent(
                            event_id="",
                            detected_date=detected_date,
                            event_type=event_type,
                            event_category='volume_change',
                            primary_entity_type='supplier',
                            primary_entity_id=supplier_id,
                            primary_entity_name=supplier_name,
                            secondary_entity_name=current_rel.customer_name,
                            previous_value=float(prev_shipments),
                            new_value=float(curr_shipments),
                            change_pct=change_pct * 100,
                            summary=(
                                f"{supplier_name} → {current_rel.customer_name}: "
                                f"{direction} {abs(change_pct)*100:.0f}% "
                                f"({prev_shipments} → {curr_shipments} shipments/12m)"
                            ),
                            significance=Significance.HIGH if abs(change_pct) > 0.5 else Significance.MEDIUM,
                        ))
        
        logger.info(f"Detected {len(events)} change events")
        return events
    
    # =========================================================================
    # Competitive Intelligence
    # =========================================================================
    
    def find_competitor_overlap(
        self,
        c1_suppliers: List[CompanySupplierRelationship],
        supplier_customers: List[SupplierCustomerRelationship],
    ) -> List[Dict[str, Any]]:
        """
        Find where C1's suppliers also ship to other companies.
        
        Args:
            c1_suppliers: C1's supplier relationships
            supplier_customers: All supplier → customer relationships
            
        Returns:
            List of overlap records
        """
        overlaps = []
        
        # Get C1's supplier names (normalized)
        c1_supplier_names = {
            normalize_name(rel.supplier_name) for rel in c1_suppliers
        }
        
        # Group supplier customers by supplier
        by_supplier: Dict[str, List[SupplierCustomerRelationship]] = {}
        for rel in supplier_customers:
            supplier_norm = normalize_name(rel.supplier_name)
            if supplier_norm not in by_supplier:
                by_supplier[supplier_norm] = []
            by_supplier[supplier_norm].append(rel)
        
        # Find overlaps
        for supplier_norm in c1_supplier_names:
            if supplier_norm not in by_supplier:
                continue
            
            relationships = by_supplier[supplier_norm]
            
            # Find C1's shipments from this supplier
            c1_shipments = 0
            for rel in c1_suppliers:
                if normalize_name(rel.supplier_name) == supplier_norm:
                    c1_shipments = rel.total_shipments_from_supplier or 0
                    break
            
            # Find other customers
            for rel in relationships:
                customer_norm = normalize_name(rel.customer_name)
                if 'composites one' in customer_norm:
                    continue  # Skip C1 itself
                
                other_shipments = rel.total_shipments_to_customer or 0
                
                overlaps.append({
                    'supplier_name': rel.supplier_name,
                    'supplier_country': rel.supplier_country,
                    'shipments_to_c1': c1_shipments,
                    'other_customer_name': rel.customer_name,
                    'shipments_to_other': other_shipments,
                    'c1_vs_other_ratio': c1_shipments / other_shipments if other_shipments > 0 else None,
                    'hs_codes': [hs.chapter for hs in rel.hs_code_chapters],
                })
        
        return overlaps
