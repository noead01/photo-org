"""
Domain model for facets - treating facets as first-class entities.

This represents a more sophisticated architecture where facets are 
reified domain concepts with their own behaviors and responsibilities.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class FacetType(Enum):
    """Types of facets supported by the system."""
    DATE_HIERARCHY = "date_hierarchy"
    SIMPLE_COUNT = "simple_count"
    NESTED_COUNT = "nested_count"
    DUPLICATE_STATS = "duplicate_stats"


@dataclass
class FacetValue:
    """A single facet value with its count and optional metadata."""
    value: Any
    count: int
    metadata: Optional[Dict[str, Any]] = None
    children: Optional[List['FacetValue']] = None


@dataclass
class FacetResult:
    """Result of computing a facet."""
    facet_name: str
    facet_type: FacetType
    values: List[FacetValue]
    total_count: int
    metadata: Optional[Dict[str, Any]] = None


class Facet(ABC):
    """Abstract base class for all facets."""
    
    def __init__(self, name: str, facet_type: FacetType):
        self.name = name
        self.facet_type = facet_type
    
    @abstractmethod
    def compute(self, filtered_photo_ids: List[str], context: 'FacetContext') -> FacetResult:
        """Compute the facet values for the given photo IDs."""
        pass
    
    @abstractmethod
    def supports_drill_sideways(self) -> bool:
        """Whether this facet supports drill-sideways filtering."""
        pass
    
    def get_cache_key(self, filtered_photo_ids: List[str]) -> str:
        """Generate cache key for this facet computation."""
        ids_hash = hash(tuple(sorted(filtered_photo_ids)))
        return f"{self.name}:{ids_hash}"


class DateHierarchyFacet(Facet):
    """Facet for date hierarchies (year -> month -> day)."""
    
    def __init__(self):
        super().__init__("date", FacetType.DATE_HIERARCHY)
    
    def compute(self, filtered_photo_ids: List[str], context: 'FacetContext') -> FacetResult:
        """Compute date hierarchy facet."""
        # This would use the context to get data
        # For now, return empty result as this is just architectural demo
        return FacetResult(
            facet_name=self.name,
            facet_type=self.facet_type,
            values=[],
            total_count=len(filtered_photo_ids)
        )
    
    def supports_drill_sideways(self) -> bool:
        return True


class SimpleCountFacet(Facet):
    """Base class for simple count-based facets (tags, people, etc.)."""
    
    def __init__(self, name: str, table_name: str, value_column: str, photo_id_column: str = "photo_id"):
        super().__init__(name, FacetType.SIMPLE_COUNT)
        self.table_name = table_name
        self.value_column = value_column
        self.photo_id_column = photo_id_column
    
    def compute(self, filtered_photo_ids: List[str], context: 'FacetContext') -> FacetResult:
        """Compute simple count facet."""
        from sqlalchemy import select, func
        
        # Get the table from context
        table = getattr(context, self.table_name)
        
        # Build query to count occurrences
        query = select(
            table.c[self.value_column],
            func.count(func.distinct(table.c[self.photo_id_column]))
        ).where(
            table.c[self.photo_id_column].in_(filtered_photo_ids)
        ).group_by(
            table.c[self.value_column]
        )
        
        rows = context.db.execute(query).all()
        
        values = [
            FacetValue(value=value, count=int(count))
            for value, count in rows
            if value is not None
        ]
        
        # Sort by count descending
        values.sort(key=lambda v: v.count, reverse=True)
        
        return FacetResult(
            facet_name=self.name,
            facet_type=self.facet_type,
            values=values,
            total_count=sum(v.count for v in values)
        )
    
    def supports_drill_sideways(self) -> bool:
        return True


class TagsFacet(SimpleCountFacet):
    """Facet for photo tags."""
    
    def __init__(self):
        super().__init__("tags", "photo_tags", "tag")


class PeopleFacet(SimpleCountFacet):
    """Facet for people in photos."""
    
    def __init__(self):
        super().__init__("people", "faces", "person_id")


class DuplicatesFacet(Facet):
    """Facet for duplicate photo statistics."""
    
    def __init__(self):
        super().__init__("duplicates", FacetType.DUPLICATE_STATS)
    
    def compute(self, filtered_photo_ids: List[str], context: 'FacetContext') -> FacetResult:
        """Compute duplicate statistics."""
        # This would use the context to get data
        # For now, return empty result as this is just architectural demo
        return FacetResult(
            facet_name=self.name,
            facet_type=self.facet_type,
            values=[],
            total_count=len(filtered_photo_ids)
        )
    
    def supports_drill_sideways(self) -> bool:
        return False


@dataclass
class FacetContext:
    """Context object providing dependencies for facet computation."""
    db: Any  # Database session
    photo_tags: Any  # photo_tags table
    faces: Any  # faces table  
    photos: Any  # photos table
    queries: Optional[Any] = None  # Query builder object
    cache: Optional[Any] = None  # Optional cache
    filters: Optional[Dict[str, Any]] = None  # Current filters for drill-sideways


class FacetRegistry:
    """Registry and coordinator for all facets."""
    
    def __init__(self):
        self._facets: Dict[str, Facet] = {}
        self._register_default_facets()
    
    def _register_default_facets(self):
        """Register the default facets."""
        self.register(DateHierarchyFacet())
        self.register(TagsFacet())
        self.register(PeopleFacet())
        self.register(DuplicatesFacet())
    
    def register(self, facet: Facet):
        """Register a facet."""
        self._facets[facet.name] = facet
    
    def get_facet(self, name: str) -> Optional[Facet]:
        """Get a facet by name."""
        return self._facets.get(name)
    
    def get_all_facets(self) -> List[Facet]:
        """Get all registered facets."""
        return list(self._facets.values())
    
    def compute_all_facets(self, filtered_photo_ids: List[str], context: FacetContext) -> Dict[str, Any]:
        """Compute all facets and return in the expected format."""
        results = {}
        
        for facet in self._facets.values():
            try:
                facet_result = facet.compute(filtered_photo_ids, context)
                results[facet.name] = self._format_facet_result(facet_result)
            except Exception as e:
                # Log error and continue with other facets
                print(f"Error computing facet {facet.name}: {e}")
                results[facet.name] = self._get_empty_facet_result(facet)
        
        return results
    
    def _format_facet_result(self, result: FacetResult) -> Any:
        """Format facet result for API response."""
        if result.facet_type == FacetType.DATE_HIERARCHY:
            return {"years": []}  # Simplified for demo
        elif result.facet_type == FacetType.SIMPLE_COUNT:
            # Format as dictionary for tags/people facets
            return {v.value: v.count for v in result.values}
        elif result.facet_type == FacetType.DUPLICATE_STATS:
            return {v.value: v.count for v in result.values}
        else:
            return [{"value": v.value, "count": v.count} for v in result.values]
    
    def _get_empty_facet_result(self, facet: Facet) -> Any:
        """Get empty result for a facet."""
        if facet.facet_type == FacetType.DATE_HIERARCHY:
            return {"years": []}
        elif facet.facet_type == FacetType.DUPLICATE_STATS:
            return {"exact": 0, "near": 0}
        else:
            return {}


# Global registry instance
facet_registry = FacetRegistry()