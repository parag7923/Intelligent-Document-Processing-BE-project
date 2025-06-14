import streamlit as st
import os
import zipfile
import fitz
import difflib
import shutil
import easyocr

# --- Constants ---
BACKEND_URL = "https://legendary-xylophone-x5x4jqv59w5q2wrg-5000.app.github.dev/"
UPLOAD_DIR = "test"

# --- Utilities ---
def extract_zip(file_path, extract_to=UPLOAD_DIR):
    if not os.path.exists(extract_to):
        os.makedirs(extract_to)
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def extract_text_from_pdf(pdf_path, reader, progress_bar, progress_text, current, total):
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                text += page_text.strip() + '\n'
            else:
                image = page.get_pixmap()
                image.save('temp_page.png')
                result = reader.readtext('temp_page.png', detail=0)
                text += ' '.join(result) + '\n'
                os.remove('temp_page.png')
        doc.close()
    except Exception as e:
        st.error(f"❗ Error processing {os.path.basename(pdf_path)}: {e}")
    progress_bar.progress(min(current / total, 1.0))
    progress_text.text(f"📄 Processing {current}/{total} - {os.path.basename(pdf_path)}")
    return text

def detect_plagiarism(texts, file_names):
    plagiarism_results = []
    no_plagiarism_files = []
    n = len(texts)
    for i in range(n):
        for j in range(i + 1, n):
            similarity = difflib.SequenceMatcher(None, texts[i], texts[j]).ratio()
            if similarity > 0.7:
                plagiarism_results.append((file_names[i], file_names[j], similarity))
            else:
                no_plagiarism_files.extend([file_names[i], file_names[j]])
    no_plagiarism_files = list(set(no_plagiarism_files) - set([x[0] for x in plagiarism_results]) - set([x[1] for x in plagiarism_results]))
    return plagiarism_results, no_plagiarism_files

# --- Main App ---
def main():
    st.set_page_config(page_title="Assignement Plagiarism Detector", layout="wide")

    # Back to Main
    st.markdown(
        f"""<div style="margin-bottom: 15px;">
            <a href="{BACKEND_URL}" style="padding: 10px 20px; text-decoration: none; color: #007bff; border: 1px solid #007bff; border-radius: 5px;">&lt; Back to Main</a>
        </div>""", unsafe_allow_html=True
    )

    # Header
    st.markdown(
        """<div style='width: 100%; background-color: #007BFF; padding: 20px; border-radius: 8px; text-align: center; color: white; font-size: 32px; font-weight: bold;'>
            🔍 Assignement Plagiarism Detector
        </div>""", unsafe_allow_html=True
    )

    # File Upload Section
    st.subheader("📂 Upload Your ZIP File")
    uploaded_file = st.file_uploader("Upload a ZIP file containing PDF documents", type=["zip"], help="Ensure the ZIP contains only PDF files.")

    if uploaded_file:
        zip_path = "uploaded.zip"
        with open(zip_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("✅ File uploaded successfully! Click on **Start Processing** to begin.")

        if st.button("🚀 Start Processing"):
            extract_zip(zip_path, UPLOAD_DIR)
            pdf_files = [f for f in os.listdir(UPLOAD_DIR) if f.lower().endswith('.pdf')]

            if not pdf_files:
                st.error("⚠ No PDF files found in the ZIP. Please upload valid PDF documents.")
                return

            st.info(f"📁 **Total PDF files detected:** {len(pdf_files)}")
            reader = easyocr.Reader(['en'])

            progress_bar = st.progress(0)
            progress_text = st.empty()

            texts = []
            for i, pdf in enumerate(pdf_files):
                pdf_path = os.path.join(UPLOAD_DIR, pdf)
                extracted = extract_text_from_pdf(pdf_path, reader, progress_bar, progress_text, i + 1, len(pdf_files))
                texts.append(extracted)

            st.success("✅ All files processed successfully!")

            results, no_plagiarism_files = detect_plagiarism(texts, pdf_files)

            if results:
                st.subheader("🚩 Detected Plagiarized Files:")
                for file1, file2, sim in results:
                    st.markdown(
                        f"<p style='font-size:18px;'><strong>{file1}</strong> & <strong>{file2}</strong> - Similarity: <strong>{sim*100:.2f}%</strong></p>",
                        unsafe_allow_html=True
                    )
            else:
                st.success("🎉 No plagiarism detected among the uploaded files.")

            if no_plagiarism_files:
                st.subheader("✅ Files with No Plagiarism Detected:")
                for file in no_plagiarism_files:
                    st.markdown(f"<p style='font-size:18px;'>📘 <strong>{file}</strong></p>", unsafe_allow_html=True)

            # Cleanup
            shutil.rmtree(UPLOAD_DIR)
            os.remove(zip_path)

if __name__ == "__main__":
    main()
