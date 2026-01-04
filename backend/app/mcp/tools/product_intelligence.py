"""Product Intelligence tools - Product catalog and competitive intelligence.

These tools provide product information, competitive analysis, and catalog management
for the composites industry. Available to Product Maven and Industry Watcher agents.
"""

import json
from typing import Optional, List
from langchain_core.tools import tool

from app.utils.grounding import load_companies, load_materials, load_industries
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Comprehensive Product Catalog - Composites Industry
# 75+ products from major suppliers with realistic spec data
PRODUCT_CATALOG = [
    # ==========================================================================
    # CARBON FIBERS
    # ==========================================================================
    
    # --- Hexcel Carbon Fibers ---
    {
        "id": "HXL-AS4",
        "supplier": "Hexcel",
        "name": "AS4 Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "standard_modulus",
        "industries": ["aerospace", "defense"],
        "specs": {
            "tensile_strength": "4,433 MPa",
            "tensile_modulus": "231 GPa",
            "elongation": "1.8%",
            "density": "1.79 g/cm³",
            "filament_count": "3K, 6K, 12K",
        },
        "description": "Industry standard aerospace carbon fiber with excellent strength and handleability.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-AS4C",
        "supplier": "Hexcel",
        "name": "AS4C Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "standard_modulus",
        "industries": ["aerospace", "defense", "sporting_goods"],
        "specs": {
            "tensile_strength": "4,620 MPa",
            "tensile_modulus": "231 GPa",
            "elongation": "1.8%",
            "density": "1.78 g/cm³",
            "filament_count": "3K, 6K, 12K",
        },
        "description": "Enhanced version of AS4 with higher strength for demanding applications.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-IM7",
        "supplier": "Hexcel",
        "name": "IM7 Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "intermediate_modulus",
        "industries": ["aerospace", "defense", "sporting_goods"],
        "specs": {
            "tensile_strength": "5,310 MPa",
            "tensile_modulus": "276 GPa",
            "elongation": "1.8%",
            "density": "1.78 g/cm³",
            "filament_count": "6K, 12K",
        },
        "description": "Premium intermediate modulus fiber for primary aerospace structures.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-IM10",
        "supplier": "Hexcel",
        "name": "IM10 Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "intermediate_modulus",
        "industries": ["aerospace", "defense"],
        "specs": {
            "tensile_strength": "6,826 MPa",
            "tensile_modulus": "303 GPa",
            "elongation": "2.0%",
            "density": "1.79 g/cm³",
            "filament_count": "12K",
        },
        "description": "Next-generation intermediate modulus fiber with exceptional strength.",
        "in_c1_catalog": False,
    },
    {
        "id": "HXL-HM63",
        "supplier": "Hexcel",
        "name": "HM63 Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "high_modulus",
        "industries": ["aerospace", "defense", "space"],
        "specs": {
            "tensile_strength": "4,688 MPa",
            "tensile_modulus": "441 GPa",
            "elongation": "1.1%",
            "density": "1.93 g/cm³",
        },
        "description": "Ultra-high modulus fiber for space and satellite applications.",
        "in_c1_catalog": False,
    },
    
    # --- Toray Carbon Fibers ---
    {
        "id": "TOR-T300",
        "supplier": "Toray",
        "name": "T300 Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "standard_modulus",
        "industries": ["aerospace", "sporting_goods", "industrial"],
        "specs": {
            "tensile_strength": "3,530 MPa",
            "tensile_modulus": "230 GPa",
            "elongation": "1.5%",
            "density": "1.76 g/cm³",
            "filament_count": "1K, 3K, 6K, 12K",
        },
        "description": "World's most widely used standard modulus carbon fiber.",
        "in_c1_catalog": True,
    },
    {
        "id": "TOR-T700S",
        "supplier": "Toray",
        "name": "T700S Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "standard_modulus",
        "industries": ["aerospace", "automotive", "wind_energy"],
        "specs": {
            "tensile_strength": "4,900 MPa",
            "tensile_modulus": "230 GPa",
            "elongation": "2.1%",
            "density": "1.80 g/cm³",
            "filament_count": "12K, 24K",
        },
        "description": "High-strength standard modulus fiber for wind energy and automotive.",
        "in_c1_catalog": True,
    },
    {
        "id": "TOR-T700G",
        "supplier": "Toray",
        "name": "T700G Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "standard_modulus",
        "industries": ["wind_energy", "automotive", "pressure_vessels"],
        "specs": {
            "tensile_strength": "4,900 MPa",
            "tensile_modulus": "240 GPa",
            "elongation": "2.0%",
            "density": "1.80 g/cm³",
            "filament_count": "12K, 24K",
        },
        "description": "Optimized variant of T700S for industrial applications.",
        "in_c1_catalog": True,
    },
    {
        "id": "TOR-T800S",
        "supplier": "Toray",
        "name": "T800S Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "intermediate_modulus",
        "industries": ["aerospace", "defense"],
        "specs": {
            "tensile_strength": "5,880 MPa",
            "tensile_modulus": "294 GPa",
            "elongation": "2.0%",
            "density": "1.81 g/cm³",
            "filament_count": "12K",
        },
        "description": "Primary structure fiber for Boeing 787 and Airbus A350.",
        "in_c1_catalog": True,
    },
    {
        "id": "TOR-T800H",
        "supplier": "Toray",
        "name": "T800H Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "intermediate_modulus",
        "industries": ["aerospace", "defense", "sporting_goods"],
        "specs": {
            "tensile_strength": "5,490 MPa",
            "tensile_modulus": "294 GPa",
            "elongation": "1.9%",
            "density": "1.81 g/cm³",
            "filament_count": "6K, 12K",
        },
        "description": "High-performance intermediate modulus fiber with balanced properties.",
        "in_c1_catalog": True,
    },
    {
        "id": "TOR-T1000G",
        "supplier": "Toray",
        "name": "T1000G Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "intermediate_modulus",
        "industries": ["aerospace", "defense"],
        "specs": {
            "tensile_strength": "6,370 MPa",
            "tensile_modulus": "294 GPa",
            "elongation": "2.2%",
            "density": "1.80 g/cm³",
            "filament_count": "12K",
        },
        "description": "Ultra-high strength fiber for next-generation aircraft.",
        "in_c1_catalog": False,
    },
    {
        "id": "TOR-T1100G",
        "supplier": "Toray",
        "name": "T1100G Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "high_modulus",
        "industries": ["aerospace", "defense", "space"],
        "specs": {
            "tensile_strength": "6,600 MPa",
            "tensile_modulus": "324 GPa",
            "elongation": "2.0%",
            "density": "1.79 g/cm³",
            "filament_count": "12K",
        },
        "description": "Highest strength-to-weight ratio carbon fiber available.",
        "in_c1_catalog": False,
    },
    {
        "id": "TOR-M40J",
        "supplier": "Toray",
        "name": "M40J Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "high_modulus",
        "industries": ["aerospace", "space", "sporting_goods"],
        "specs": {
            "tensile_strength": "4,410 MPa",
            "tensile_modulus": "377 GPa",
            "elongation": "1.2%",
            "density": "1.77 g/cm³",
        },
        "description": "High modulus fiber for satellite structures and premium sporting goods.",
        "in_c1_catalog": False,
    },
    {
        "id": "TOR-M55J",
        "supplier": "Toray",
        "name": "M55J Carbon Fiber",
        "category": "carbon_fiber",
        "subcategory": "ultra_high_modulus",
        "industries": ["space", "defense"],
        "specs": {
            "tensile_strength": "4,020 MPa",
            "tensile_modulus": "540 GPa",
            "elongation": "0.8%",
            "density": "1.93 g/cm³",
        },
        "description": "Ultra-high modulus pitch-based fiber for space applications.",
        "in_c1_catalog": False,
    },
    
    # --- SGL Carbon Fibers ---
    {
        "id": "SGL-SIGRAFIL-C30",
        "supplier": "SGL Carbon",
        "name": "SIGRAFIL C30 T050 EPY",
        "category": "carbon_fiber",
        "subcategory": "standard_modulus",
        "industries": ["automotive", "industrial"],
        "specs": {
            "tensile_strength": "3,950 MPa",
            "tensile_modulus": "230 GPa",
            "elongation": "1.7%",
            "density": "1.79 g/cm³",
            "filament_count": "50K",
        },
        "description": "Cost-effective large tow carbon fiber for automotive applications.",
        "in_c1_catalog": True,
    },
    {
        "id": "SGL-SIGRAFIL-C50",
        "supplier": "SGL Carbon",
        "name": "SIGRAFIL C T50-4.4",
        "category": "carbon_fiber",
        "subcategory": "standard_modulus",
        "industries": ["automotive", "industrial", "wind_energy"],
        "specs": {
            "tensile_strength": "4,400 MPa",
            "tensile_modulus": "240 GPa",
            "elongation": "1.8%",
            "density": "1.79 g/cm³",
            "filament_count": "50K",
        },
        "description": "High-strength large tow fiber for structural automotive parts.",
        "in_c1_catalog": True,
    },
    
    # --- Mitsubishi Carbon Fibers ---
    {
        "id": "MIT-TR30S",
        "supplier": "Mitsubishi Chemical",
        "name": "PYROFIL TR30S",
        "category": "carbon_fiber",
        "subcategory": "standard_modulus",
        "industries": ["aerospace", "sporting_goods"],
        "specs": {
            "tensile_strength": "4,410 MPa",
            "tensile_modulus": "235 GPa",
            "elongation": "1.9%",
            "density": "1.79 g/cm³",
            "filament_count": "3K, 6K, 12K",
        },
        "description": "General-purpose aerospace-grade carbon fiber.",
        "in_c1_catalog": True,
    },
    {
        "id": "MIT-TR50S",
        "supplier": "Mitsubishi Chemical",
        "name": "PYROFIL TR50S",
        "category": "carbon_fiber",
        "subcategory": "intermediate_modulus",
        "industries": ["aerospace", "defense"],
        "specs": {
            "tensile_strength": "4,900 MPa",
            "tensile_modulus": "240 GPa",
            "elongation": "2.0%",
            "density": "1.82 g/cm³",
            "filament_count": "6K, 12K, 15K",
        },
        "description": "High-strength intermediate modulus fiber for aerospace.",
        "in_c1_catalog": False,
    },
    {
        "id": "MIT-MR40",
        "supplier": "Mitsubishi Chemical",
        "name": "PYROFIL MR40",
        "category": "carbon_fiber",
        "subcategory": "intermediate_modulus",
        "industries": ["aerospace", "sporting_goods"],
        "specs": {
            "tensile_strength": "4,410 MPa",
            "tensile_modulus": "295 GPa",
            "elongation": "1.5%",
            "density": "1.76 g/cm³",
        },
        "description": "Balanced strength and modulus for primary structures.",
        "in_c1_catalog": False,
    },
    
    # ==========================================================================
    # PREPREGS
    # ==========================================================================
    
    # --- Hexcel Prepregs ---
    {
        "id": "HXL-M21",
        "supplier": "Hexcel",
        "name": "HexPly M21",
        "category": "prepreg",
        "subcategory": "aerospace_structural",
        "industries": ["aerospace"],
        "specs": {
            "resin_type": "Toughened Epoxy",
            "cure_temp": "180°C",
            "tack": "Medium",
            "out_time": "30 days @ 23°C",
            "shelf_life": "12 months @ -18°C",
            "reinforcement": "UD, Fabric",
        },
        "description": "Primary structural prepreg for Airbus A350 and A400M.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-M21E",
        "supplier": "Hexcel",
        "name": "HexPly M21E",
        "category": "prepreg",
        "subcategory": "aerospace_structural",
        "industries": ["aerospace", "defense"],
        "specs": {
            "resin_type": "Enhanced Toughened Epoxy",
            "cure_temp": "180°C",
            "tack": "Medium-High",
            "out_time": "35 days @ 23°C",
            "shelf_life": "12 months @ -18°C",
        },
        "description": "Enhanced M21 with improved damage tolerance.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-8552",
        "supplier": "Hexcel",
        "name": "HexPly 8552",
        "category": "prepreg",
        "subcategory": "aerospace_structural",
        "industries": ["aerospace", "defense"],
        "specs": {
            "resin_type": "Amine-cured Toughened Epoxy",
            "cure_temp": "177°C",
            "tack": "High",
            "out_time": "21 days @ 23°C",
            "shelf_life": "12 months @ -18°C",
            "reinforcement": "UD, Fabric",
        },
        "description": "Industry workhorse for Boeing aircraft programs.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-913",
        "supplier": "Hexcel",
        "name": "HexPly 913",
        "category": "prepreg",
        "subcategory": "general_aerospace",
        "industries": ["aerospace", "sporting_goods"],
        "specs": {
            "resin_type": "Modified Epoxy",
            "cure_temp": "120°C or 175°C",
            "tack": "Low-Medium",
            "out_time": "14 days @ 23°C",
        },
        "description": "Versatile prepreg for secondary structures and sporting goods.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-M56",
        "supplier": "Hexcel",
        "name": "HexPly M56",
        "category": "prepreg",
        "subcategory": "out_of_autoclave",
        "industries": ["aerospace", "automotive"],
        "specs": {
            "resin_type": "OOA Epoxy",
            "cure_temp": "180°C",
            "process": "Vacuum Bag Only",
            "void_content": "<1%",
        },
        "description": "Out-of-autoclave prepreg with autoclave-quality results.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-M77",
        "supplier": "Hexcel",
        "name": "HexPly M77",
        "category": "prepreg",
        "subcategory": "fast_cure",
        "industries": ["automotive", "industrial"],
        "specs": {
            "resin_type": "Fast-cure Epoxy",
            "cure_temp": "150°C",
            "cure_time": "3 minutes",
            "process": "Compression molding",
        },
        "description": "Rapid-cure prepreg for high-volume automotive production.",
        "in_c1_catalog": True,
    },
    
    # --- Toray Prepregs ---
    {
        "id": "TOR-2510",
        "supplier": "Toray",
        "name": "Torayca 2510",
        "category": "prepreg",
        "subcategory": "general_purpose",
        "industries": ["aerospace", "sporting_goods", "industrial"],
        "specs": {
            "resin_type": "Standard Epoxy",
            "cure_temp": "120°C or 135°C",
            "tack": "Medium",
            "shelf_life": "6 months @ -18°C",
        },
        "description": "Cost-effective general-purpose prepreg system.",
        "in_c1_catalog": True,
    },
    {
        "id": "TOR-3900",
        "supplier": "Toray",
        "name": "Torayca 3900 Series",
        "category": "prepreg",
        "subcategory": "aerospace_structural",
        "industries": ["aerospace"],
        "specs": {
            "resin_type": "Toughened Epoxy",
            "cure_temp": "180°C",
            "tack": "Medium-High",
            "out_time": "21 days @ 23°C",
            "reinforcement": "UD",
        },
        "description": "Primary structure prepreg for Boeing 787 fuselage.",
        "in_c1_catalog": True,
    },
    {
        "id": "TOR-3911",
        "supplier": "Toray",
        "name": "Torayca 3911",
        "category": "prepreg",
        "subcategory": "aerospace_structural",
        "industries": ["aerospace", "defense"],
        "specs": {
            "resin_type": "Next-gen Toughened Epoxy",
            "cure_temp": "180°C",
            "damage_tolerance": "Enhanced",
            "cai": ">275 MPa",
        },
        "description": "Advanced prepreg with superior damage tolerance.",
        "in_c1_catalog": False,
    },
    {
        "id": "TOR-F655",
        "supplier": "Toray",
        "name": "Torayca F655",
        "category": "prepreg",
        "subcategory": "thermoplastic_toughened",
        "industries": ["aerospace"],
        "specs": {
            "resin_type": "Thermoplastic-toughened Epoxy",
            "cure_temp": "180°C",
            "gic": "High",
            "hot_wet_performance": "Excellent",
        },
        "description": "Premium prepreg for demanding aerospace applications.",
        "in_c1_catalog": False,
    },
    
    # --- Gurit Prepregs ---
    {
        "id": "GUR-SE84LV",
        "supplier": "Gurit",
        "name": "SE 84LV",
        "category": "prepreg",
        "subcategory": "marine_wind",
        "industries": ["marine", "wind_energy"],
        "specs": {
            "resin_type": "Low Temperature Cure Epoxy",
            "cure_temp": "80°C",
            "process": "Vacuum bag cure",
            "out_time": "20 days @ 20°C",
        },
        "description": "Industry standard for marine and wind energy structures.",
        "in_c1_catalog": True,
    },
    {
        "id": "GUR-SPRINT",
        "supplier": "Gurit",
        "name": "SPRINT ST94",
        "category": "prepreg",
        "subcategory": "marine_wind",
        "industries": ["marine", "wind_energy", "industrial"],
        "specs": {
            "resin_type": "Film Infusion Epoxy",
            "cure_temp": "80°C",
            "process": "Vacuum infusion",
            "thickness_per_ply": "0.6mm typical",
        },
        "description": "Rapid infusion prepreg for large structures.",
        "in_c1_catalog": True,
    },
    {
        "id": "GUR-WE91-2",
        "supplier": "Gurit",
        "name": "WE91-2",
        "category": "prepreg",
        "subcategory": "wind_energy",
        "industries": ["wind_energy"],
        "specs": {
            "resin_type": "Wind Energy Epoxy",
            "cure_temp": "80°C",
            "spar_cap": "Yes",
            "fatigue_performance": "Excellent",
        },
        "description": "Specialized prepreg for wind turbine spar caps.",
        "in_c1_catalog": False,
    },
    
    # ==========================================================================
    # GLASS FIBERS
    # ==========================================================================
    
    # --- Owens Corning Glass Fibers ---
    {
        "id": "OC-SE1500",
        "supplier": "Owens Corning",
        "name": "SE1500 E-Glass Roving",
        "category": "glass_fiber",
        "subcategory": "e_glass",
        "industries": ["wind_energy", "marine", "construction"],
        "specs": {
            "tensile_strength": "3,445 MPa",
            "tensile_modulus": "72 GPa",
            "density": "2.54 g/cm³",
            "tex": "2400",
        },
        "description": "Standard E-glass roving for wind energy and marine.",
        "in_c1_catalog": True,
    },
    {
        "id": "OC-SE1200",
        "supplier": "Owens Corning",
        "name": "SE1200 E-Glass Roving",
        "category": "glass_fiber",
        "subcategory": "e_glass",
        "industries": ["wind_energy", "industrial"],
        "specs": {
            "tensile_strength": "3,400 MPa",
            "tensile_modulus": "72 GPa",
            "tex": "1200",
        },
        "description": "Medium-tex roving for pultrusion and filament winding.",
        "in_c1_catalog": True,
    },
    {
        "id": "OC-ADVANTEX",
        "supplier": "Owens Corning",
        "name": "Advantex ECR Glass",
        "category": "glass_fiber",
        "subcategory": "ecr_glass",
        "industries": ["wind_energy", "infrastructure", "chemical"],
        "specs": {
            "tensile_strength": "3,100 MPa",
            "tensile_modulus": "81 GPa",
            "corrosion_resistance": "Excellent",
            "acid_resistance": "Superior to E-glass",
        },
        "description": "Boron-free corrosion-resistant glass for demanding environments.",
        "in_c1_catalog": True,
    },
    {
        "id": "OC-WINDSTRAND",
        "supplier": "Owens Corning",
        "name": "WindStrand H-Glass",
        "category": "glass_fiber",
        "subcategory": "high_performance_glass",
        "industries": ["wind_energy"],
        "specs": {
            "tensile_strength": "3,800 MPa",
            "tensile_modulus": "89 GPa",
            "fatigue_resistance": "Enhanced",
        },
        "description": "High-modulus glass fiber designed specifically for wind turbine blades.",
        "in_c1_catalog": True,
    },
    
    # --- AGY Glass Fibers ---
    {
        "id": "AGY-S2",
        "supplier": "AGY",
        "name": "S-2 Glass Fiber",
        "category": "glass_fiber",
        "subcategory": "s_glass",
        "industries": ["aerospace", "defense", "armor"],
        "specs": {
            "tensile_strength": "4,890 MPa",
            "tensile_modulus": "87 GPa",
            "density": "2.46 g/cm³",
            "temperature_capability": "Higher than E-glass",
        },
        "description": "Premium high-strength glass for ballistic and aerospace applications.",
        "in_c1_catalog": True,
    },
    {
        "id": "AGY-933",
        "supplier": "AGY",
        "name": "933 S-2 Glass Roving",
        "category": "glass_fiber",
        "subcategory": "s_glass",
        "industries": ["aerospace", "defense"],
        "specs": {
            "tensile_strength": "4,890 MPa",
            "tensile_modulus": "87 GPa",
            "yield": "250-2500 yards/lb",
        },
        "description": "High-performance S-2 glass in roving form.",
        "in_c1_catalog": True,
    },
    
    # --- Jushi Glass Fibers ---
    {
        "id": "JUS-ECT469",
        "supplier": "Jushi",
        "name": "ECT469 E-Glass Direct Roving",
        "category": "glass_fiber",
        "subcategory": "e_glass",
        "industries": ["wind_energy", "automotive", "industrial"],
        "specs": {
            "tensile_strength": "3,200 MPa",
            "tex": "2400, 4800",
            "compatibility": "Epoxy, VE, UP",
        },
        "description": "Cost-effective E-glass for high-volume applications.",
        "in_c1_catalog": True,
    },
    
    # ==========================================================================
    # CORE MATERIALS
    # ==========================================================================
    
    # --- Honeycomb Cores (Hexcel) ---
    {
        "id": "HXL-HRH10",
        "supplier": "Hexcel",
        "name": "HRH-10 Nomex Honeycomb",
        "category": "core",
        "subcategory": "honeycomb_aramid",
        "industries": ["aerospace", "defense"],
        "specs": {
            "cell_size": "3.2mm (1/8 inch)",
            "density": "29-192 kg/m³",
            "compressive_strength": "0.69-10.3 MPa",
            "material": "Aramid/Phenolic",
        },
        "description": "Standard Nomex honeycomb for aerospace sandwich structures.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-HRH327",
        "supplier": "Hexcel",
        "name": "HRH-327 Fiberglass Honeycomb",
        "category": "core",
        "subcategory": "honeycomb_glass",
        "industries": ["aerospace", "marine"],
        "specs": {
            "cell_size": "6.4mm (1/4 inch)",
            "density": "32-128 kg/m³",
            "material": "Glass/Phenolic",
        },
        "description": "Fiberglass honeycomb for radomes and marine applications.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-ALCORE",
        "supplier": "Hexcel",
        "name": "CRIII Aluminum Honeycomb",
        "category": "core",
        "subcategory": "honeycomb_aluminum",
        "industries": ["aerospace", "industrial"],
        "specs": {
            "cell_size": "3.2-19mm",
            "density": "16-192 kg/m³",
            "material": "5052 Aluminum",
        },
        "description": "Corrosion-resistant aluminum honeycomb core.",
        "in_c1_catalog": True,
    },
    
    # --- Foam Cores ---
    {
        "id": "DIAB-H60",
        "supplier": "Diab",
        "name": "Divinycell H60",
        "category": "core",
        "subcategory": "foam_pvc",
        "industries": ["marine", "wind_energy", "transportation"],
        "specs": {
            "density": "60 kg/m³",
            "compressive_strength": "0.9 MPa",
            "shear_strength": "0.76 MPa",
            "material": "Cross-linked PVC",
        },
        "description": "Versatile closed-cell PVC foam for marine and wind.",
        "in_c1_catalog": True,
    },
    {
        "id": "DIAB-H80",
        "supplier": "Diab",
        "name": "Divinycell H80",
        "category": "core",
        "subcategory": "foam_pvc",
        "industries": ["marine", "wind_energy", "aerospace"],
        "specs": {
            "density": "80 kg/m³",
            "compressive_strength": "1.4 MPa",
            "shear_strength": "1.15 MPa",
            "material": "Cross-linked PVC",
        },
        "description": "Higher density PVC foam for structural applications.",
        "in_c1_catalog": True,
    },
    {
        "id": "DIAB-H100",
        "supplier": "Diab",
        "name": "Divinycell H100",
        "category": "core",
        "subcategory": "foam_pvc",
        "industries": ["marine", "industrial"],
        "specs": {
            "density": "100 kg/m³",
            "compressive_strength": "2.0 MPa",
            "shear_strength": "1.6 MPa",
        },
        "description": "High-performance PVC foam for demanding applications.",
        "in_c1_catalog": True,
    },
    {
        "id": "DIAB-HP130",
        "supplier": "Diab",
        "name": "Divinycell HP130",
        "category": "core",
        "subcategory": "foam_pvc",
        "industries": ["aerospace", "marine"],
        "specs": {
            "density": "130 kg/m³",
            "compressive_strength": "4.0 MPa",
            "temperature_resistance": "High",
        },
        "description": "High-performance foam for aerospace sandwich panels.",
        "in_c1_catalog": False,
    },
    {
        "id": "ARX-C70",
        "supplier": "3A Composites",
        "name": "AIREX C70",
        "category": "core",
        "subcategory": "foam_pvc",
        "industries": ["marine", "wind_energy", "rail"],
        "specs": {
            "density": "40-200 kg/m³",
            "material": "Linear PVC",
            "fsc_certified": "Yes",
        },
        "description": "Sustainable PVC foam core with FSC certification.",
        "in_c1_catalog": True,
    },
    {
        "id": "ARX-T92",
        "supplier": "3A Composites",
        "name": "AIREX T92",
        "category": "core",
        "subcategory": "foam_pet",
        "industries": ["wind_energy", "marine", "transportation"],
        "specs": {
            "density": "100-200 kg/m³",
            "material": "PET",
            "recyclable": "Yes",
            "fsc_certified": "Yes",
        },
        "description": "Recyclable PET foam for sustainable composite applications.",
        "in_c1_catalog": True,
    },
    
    # --- Gurit Core Materials ---
    {
        "id": "GUR-CORECELL",
        "supplier": "Gurit",
        "name": "Corecell M80",
        "category": "core",
        "subcategory": "foam_san",
        "industries": ["marine", "wind_energy"],
        "specs": {
            "density": "80 kg/m³",
            "material": "SAN foam",
            "impact_resistance": "High",
        },
        "description": "SAN foam core with excellent impact resistance.",
        "in_c1_catalog": True,
    },
    {
        "id": "GUR-KERDYN",
        "supplier": "Gurit",
        "name": "Kerdyn PET",
        "category": "core",
        "subcategory": "foam_pet",
        "industries": ["wind_energy", "rail", "marine"],
        "specs": {
            "density": "65-200 kg/m³",
            "material": "PET",
            "recyclability": "100%",
        },
        "description": "Fully recyclable PET foam core material.",
        "in_c1_catalog": True,
    },
    {
        "id": "GUR-BALTEK",
        "supplier": "Gurit",
        "name": "Baltek SB.100",
        "category": "core",
        "subcategory": "balsa",
        "industries": ["marine", "wind_energy"],
        "specs": {
            "density": "100-250 kg/m³",
            "material": "End-grain balsa",
            "shear_strength": "2.8-6.7 MPa",
        },
        "description": "Natural balsa wood core for marine and wind applications.",
        "in_c1_catalog": True,
    },
    
    # ==========================================================================
    # RESINS
    # ==========================================================================
    
    # --- Hexcel Resins ---
    {
        "id": "HXL-RTM6",
        "supplier": "Hexcel",
        "name": "HexFlow RTM6",
        "category": "resin",
        "subcategory": "rtm_epoxy",
        "industries": ["aerospace"],
        "specs": {
            "viscosity": "33 mPa.s @ 120°C",
            "pot_life": "2 hours @ 120°C",
            "cure_temp": "180°C",
            "tg": "183°C (DMA)",
        },
        "description": "High-performance RTM epoxy for aerospace structures.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-RTM6-2",
        "supplier": "Hexcel",
        "name": "HexFlow RTM6-2",
        "category": "resin",
        "subcategory": "rtm_epoxy",
        "industries": ["aerospace", "automotive"],
        "specs": {
            "viscosity": "30 mPa.s @ 120°C",
            "pot_life": "2.5 hours @ 120°C",
            "cure_temp": "180°C",
            "tg": "194°C (DMA)",
        },
        "description": "Enhanced RTM6 with improved processing window.",
        "in_c1_catalog": True,
    },
    
    # --- Huntsman Resins ---
    {
        "id": "HUN-LY556",
        "supplier": "Huntsman",
        "name": "Araldite LY 556",
        "category": "resin",
        "subcategory": "laminating_epoxy",
        "industries": ["aerospace", "industrial", "marine"],
        "specs": {
            "viscosity": "10,000-12,000 mPa.s @ 25°C",
            "epoxy_equivalent": "183-189 g/eq",
            "density": "1.17 g/cm³",
        },
        "description": "Standard bisphenol-A epoxy for hand layup and infusion.",
        "in_c1_catalog": True,
    },
    {
        "id": "HUN-8605",
        "supplier": "Huntsman",
        "name": "Araldite 8605",
        "category": "resin",
        "subcategory": "infusion_epoxy",
        "industries": ["wind_energy", "marine"],
        "specs": {
            "viscosity": "250 mPa.s @ 25°C",
            "gel_time": "240 min @ 25°C",
            "cure_temp": "70°C post-cure",
        },
        "description": "Low-viscosity infusion epoxy for large structures.",
        "in_c1_catalog": True,
    },
    
    # --- Polynt Resins ---
    {
        "id": "POL-ENYDYNE",
        "supplier": "Polynt-Reichhold",
        "name": "Enydyne H68284",
        "category": "resin",
        "subcategory": "vinyl_ester",
        "industries": ["marine", "chemical", "infrastructure"],
        "specs": {
            "viscosity": "150-200 mPa.s @ 25°C",
            "corrosion_resistance": "Excellent",
            "hdt": "105°C",
        },
        "description": "Premium vinyl ester for corrosion-resistant applications.",
        "in_c1_catalog": True,
    },
    {
        "id": "POL-POLYLITE",
        "supplier": "Polynt-Reichhold",
        "name": "Polylite 31325-00",
        "category": "resin",
        "subcategory": "polyester",
        "industries": ["marine", "construction", "transportation"],
        "specs": {
            "viscosity": "350-450 mPa.s @ 25°C",
            "type": "Isophthalic polyester",
            "gel_time": "10-15 min",
        },
        "description": "Marine-grade isophthalic polyester resin.",
        "in_c1_catalog": True,
    },
    {
        "id": "POL-DION",
        "supplier": "Polynt-Reichhold",
        "name": "DION 9800-05A",
        "category": "resin",
        "subcategory": "vinyl_ester",
        "industries": ["chemical", "infrastructure", "pulp_paper"],
        "specs": {
            "viscosity": "200-300 mPa.s",
            "chemical_resistance": "Superior",
            "temperature_resistance": "Up to 150°C",
        },
        "description": "High-performance vinyl ester for chemical storage tanks.",
        "in_c1_catalog": True,
    },
    
    # ==========================================================================
    # ADHESIVES & FILMS
    # ==========================================================================
    {
        "id": "HXL-FM300",
        "supplier": "Hexcel",
        "name": "FM 300 Adhesive Film",
        "category": "adhesive",
        "subcategory": "structural_film",
        "industries": ["aerospace"],
        "specs": {
            "cure_temp": "121°C or 177°C",
            "peel_strength": "Excellent",
            "weight": "293 g/m²",
        },
        "description": "Modified epoxy structural adhesive film for aerospace bonding.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-FM94",
        "supplier": "Hexcel",
        "name": "FM 94 Adhesive Film",
        "category": "adhesive",
        "subcategory": "structural_film",
        "industries": ["aerospace", "defense"],
        "specs": {
            "cure_temp": "120°C",
            "service_temp": "-55°C to 150°C",
            "outlife": ">30 days",
        },
        "description": "High-performance aerospace adhesive film with excellent durability.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-REDUX",
        "supplier": "Hexcel",
        "name": "Redux 322",
        "category": "adhesive",
        "subcategory": "structural_film",
        "industries": ["aerospace"],
        "specs": {
            "cure_temp": "175°C",
            "lap_shear": "High",
            "metal_bonding": "Yes",
        },
        "description": "Classic aerospace adhesive for metal-to-metal bonding.",
        "in_c1_catalog": False,
    },
    
    # ==========================================================================
    # FABRICS
    # ==========================================================================
    {
        "id": "HXL-G0814",
        "supplier": "Hexcel",
        "name": "G0814 Carbon Fabric",
        "category": "fabric",
        "subcategory": "carbon_woven",
        "industries": ["aerospace", "automotive"],
        "specs": {
            "weave": "2x2 Twill",
            "weight": "285 g/m²",
            "fiber": "AS4 6K",
            "width": "1270mm",
        },
        "description": "Standard aerospace carbon fabric in twill weave.",
        "in_c1_catalog": True,
    },
    {
        "id": "HXL-G0939",
        "supplier": "Hexcel",
        "name": "G0939 Carbon Fabric",
        "category": "fabric",
        "subcategory": "carbon_woven",
        "industries": ["aerospace", "sporting_goods"],
        "specs": {
            "weave": "Plain",
            "weight": "193 g/m²",
            "fiber": "AS4 3K",
        },
        "description": "Lightweight plain weave carbon fabric.",
        "in_c1_catalog": True,
    },
    {
        "id": "FIB-QX22",
        "supplier": "Fibreglast",
        "name": "QX 2610 Carbon NCF",
        "category": "fabric",
        "subcategory": "carbon_ncf",
        "industries": ["automotive", "marine", "industrial"],
        "specs": {
            "construction": "Biaxial +45/-45",
            "weight": "400 g/m²",
            "fiber": "T700 12K",
        },
        "description": "Non-crimp fabric for high-performance applications.",
        "in_c1_catalog": True,
    },
]


def _search_products(
    supplier: Optional[str] = None,
    category: Optional[str] = None,
    industry: Optional[str] = None,
    query: Optional[str] = None,
    in_catalog_only: bool = False,
) -> List[dict]:
    """Internal helper to search products."""
    results = PRODUCT_CATALOG.copy()
    
    if supplier:
        results = [p for p in results if supplier.lower() in p["supplier"].lower()]
    
    if category:
        results = [p for p in results if category.lower() in p["category"].lower()]
    
    if industry:
        results = [p for p in results if industry.lower() in [i.lower() for i in p.get("industries", [])]]
    
    if query:
        q = query.lower()
        results = [p for p in results if 
                   q in p["name"].lower() or 
                   q in p["supplier"].lower() or
                   q in p.get("category", "").lower() or
                   q in p.get("subcategory", "").lower()]
    
    if in_catalog_only:
        results = [p for p in results if p.get("in_c1_catalog", False)]
    
    return results


@tool
def search_competitor_products(
    supplier: Optional[str] = None,
    category: Optional[str] = None,
    industry: Optional[str] = None,
    query: Optional[str] = None,
) -> str:
    """
    Search competitor product catalogs for composites materials.
    
    Use when users ask:
    - "What prepreg SKUs does Hexcel offer?"
    - "Show me Toray's aerospace products"
    - "Find carbon fiber products for wind energy"
    - "What does the competition offer in marine?"
    
    Args:
        supplier: Filter by supplier name (Hexcel, Toray, Owens Corning, etc.)
        category: Product category (carbon_fiber, glass_fiber, prepreg, resin)
        industry: Target industry (aerospace, automotive, marine, wind_energy)
        query: Free text search across product names and specs
    
    Returns:
        List of matching products with availability status
    """
    logger.info(f"Searching products: supplier={supplier}, category={category}, industry={industry}")
    
    products = _search_products(supplier, category, industry, query)
    
    if not products:
        filters = []
        if supplier:
            filters.append(f"supplier: {supplier}")
        if category:
            filters.append(f"category: {category}")
        if industry:
            filters.append(f"industry: {industry}")
        if query:
            filters.append(f"query: {query}")
        return json.dumps({
            "count": 0,
            "message": f"No products found matching: {', '.join(filters) if filters else 'criteria'}",
            "suggestion": "Try broader search terms or different category",
        }, indent=2)
    
    # Group by supplier
    by_supplier = {}
    for p in products:
        if p["supplier"] not in by_supplier:
            by_supplier[p["supplier"]] = []
        by_supplier[p["supplier"]].append({
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "industries": p.get("industries", []),
            "in_c1_catalog": p.get("in_c1_catalog", False),
        })
    
    return json.dumps({
        "count": len(products),
        "products_by_supplier": by_supplier,
        "c1_available": sum(1 for p in products if p.get("in_c1_catalog")),
        "gaps": sum(1 for p in products if not p.get("in_c1_catalog")),
    }, indent=2)


@tool
def get_product_specs(product_name: str) -> str:
    """
    Get detailed specifications for a specific product.
    
    Use when users ask:
    - "What are the specs for T700S?"
    - "Tell me about HexPly M21"
    - "Get details on Advantex glass fiber"
    
    Args:
        product_name: Product name or product ID
    
    Returns:
        Detailed product specifications including mechanical properties
    """
    logger.info(f"Getting product specs: {product_name}")
    
    products = _search_products(query=product_name)
    
    if not products:
        return json.dumps({
            "error": f"Product '{product_name}' not found",
            "suggestion": "Try search_competitor_products to find the correct product name",
        }, indent=2)
    
    # Return first match with full details
    p = products[0]
    
    return json.dumps({
        "product": {
            "id": p["id"],
            "name": p["name"],
            "supplier": p["supplier"],
            "category": p["category"],
            "subcategory": p.get("subcategory"),
            "industries": p.get("industries", []),
        },
        "specifications": p.get("specs", {}),
        "availability": {
            "in_c1_catalog": p.get("in_c1_catalog", False),
            "message": "Available through Composites One" if p.get("in_c1_catalog") else "Not currently in C1 catalog",
        },
    }, indent=2)


@tool
def compare_product_specs(product1: str, product2: str) -> str:
    """
    Compare specifications between two products side-by-side.
    
    Use when users ask:
    - "Compare Hexcel M21 vs Toray 3900"
    - "How does T700S compare to AS4?"
    - "Difference between IM7 and T800S"
    
    Args:
        product1: First product name or ID
        product2: Second product name or ID
    
    Returns:
        Side-by-side specification comparison
    """
    logger.info(f"Comparing products: {product1} vs {product2}")
    
    p1_results = _search_products(query=product1)
    p2_results = _search_products(query=product2)
    
    if not p1_results:
        return json.dumps({"error": f"Product '{product1}' not found"}, indent=2)
    if not p2_results:
        return json.dumps({"error": f"Product '{product2}' not found"}, indent=2)
    
    p1, p2 = p1_results[0], p2_results[0]
    
    # Get all spec keys from both products
    all_specs = set(p1.get("specs", {}).keys()) | set(p2.get("specs", {}).keys())
    
    comparison = {}
    for key in sorted(all_specs):
        comparison[key] = {
            p1["name"]: p1.get("specs", {}).get(key, "N/A"),
            p2["name"]: p2.get("specs", {}).get(key, "N/A"),
        }
    
    return json.dumps({
        "comparison": {
            "product_1": {
                "name": p1["name"],
                "supplier": p1["supplier"],
                "category": p1["category"],
                "in_c1_catalog": p1.get("in_c1_catalog", False),
            },
            "product_2": {
                "name": p2["name"],
                "supplier": p2["supplier"],
                "category": p2["category"],
                "in_c1_catalog": p2.get("in_c1_catalog", False),
            },
        },
        "specifications": comparison,
        "recommendation": _get_comparison_recommendation(p1, p2),
    }, indent=2)


def _get_comparison_recommendation(p1: dict, p2: dict) -> str:
    """Generate a recommendation based on comparison."""
    c1_1 = p1.get("in_c1_catalog", False)
    c1_2 = p2.get("in_c1_catalog", False)
    
    if c1_1 and not c1_2:
        return f"{p1['name']} is available through C1, {p2['name']} is not."
    elif c1_2 and not c1_1:
        return f"{p2['name']} is available through C1, {p1['name']} is not."
    elif c1_1 and c1_2:
        return "Both products are available through Composites One."
    else:
        return "Neither product is currently in the C1 catalog."


@tool
def find_product_gaps(
    category: str,
    industry: Optional[str] = None,
) -> str:
    """
    Identify product gaps vs competition - what competitors offer that we don't.
    
    Use when users ask:
    - "Where do we have gaps vs Gurit in marine?"
    - "What aerospace prepregs don't we carry?"
    - "Product gaps in carbon fiber"
    
    Args:
        category: Product category to analyze (carbon_fiber, prepreg, resin, glass_fiber)
        industry: Optional industry filter
    
    Returns:
        Gap analysis showing what we carry vs what competitors offer
    """
    logger.info(f"Finding product gaps: category={category}, industry={industry}")
    
    all_products = _search_products(category=category, industry=industry)
    
    if not all_products:
        return json.dumps({
            "error": f"No products found in category '{category}'",
            "available_categories": ["carbon_fiber", "glass_fiber", "prepreg", "resin"],
        }, indent=2)
    
    we_carry = [p for p in all_products if p.get("in_c1_catalog", False)]
    gaps = [p for p in all_products if not p.get("in_c1_catalog", False)]
    
    # Group gaps by supplier
    gaps_by_supplier = {}
    for p in gaps:
        if p["supplier"] not in gaps_by_supplier:
            gaps_by_supplier[p["supplier"]] = []
        gaps_by_supplier[p["supplier"]].append(p["name"])
    
    coverage_pct = (len(we_carry) / len(all_products) * 100) if all_products else 0
    
    return json.dumps({
        "category": category,
        "industry_filter": industry,
        "summary": {
            "total_products": len(all_products),
            "we_carry": len(we_carry),
            "gaps": len(gaps),
            "coverage_percent": round(coverage_pct, 1),
        },
        "products_we_carry": [{"name": p["name"], "supplier": p["supplier"]} for p in we_carry],
        "gaps_by_supplier": gaps_by_supplier,
        "recommendation": f"Coverage is {coverage_pct:.0f}%. " + 
                         (f"Consider adding products from: {', '.join(gaps_by_supplier.keys())}" if gaps else "Full coverage achieved!"),
    }, indent=2)


@tool
def get_c1_catalog(
    category: Optional[str] = None,
    industry: Optional[str] = None,
) -> str:
    """
    Get Composites One's product catalog - what we distribute.
    
    Use when users ask:
    - "What do we distribute?"
    - "Show me our aerospace products"
    - "What carbon fiber do we carry?"
    - "Our product catalog"
    
    Args:
        category: Filter by category (carbon_fiber, prepreg, resin, glass_fiber)
        industry: Filter by industry (aerospace, automotive, marine, wind_energy)
    
    Returns:
        C1's product catalog with filtering
    """
    logger.info(f"Getting C1 catalog: category={category}, industry={industry}")
    
    c1_products = _search_products(category=category, industry=industry, in_catalog_only=True)
    
    if not c1_products:
        filters = []
        if category:
            filters.append(f"category: {category}")
        if industry:
            filters.append(f"industry: {industry}")
        return json.dumps({
            "count": 0,
            "message": f"No C1 products found matching: {', '.join(filters) if filters else 'criteria'}",
        }, indent=2)
    
    # Group by category
    by_category = {}
    for p in c1_products:
        cat = p["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append({
            "name": p["name"],
            "supplier": p["supplier"],
            "industries": p.get("industries", []),
        })
    
    return json.dumps({
        "total_products": len(c1_products),
        "filter_applied": {
            "category": category,
            "industry": industry,
        },
        "products_by_category": by_category,
        "suppliers_represented": list(set(p["supplier"] for p in c1_products)),
    }, indent=2)


@tool
def suggest_alternatives(product_name: str) -> str:
    """
    Suggest alternative products from our catalog when we don't carry something.
    
    Use when users ask:
    - "What can we offer instead of [competitor product]?"
    - "Alternatives to Gurit prepreg"
    - "What do we have similar to T1100G?"
    
    Args:
        product_name: Product to find alternatives for
    
    Returns:
        Alternative products from C1 catalog with comparison
    """
    logger.info(f"Finding alternatives to: {product_name}")
    
    products = _search_products(query=product_name)
    
    if not products:
        return json.dumps({
            "error": f"Product '{product_name}' not found",
            "suggestion": "Try search_competitor_products to find the correct product",
        }, indent=2)
    
    target = products[0]
    
    # Find alternatives in same category that we carry
    alternatives = _search_products(
        category=target["category"],
        in_catalog_only=True,
    )
    
    # Remove the target if it's in our catalog
    alternatives = [p for p in alternatives if p["id"] != target["id"]]
    
    # Prioritize same subcategory if exists
    same_subcategory = [p for p in alternatives if p.get("subcategory") == target.get("subcategory")]
    other = [p for p in alternatives if p.get("subcategory") != target.get("subcategory")]
    
    ranked_alternatives = same_subcategory + other
    
    return json.dumps({
        "target_product": {
            "name": target["name"],
            "supplier": target["supplier"],
            "category": target["category"],
            "in_c1_catalog": target.get("in_c1_catalog", False),
        },
        "alternatives_found": len(ranked_alternatives),
        "recommended_alternatives": [
            {
                "name": p["name"],
                "supplier": p["supplier"],
                "match_reason": "Same subcategory" if p in same_subcategory else "Same category",
                "industries": p.get("industries", []),
            }
            for p in ranked_alternatives[:5]
        ],
        "recommendation": f"We have {len(ranked_alternatives)} alternative(s) in the same category." if ranked_alternatives else "No direct alternatives in C1 catalog.",
    }, indent=2)
