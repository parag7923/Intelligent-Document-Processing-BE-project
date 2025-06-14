import streamlit as st
import numpy as np
import base64
import torch
import easyocr
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader
from pdf2image import convert_from_path
from PIL import Image
import os
import re
import shutil
import tempfile
import atexit
from docx import Document
import textwrap

# ✅ Streamlit page config
st.set_page_config(page_title="Summary Generator", layout="wide")

# --- Constants ---
BACKEND_URL = "https://legendary-xylophone-x5x4jqv59w5q2wrg-5000.app.github.dev/"
TEMP_UPLOAD_FOLDER = "temp_uploads_summary"
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 128
SHORT_SUMMARY_RATIO = 0.4
LONG_SUMMARY_RATIO = 0.6
SUMMARY_BUFFER = 50
WORDS_PER_LINE = 20
MAX_PAGES = 50 # 🔒 Backend-only trick: limit pages to 3

# --- Load models ---
@st.cache_resource
def load_models():
    tokenizer = AutoTokenizer.from_pretrained("facebook/bart-large-cnn")
    model = AutoModelForSeq2SeqLM.from_pretrained("facebook/bart-large-cnn", device_map="auto", torch_dtype=torch.float32)
    return tokenizer, model

tokenizer, model = load_models()
ocr_reader = easyocr.Reader(['en'], gpu=False)

# --- Page selection logic (only in backend) ---
def get_first_n_pages(pages, n=MAX_PAGES):
    return pages[:min(n, len(pages))]

# --- Text-based PDF processing ---
def file_preprocessing(file_path):
    try:
        loader = PyPDFLoader(file_path)
        all_pages = loader.load_and_split()
        selected_pages = get_first_n_pages(all_pages)
        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        chunks = splitter.split_documents(selected_pages)
        cleaned_chunks = []
        for doc in chunks:
            content = doc.page_content
            content = re.sub(r"[^a-zA-Z0-9\s.,?!'\"()\[\]{}:;+-]", "", content)
            content = re.sub(r"\s+", " ", content).strip()
            if content:
                cleaned_chunks.append(content)
        return cleaned_chunks
    except Exception as e:
        st.error(f"Error during text-based PDF processing: {e}")
        return []

# --- OCR-based image/pdf text extraction ---
def extract_text_from_image_or_pdf(file_path, file_type):
    texts = []
    try:
        if file_type == "pdf":
            images = convert_from_path(file_path)
        else:
            images = [Image.open(file_path)]
        selected_images = images[:MAX_PAGES]
        for img in selected_images:
            result = ocr_reader.readtext(np.array(img), detail=0, paragraph=True)
            joined = " ".join(result)
            joined = re.sub(r"[^a-zA-Z0-9\s.,?!'\"()\[\]{}:;+-]", "", joined)
            joined = re.sub(r"\s+", " ", joined).strip()
            if joined:
                texts.append(joined)
    except Exception as e:
        st.error(f"OCR failed: {e}")
    return texts

# --- DOCX word file extraction ---
def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        text = " ".join([p.text for p in doc.paragraphs if p.text.strip()])
        text = re.sub(r"[^a-zA-Z0-9\s.,?!'\"()\[\]{}:;+-]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return [text] if text else []
    except Exception as e:
        st.error(f"Word file processing failed: {e}")
        return []

# --- Summarization pipeline ---
def summarize_texts(texts, summary_ratio):
    summarizer = pipeline("summarization", model=model, tokenizer=tokenizer, truncation=True)
    final_summary = ""

    for text in texts:
        try:
            wrapped_chunks = textwrap.wrap(text, width=1000, break_long_words=False)

            for chunk in wrapped_chunks:
                input_ids = tokenizer.encode(chunk, truncation=True)
                input_len = len(input_ids)

                if input_len < 30:
                    continue

                max_len = min(512, max(60, int(input_len * summary_ratio) + SUMMARY_BUFFER))
                min_len = max(20, int(max_len * 0.3))

                result = summarizer(chunk, max_length=max_len, min_length=min_len)
                final_summary += result[0]['summary_text'] + "\n"

        except Exception as e:
            st.warning(f"Summarization failed: {e}")

    return final_summary.strip()

# --- Display PDF inline ---
def displayPDF(file_path):
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    return f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600"></iframe>'

# --- Save uploaded file ---
def save_uploaded_file(uploaded_file):
    file_path = os.path.join(TEMP_UPLOAD_FOLDER, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path

# --- Format summary text ---
def format_summary_for_download(summary):
    words = summary.split()
    return "\n".join(" ".join(words[i:i + WORDS_PER_LINE]) for i in range(0, len(words), WORDS_PER_LINE))

# --- Main UI ---
def main():
    st.markdown(
        f"""<div style="margin-bottom: 15px;">
            <a href="{BACKEND_URL}" style="padding: 10px 20px; text-decoration: none; color: #007bff; border: 1px solid #007bff; border-radius: 5px;">&lt; Back to Main</a>
        </div>""", unsafe_allow_html=True
    )

    st.markdown(
        """<div style='width: 100%; background-color: #007BFF; padding: 20px; border-radius: 8px; text-align: center; color: white; font-size: 32px; font-weight: bold;'>
            📝 Summary Generator
        </div>""", unsafe_allow_html=True
    )

    st.subheader("📄 Upload your Document")
    uploaded_file = st.file_uploader("Upload PDF, Image or Word file", type=["pdf", "png", "jpg", "jpeg", "docx", "doc"])

    if uploaded_file is not None:
        file_path = save_uploaded_file(uploaded_file)
        file_ext = uploaded_file.name.lower().split('.')[-1]

        col1, col2 = st.columns([0.4, 0.6])
        with col1:
            st.subheader("📁 Preview")
            if file_ext == "pdf":
                st.markdown(displayPDF(file_path), unsafe_allow_html=True)
            elif file_ext in ["jpg", "jpeg", "png"]:
                st.image(file_path, use_column_width=True)
            else:
                st.info("Preview not available for Word files but you can still summarize the document")

        with col2:
            st.subheader("⚙️ Summary Settings")
            if st.button("Generate Summary", type="primary"):
                with st.spinner("🔍 Processing and summarizing document..."):
                    if file_ext in ["jpg", "jpeg", "png"]:
                        processed_texts = extract_text_from_image_or_pdf(file_path, "image")
                    elif file_ext == "pdf":
                        processed_texts = file_preprocessing(file_path)
                        if not processed_texts:
                            processed_texts = extract_text_from_image_or_pdf(file_path, "pdf")
                    elif file_ext in ["doc", "docx"]:
                        processed_texts = extract_text_from_docx(file_path)
                    else:
                        st.error("Unsupported file type.")
                        return

                    if processed_texts:
                        summary = summarize_texts(processed_texts, SHORT_SUMMARY_RATIO)

                        st.subheader("📝 Summary:")
                        st.markdown(
                            f"<div style='padding: 20px; background-color: rgba(61, 213, 109, 0.2); border-radius: 8px; white-space: pre-wrap;'>{summary}</div>",
                            unsafe_allow_html=True
                        )

                        formatted = format_summary_for_download(summary)
                        st.download_button("Download Summary as TXT", data=formatted.encode("utf-8"), file_name="summary.txt", mime="text/plain")
                    else:
                        st.error("❌ No text could be extracted.")

        if os.path.exists(file_path):
            os.remove(file_path)

# --- Clean up temp folder on app exit ---
def cleanup_temp_folder():
    if os.path.exists(TEMP_UPLOAD_FOLDER):
        shutil.rmtree(TEMP_UPLOAD_FOLDER)

atexit.register(cleanup_temp_folder)

if __name__ == "__main__":
    main()
