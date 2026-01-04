"""Data visualization tools."""

from typing import Optional, List, Dict, Any
import json
from langchain_core.tools import tool

from app.utils.logger import get_logger

logger = get_logger(__name__)


@tool
def create_chart(
    chart_type: str,
    title: str,
    labels: List[str],
    datasets: List[Dict[str, Any]],
    x_axis_label: Optional[str] = None,
    y_axis_label: Optional[str] = None,
) -> str:
    """
    Create a chart specification for visualization.
    
    Use this to generate charts for financial data, trends, comparisons.
    The chart specification will be rendered by the frontend.
    
    Args:
        chart_type: Type of chart - "bar", "line", "pie", "doughnut", "scatter"
        title: Chart title
        labels: List of labels for x-axis or pie slices
        datasets: List of dataset objects, each with:
            - label: Dataset name
            - data: List of numeric values
            - backgroundColor: Optional color or list of colors
            - borderColor: Optional border color
        x_axis_label: Optional label for x-axis
        y_axis_label: Optional label for y-axis
    
    Returns:
        JSON string with Chart.js compatible specification
    
    Example:
        create_chart(
            chart_type="bar",
            title="Revenue Comparison",
            labels=["Q1", "Q2", "Q3", "Q4"],
            datasets=[
                {"label": "Hexcel", "data": [100, 120, 130, 125]},
                {"label": "Toray", "data": [90, 110, 120, 115]}
            ],
            y_axis_label="Revenue ($M)"
        )
    """
    logger.info(f"Creating {chart_type} chart: {title}")
    
    valid_types = ["bar", "line", "pie", "doughnut", "scatter"]
    if chart_type not in valid_types:
        return json.dumps({
            "error": f"Invalid chart type. Must be one of: {valid_types}"
        })
    
    # Default colors
    default_colors = [
        "#7d4199",  # C1 Purple
        "#0f4c8b",  # C1 Navy
        "#3b82f6",  # Blue
        "#10b981",  # Green
        "#f97316",  # Orange
        "#ef4444",  # Red
        "#8b5cf6",  # Violet
        "#06b6d4",  # Cyan
    ]
    
    # Process datasets
    processed_datasets = []
    for i, dataset in enumerate(datasets):
        processed = {
            "label": dataset.get("label", f"Dataset {i+1}"),
            "data": dataset.get("data", []),
        }
        
        # Add colors
        if chart_type in ["pie", "doughnut"]:
            processed["backgroundColor"] = dataset.get(
                "backgroundColor", 
                default_colors[:len(dataset.get("data", []))]
            )
        else:
            color = dataset.get("backgroundColor", default_colors[i % len(default_colors)])
            processed["backgroundColor"] = color
            processed["borderColor"] = dataset.get("borderColor", color)
        
        processed_datasets.append(processed)
    
    # Build chart specification
    chart_spec = {
        "type": chart_type,
        "data": {
            "labels": labels,
            "datasets": processed_datasets,
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": title,
                },
                "legend": {
                    "display": len(processed_datasets) > 1,
                },
            },
        },
    }
    
    # Add axis labels if provided
    if chart_type in ["bar", "line", "scatter"]:
        chart_spec["options"]["scales"] = {
            "x": {
                "title": {
                    "display": bool(x_axis_label),
                    "text": x_axis_label or "",
                }
            },
            "y": {
                "title": {
                    "display": bool(y_axis_label),
                    "text": y_axis_label or "",
                }
            },
        }
    
    return json.dumps({
        "chart": chart_spec,
        "message": f"Created {chart_type} chart: {title}",
    }, indent=2)
