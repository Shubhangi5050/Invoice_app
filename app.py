import streamlit as st
import json
import pandas as pd
from io import BytesIO
import os
from dotenv import load_dotenv
from PIL import Image

# Google GenAI SDK Import
from google import genai
from google.genai import types

# Load environment variables (.env file)
load_dotenv()

# Page Configuration
st.set_page_config(
    page_title="AI Financial Operations & Invoice Agent",
    page_icon="🧾",
    layout="wide"
)

# Custom CSS for UI
st.markdown("""
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E293B; margin-bottom: 0px; }
    .sub-header { font-size: 1rem; color: #64748B; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)


# Initialize Gemini Client
@st.cache_resource
def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("⚠️ GEMINI_API_KEY not found in .env file. Please check your setup.")
        st.stop()
    return genai.Client(api_key=api_key)


def parse_invoice_with_gemini(client, uploaded_file):
    """Use Google Gemini 2.5 Flash to extract structured invoice data."""
    prompt = """
    You are an expert Financial Audit AI Agent. Extract information from the provided invoice image or document.
    Respond strictly with a valid JSON object matching this schema:
    {
        "vendor_name": "string",
        "invoice_number": "string",
        "invoice_date": "YYYY-MM-DD",
        "currency": "USD/EUR/INR etc",
        "subtotal": float,
        "tax_amount": float,
        "total_amount": float,
        "line_items": [
            {"description": "string", "quantity": float, "unit_price": float, "amount": float}
        ]
    }
    """

    try:
        # Convert uploaded file to PIL Image
        image = Image.open(uploaded_file)

        # Force Gemini to return clean JSON
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt],
            config=config
        )

        raw_text = response.text.strip()
        return json.loads(raw_text)

    except Exception as e:
        st.error(f"Error communicating with Gemini API: {str(e)}")
        return None


def run_business_validations(parsed_data):
    """Apply rule-based audit logic to parsed data."""
    warnings = []
    status = "Approved"

    total = parsed_data.get("total_amount", 0.0)
    subtotal = parsed_data.get("subtotal", 0.0)
    tax = parsed_data.get("tax_amount", 0.0)

    # Rule 1: High Value Threshold Flag (> $1,000)
    if total > 1000.0:
        warnings.append("⚠️ High Value Invoice (> $1,000): Requires Manager Approval")
        status = "Needs Review"

    # Rule 2: Subtotal + Tax mismatch check
    calculated_total = round(subtotal + tax, 2)
    if abs(calculated_total - round(total, 2)) > 0.05:
        warnings.append(f"❌ Calculation Mismatch: Subtotal ({subtotal}) + Tax ({tax}) != Total ({total})")
        status = "Requires Correction"

    # Rule 3: Missing tax check
    if tax == 0.0 and total > 200.0:
        warnings.append("⚠️ Zero Tax Recorded: Verify tax exemption status for vendor")

    return status, warnings


def convert_df_to_excel(extracted_data):
    """Generate Excel file download for accounting software imports."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1: Summary Data
        summary_df = pd.DataFrame([{
            "Vendor": extracted_data.get("vendor_name"),
            "Invoice #": extracted_data.get("invoice_number"),
            "Date": extracted_data.get("invoice_date"),
            "Currency": extracted_data.get("currency"),
            "Subtotal": extracted_data.get("subtotal"),
            "Tax": extracted_data.get("tax_amount"),
            "Total Amount": extracted_data.get("total_amount")
        }])
        summary_df.to_excel(writer, sheet_name="Invoice Summary", index=False)

        # Sheet 2: Line Items Detail
        items_df = pd.DataFrame(extracted_data.get("line_items", []))
        if not items_df.empty:
            items_df.to_excel(writer, sheet_name="Line Items", index=False)

    output.seek(0)
    return output


# --- STREAMLIT UI LAYOUT ---

st.markdown('<p class="main-header">🧾 AI Invoice & Financial Audit Agent</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Automated Data Extraction & Audit Rules powered by Gemini 2.5 Flash</p>', unsafe_allow_html=True)

# Sidebar
st.sidebar.title("Configuration & Status")
api_key_input = st.sidebar.text_input("Gemini API Key Override (Optional)", type="password")

if api_key_input:
    client = genai.Client(api_key=api_key_input)
else:
    client = get_gemini_client()

st.sidebar.markdown("---")
st.sidebar.markdown("### Agent Capabilities")
st.sidebar.info("""
- 📄 Image & Invoice Extraction
- 🧠 Powered by Gemini 2.5 Flash (Free Tier)
- 🔍 Automated Fraud & Calculation Checks
- 📊 Excel / CSV Accounting Export
""")

# Main Layout
col1, col2 = st.columns([1, 1], gap="medium")

with col1:
    st.subheader("1. Upload Invoice / Receipt")
    uploaded_file = st.file_uploader(
        "Upload Image Format: PNG, JPG, JPEG, WEBP",
        type=["png", "jpg", "jpeg", "webp"]
    )

    if uploaded_file:
        st.success(f"File uploaded: `{uploaded_file.name}`")
        st.image(uploaded_file, caption="Document Preview", use_column_width=True)
        process_button = st.button("🚀 Process Invoice with Gemini Agent", type="primary")

with col2:
    st.subheader("2. Audit & Extraction Results")

    # HERE IS THE CODE SECTION YOU ASKED ABOUT:
    if uploaded_file and 'process_button' in locals() and process_button:
        with st.spinner("Analyzing document with Gemini 2.5 Flash & Running Audit Rules..."):
            
            # Call Gemini Agent Function
            extracted_json = parse_invoice_with_gemini(client, uploaded_file)

            if extracted_json:
                # Run Business Logic Checks
                status, warnings = run_business_validations(extracted_json)

                # Show Status Flag
                status_color = "green" if status == "Approved" else "orange" if status == "Needs Review" else "red"
                st.markdown(f"### Workflow Status: :{status_color}[{status}]")

                # Show Warnings if any
                if warnings:
                    st.markdown("#### Audit Warnings & Flags:")
                    for warn in warnings:
                        st.warning(warn)

                # Display Summary Metrics
                m1, m2, m3 = st.columns(3)
                m1.metric("Vendor", extracted_json.get("vendor_name", "N/A"))
                m2.metric("Invoice #", extracted_json.get("invoice_number", "N/A"))
                m3.metric(
                    "Total Amount", 
                    f"{extracted_json.get('currency', '$')} {extracted_json.get('total_amount', 0.0):,.2f}"
                )

                # Display Extracted Line Items
                st.markdown("#### Extracted Line Items")
                line_items = extracted_json.get("line_items", [])
                if line_items:
                    df_items = pd.DataFrame(line_items)
                    st.dataframe(df_items, use_container_width=True)

                # View JSON Data
                with st.expander("🔍 View Structured JSON Output"):
                    st.json(extracted_json)

                # Excel Export Button
                st.markdown("---")
                excel_file = convert_df_to_excel(extracted_json)
                st.download_button(
                    label="📥 Download Structured Excel Report",
                    data=excel_file,
                    file_name=f"Invoice_{extracted_json.get('invoice_number', 'export')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    else:
        st.info("Upload an invoice image on the left and click **Process** to see agent results.")