import streamlit as st
import fitz  # PyMuPDF
import json
from google import genai
from google.genai import types

st.set_page_config(page_title="Earnings Call Analyzer", layout="wide")
st.title("📝 Earnings Call & Management Summary Tool")
st.markdown("**Call Analyzer**")

# Initialize client with API key from Streamlit secrets
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

uploaded_files = st.file_uploader(
    "Upload Earnings Call Transcripts or MD&A (PDFs)",
    type=["pdf"],
    accept_multiple_files=True,
    help="You can upload multiple PDFs (e.g., Q1, Q2, Q3)"
)

# Helper to safely convert string → list (fixes Gemini's occasional string output)
def safe_list(field):
    if isinstance(field, list):
        return field
    if isinstance(field, str):
        return [field.strip()] if field and field.strip() else ["Not mentioned"]
    return ["Not mentioned"]

if st.button("Generate Summary", type="primary") and uploaded_files:
    all_summaries = {}

    for uploaded_file in uploaded_files:
        with st.spinner(f"Analyzing **{uploaded_file.name}**..."):
            # Extract text
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text() + "\n"

            # NEW: Check text length
            if len(text) < 1000:
                st.warning(f"Short text detected in {uploaded_file.name} (likely cover pages only). Summary may be limited.")

            # Updated prompt - always generate summary based on available content
            prompt = f"""You are an expert equity research analyst. Analyze the following earnings call transcript or management discussion.

Return **only** valid JSON with this exact structure (no extra text):
{{
  "executive_summary": "A concise 4-6 sentence high-level overview of the key messages, tone, performance highlights, and strategic outlook from the call. Always generate a summary based on the provided text, even if limited (e.g., summarize cover info if that's all there is).",
  "tone": "optimistic" | "cautious" | "neutral" | "pessimistic",
  "confidence_level": "high" | "medium" | "low",
  "key_positives": ["bullet point 1", "bullet point 2", ...],
  "key_concerns": ["bullet point 1", "bullet point 2", ...],
  "forward_guidance": "Clear summary of revenue, margin, capex, or other guidance",
  "capacity_utilization_trends": "Trends mentioned or 'Not mentioned'",
  "new_growth_initiatives": ["initiative 1", "initiative 2", ...]
}}

Rules:
- Base everything strictly on the provided text only.
- If any section is missing, use "Not mentioned".
- **All array fields (key_positives, key_concerns, new_growth_initiatives) MUST be valid JSON arrays of strings. Never return a plain string.**
- Do not hallucinate.
- Be concise and analyst-friendly.

Transcript:
{text[:180000]}
"""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )

            summary = json.loads(response.text)
            all_summaries[uploaded_file.name] = summary

    st.success(f"✅ Analysis Complete! ({len(uploaded_files)} file(s) processed)")

    # ── DISPLAY SUMMARIES ──
    for filename, summary in all_summaries.items():
        st.divider()
        st.subheader(f"📄 Summary for: **{filename}**")

        # Executive Summary (always visible)
        st.subheader("Executive Summary")
        st.markdown(summary.get("executive_summary", "Not generated"))

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Management Tone", summary.get("tone", "N/A").title())
            st.metric("Confidence Level", summary.get("confidence_level", "N/A").title())
        with col2:
            st.subheader("Forward Guidance")
            st.write(summary.get("forward_guidance", "Not mentioned"))

        st.subheader("Key Positives")
        for point in safe_list(summary.get("key_positives", [])):
            st.success(f"• {point}")

        st.subheader("Key Concerns / Challenges")
        for point in safe_list(summary.get("key_concerns", [])):
            st.error(f"• {point}")

        st.subheader("Capacity Utilization Trends")
        st.write(summary.get("capacity_utilization_trends", "Not mentioned"))

        st.subheader("New Growth Initiatives")
        for point in safe_list(summary.get("new_growth_initiatives", [])):
            st.info(f"• {point}")

    # ── DOWNLOAD BUTTON ──
    st.divider()
    json_data = json.dumps(all_summaries, indent=4, ensure_ascii=False)
    st.download_button(
        label="📥 Download All Summaries as JSON",
        data=json_data,
        file_name="earnings_call_summaries.json",
        mime="application/json",
        use_container_width=True
    )


