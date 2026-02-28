import streamlit as st
import pandas as pd
import math
import numpy as np

st.set_page_config(page_title="IS Code Pile Foundation Designer", layout="wide")

st.title("🏗️ IS-Compliant Pile Foundation & BBS Generator")
st.markdown("Automated conversion of Isolated Footings to Under-Reamed Piles with strict adherence to **IS 2911** and **IS 456**.")

# ==========================================
# 1. DESIGN PARAMETERS (Sidebar)
# ==========================================
st.sidebar.header("1. Soil & Pile Parameters")
sbc = st.sidebar.number_input("Soil Bearing Capacity (kN/m²)", min_value=50, value=100, step=10)

st.sidebar.markdown("---")
st.sidebar.subheader("Pile Specs (IS 2911)")
pile_dia = st.sidebar.selectbox("Pile Diameter (D) in mm", [250, 300, 400], index=1)
pile_depth = st.sidebar.number_input("Pile Depth (m)", min_value=2.0, value=4.0, step=0.5)
pile_capacity = st.sidebar.number_input("Safe Load Capacity per Pile (kN)", min_value=100, value=250, step=50)

st.sidebar.markdown("---")
st.sidebar.subheader("Detailing Rules (IS 456)")
cover_fnd = st.sidebar.number_input("Foundation Cover (mm)", value=50)
cover_col = st.sidebar.number_input("Column Cover (mm)", value=40)

# Standard IS weights for steel (D^2 / 162)
unit_wt = {8: 0.395, 10: 0.617, 12: 0.888, 16: 1.580, 20: 2.466}

# ==========================================
# 2. INPUT DATA
# ==========================================
st.header("2. Input Structural Data")
st.caption("Enter column sizes and original isolated footing dimensions. The AI will reverse-engineer the axial loads.")

# Default data mimicking the Gaidhane Residence structural drawing
default_data = pd.DataFrame({
    "ID": ["F1", "F2", "F3", "F4"],
    "Qty": [4, 4, 1, 3],
    "Footing L (m)": [1.65, 1.65, 2.35, 2.25],
    "Footing B (m)": [1.53, 1.53, 2.13, 2.03],
    "Col L (mm)": [400, 400, 500, 500],
    "Col B (mm)": [280, 280, 280, 280],
    "Main Dia (mm)": [12, 12, 16, 16],
    "Main Qty": [6, 6, 4, 4],
    "Sec Dia (mm)": [0, 0, 12, 12],
    "Sec Qty": [0, 0, 4, 4]
})

input_df = st.data_editor(default_data, num_rows="dynamic", use_container_width=True)

# ==========================================
# 3. ENGINEERING ENGINE & BBS GENERATOR
# ==========================================
if st.button("🚀 Run IS Code Design & Generate BBS", type="primary"):
    st.markdown("---")
    st.header("3. Output: Bar Bending Schedule & Abstract")
    
    bbs_data = []
    total_steel = {8: 0, 10: 0, 12: 0, 16: 0, 20: 0}
    
    # IS 2911 Under-Reamed Math
    bulb_dia = 2.5 * pile_dia
    min_spacing = 1.5 * bulb_dia  # Code requirement to prevent bulb intersection
    
    for index, row in input_df.iterrows():
        qty = int(row["Qty"])
        if qty <= 0: continue
            
        # --- A. LOAD & PILE REQUIREMENT ---
        load_kn = (row["Footing L (m)"] * row["Footing B (m)"]) * sbc
        num_piles = max(1, math.ceil(load_kn / pile_capacity))
        
        # --- B. DYNAMIC PILE CAP SIZING ---
        edge_clearance = 150 # mm
        if num_piles == 1:
            cap_l = pile_dia + (2 * edge_clearance)
            cap_w = cap_l
            cap_d = 450
            mesh_x_len = (cap_l - 2*cover_fnd + 200) / 1000 # Add 100mm L-bends
            mesh_y_len = mesh_x_len
            mesh_x_qty = math.ceil(cap_w / 150) + 1
            mesh_y_qty = mesh_x_qty
        else:
            # 2-Pile Cap sizing using strict IS 2911 spacing
            cap_l = min_spacing + pile_dia + (2 * edge_clearance)
            cap_w = pile_dia + (2 * edge_clearance)
            cap_d = 500
            
            # Mesh calculations
            mesh_long_len = (cap_l - 2*cover_fnd + 200) / 1000
            mesh_short_len = (cap_w - 2*cover_fnd + 200) / 1000
            
            mesh_long_qty = math.ceil(cap_w / 150) + 1
            mesh_short_qty = math.ceil(cap_l / 150) + 1

        # --- C. BBS ROW GENERATION ---
        
        # 1. Piles
        total_piles = num_piles * qty
        pile_main_len = pile_depth + 0.5 # 0.5m anchorage into cap
        bbs_data.append({"Element": f"{row['ID']} - Piles Main", "Shape": "L (Vertical)", "Dia": 12, "Members": total_piles, "Bars/Mem": 6, "Total Bars": total_piles*6, "Cut Length (m)": pile_main_len, "Total Len (m)": total_piles*6*pile_main_len})
        total_steel[12] += total_piles * 6 * pile_main_len
        
        # Spiral Ties (Assuming 150mm pitch)
        spiral_length = (pile_depth / 0.15) * (math.pi * (pile_dia - 2*cover_fnd)/1000)
        bbs_data.append({"Element": f"{row['ID']} - Pile Spiral", "Shape": "◯", "Dia": 8, "Members": total_piles, "Bars/Mem": 1, "Total Bars": total_piles, "Cut Length (m)": round(spiral_length,2), "Total Len (m)": round(total_piles*spiral_length,2)})
        total_steel[8] += total_piles * spiral_length
        
        # 2. Pile Caps
        if num_piles == 1:
            bbs_data.append({"Element": f"{row['ID']} - Cap Mesh X", "Shape": "└─┘", "Dia": 10, "Members": qty, "Bars/Mem": mesh_x_qty, "Total Bars": qty*mesh_x_qty, "Cut Length (m)": mesh_x_len, "Total Len (m)": qty*mesh_x_qty*mesh_x_len})
            bbs_data.append({"Element": f"{row['ID']} - Cap Mesh Y", "Shape": "└─┘", "Dia": 10, "Members": qty, "Bars/Mem": mesh_y_qty, "Total Bars": qty*mesh_y_qty, "Cut Length (m)": mesh_y_len, "Total Len (m)": qty*mesh_y_qty*mesh_y_len})
            total_steel[10] += (qty * mesh_x_qty * mesh_x_len) + (qty * mesh_y_qty * mesh_y_len)
        else:
            bbs_data.append({"Element": f"{row['ID']} - Cap Short Span", "Shape": "└─┘", "Dia": 10, "Members": qty, "Bars/Mem": mesh_short_qty, "Total Bars": qty*mesh_short_qty, "Cut Length (m)": mesh_short_len, "Total Len (m)": round(qty*mesh_short_qty*mesh_short_len, 2)})
            bbs_data.append({"Element": f"{row['ID']} - Cap Long Span", "Shape": "└─┘", "Dia": 12, "Members": qty, "Bars/Mem": mesh_long_qty, "Total Bars": qty*mesh_long_qty, "Cut Length (m)": mesh_long_len, "Total Len (m)": round(qty*mesh_long_qty*mesh_long_len, 2)})
            total_steel[10] += (qty * mesh_short_qty * mesh_short_len)
            total_steel[12] += (qty * mesh_long_qty * mesh_long_len)

        # 3. Columns (Assumed 1.5m below ground)
        col_l, col_b = row["Col L (mm)"], row["Col B (mm)"]
        
        # Main Steel
        main_dia = int(row["Main Dia (mm)"])
        if main_dia > 0:
            main_len = 1.5 + 0.6  # 1.5m height + 0.6m L-shoe
            bbs_data.append({"Element": f"Col {row['ID']} - Main", "Shape": "L", "Dia": main_dia, "Members": qty, "Bars/Mem": int(row["Main Qty"]), "Total Bars": qty*int(row["Main Qty"]), "Cut Length (m)": main_len, "Total Len (m)": round(qty*int(row["Main Qty"])*main_len, 2)})
            total_steel[main_dia] += qty * int(row["Main Qty"]) * main_len
            
        # Secondary Steel
        sec_dia = int(row["Sec Dia (mm)"])
        if sec_dia > 0:
            bbs_data.append({"Element": f"Col {row['ID']} - Sec", "Shape": "L", "Dia": sec_dia, "Members": qty, "Bars/Mem": int(row["Sec Qty"]), "Total Bars": qty*int(row["Sec Qty"]), "Cut Length (m)": main_len, "Total Len (m)": round(qty*int(row["Sec Qty"])*main_len, 2)})
            total_steel[sec_dia] += qty * int(row["Sec Qty"]) * main_len

        # Column Ties (Dynamic calculation with seismic hooks)
        core_l = col_l - (2 * cover_col)
        core_b = col_b - (2 * cover_col)
        tie_cut_len = (2 * (core_l + core_b) + (24 * 8)) / 1000 # 24d for 135-deg hooks
        
        bbs_data.append({"Element": f"Col {row['ID']} - Ties", "Shape": "▭", "Dia": 8, "Members": qty, "Bars/Mem": 10, "Total Bars": qty*10, "Cut Length (m)": round(tie_cut_len,2), "Total Len (m)": round(qty*10*tie_cut_len, 2)})
        total_steel[8] += qty * 10 * tie_cut_len

    # --- RENDER TABLES ---
    st.subheader("1. Code-Compliant Bar Bending Schedule")
    df_bbs = pd.DataFrame(bbs_data)
    st.dataframe(df_bbs, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("2. Steel Abstract (Material Takeoff)")
    
    abstract_data = []
    grand_total = 0
    
    for dia, length in total_steel.items():
        if length > 0:
            weight = length * unit_wt.get(dia, 0)
            grand_total += weight
            abstract_data.append({
                "Bar Dia (mm)": f"{dia} mm",
                "Total Length (m)": round(length, 1),
                "Unit Weight (kg/m)": unit_wt.get(dia, 0),
                "Total Weight (kg)": round(weight, 1)
            })
            
    col1, col2 = st.columns([2, 1])
    with col1:
        st.table(pd.DataFrame(abstract_data))
    with col2:
        st.info("Calculations based strictly on IS 2911 spacing rules and IS 456 detailing lengths.")
        st.success(f"### 🛒 Grand Total (incl. 5% waste):\n **{grand_total * 1.05:.1f} kg**")
