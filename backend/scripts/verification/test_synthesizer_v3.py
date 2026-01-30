import asyncio
import sys
import os
from pathlib import Path
import json

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.agents.research.synthesizer import synthesis_node
from app.agents.research.state import BlockType

from types import SimpleNamespace

async def test_synthesis():
    print("Testing Synthesizer V3...")
    
from types import SimpleNamespace

class DictToObject:
    def __init__(self, dictionary):
        for key, value in dictionary.items():
            if isinstance(value, dict):
                setattr(self, key, DictToObject(value))
            elif isinstance(value, list):
                setattr(self, key, [DictToObject(item) if isinstance(item, dict) else item for item in value])
            else:
                setattr(self, key, value)

async def test_synthesis():
    print("Testing Synthesizer V3...")
    
    brief_data = {
         "clarified_intent": "Analyze financial outlook and market position",
         "entities_to_track": ["Hexcel"],
         "timeframe": "2025",
         "domain_context": "Aerospace"
    }

    fin_data = {
        "annual_reports": [],
        "quarterly_reports": [], 
        "metrics": [
            {"metric_name": "Revenue", "value": "$1.9B", "period": "FY 2024", "yoy_change": "+10%"},
            {"metric_name": "Gross Margin", "value": "24%", "period": "FY 2024", "yoy_change": "+120bps"}
        ],
        "key_findings": [
            {"finding": "Commercial aerospace demand is driving growth.", "source_url": "http://hexcel.com"},
            {"finding": "Supply chain constraints are easing.", "source_url": "http://bloomberg.com"}
        ],
        "quotes": [
            {"text": "We expect double digit growth in 2025.", "speaker": "CEO", "context": "Q4 Call", "sentiment": "positive"}
        ]
    }
    
    ind_data = {
        "market_trends": [{"trend": "Widebody aircraft ramp up", "impact": "Positive"}],
        "competitor_moves": []
    }
    
    vis_data = {
        "supporting_visuals": [
            {
                "visual_id": "vis_rev_chart_01",
                "image_url": "http://example.com/chart.png", 
                "caption": "Revenue Trajectory 2023-2025",
                "placement": "financial_section",
                "data_summary": "Shows consistent 10% CAGR",
                "size": "half_width"
            }
        ]
    }

    # Mock state (DeepResearchState is a TypedDict)
    state = {
        "user_query": "Outlook for Hexcel Corporation in 2025",
        "research_brief": DictToObject(brief_data),
        "financial_output": DictToObject(fin_data),
        "industry_output": DictToObject(ind_data),
        "visual_output": DictToObject(vis_data),
        "errors": []
    }
    
    # Run node
    try:
        print("Running synthesis_node... (this calls the LLM, so verify you have API keys)")
        result_state = await synthesis_node(state)
        report = result_state.get("final_report")
        
        if not report:
            print("FAILED: No report generated")
            if result_state.get("errors"):
                print("Errors:", result_state["errors"])
            return
            
        print(f"Report Generated: {report.report_id}")
        
        has_blocks = False
        for section in report.sections:
            print(f"\nSection: {section.section_title}")
            print(f"  Content (Legacy): {section.content[:50] if section.content else 'None'}")
            if section.blocks:
                has_blocks = True
                print(f"  Blocks ({len(section.blocks)}):")
                for block in section.blocks:
                    print(f"    - [{block.block_type}] {block.block_id}")
                    if block.block_type == "visual_split":
                        print(f"      Visual ID: {block.data.get('visual_id')}")
                    if block.block_type == "paragraph":
                         print(f"      Text: {block.data.get('text')[:40]}...")
            else:
                print("  NO BLOCKS")
                
        # Verification Logic
        if has_blocks:
            print("\n✅ SUCCESS: Report contains V3 Blocks!")
        else:
            print("\n⚠️ WARNING: Report generated but no blocks found.")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_synthesis())
