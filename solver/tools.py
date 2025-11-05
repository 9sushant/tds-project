import httpx
import pandas as pd
import pdfplumber
import io
import base64
import matplotlib.pyplot as plt
from playwright.async_api import async_playwright
import os

async def scrape_page_content(url: str) -> str:
    """
    Uses Playwright to scrape a JS-rendered page and return its FULL HTML content.
    """
    print(f"Scraping: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle")
            
            # --- THIS IS THE FIX ---
            # We get the full HTML content, not just the text.
            # This preserves <a> tags and other structures.
            content = await page.content()
            # ---------------------
            
            await browser.close()
            return content
        except Exception as e:
            await browser.close()
            print(f"Error scraping {url}: {e}")
            return f"Error: Could not scrape page. {e}"

# ---
# All other functions in this file (download_file, get_text_from_pdf, etc.)
# are PERFECT. Do not change them.
# ---

async def download_file(url: str, save_path: str = "temp_data") -> str:
    """
    Downloads a file and saves it locally. Returns the file path.
    """
    print(f"Downloading: {url}")
    os.makedirs(save_path, exist_ok=True) 
    
    # Simple way to get a unique-ish filename
    filename = url.split('/')[-1].split('?')[0] # Clean query params
    
    if '.' not in filename:
        filename = f"data_{filename.split('-')[-1]}"

    filepath = f"{save_path}/{filename}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        with open(filepath, 'wb') as f:
            f.write(response.content)
    return filepath

def get_text_from_pdf(file_path: str) -> str:
    """
    Extracts all text from a PDF file.
    """
    print(f"Reading PDF: {file_path}")
    all_text = ""
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            all_text += f"--- PDF Page {i+1} ---\n{page.extract_text()}\n\n"
    return all_text

def get_text_from_csv(file_path: str) -> str:
    """
    Reads a CSV and returns it as a string (to be fed to the LLM).
    """
    print(f"Reading CSV: {file_path}")
    df = pd.read_csv(file_path)
    return df.to_string()

def generate_visualization(data_dict: dict) -> str:
    """
    Generates a simple bar chart from a dict and returns a base64 string.
    """
    print("Generating visualization...")
    try:
        keys = list(data_dict.keys())
        values = list(data_dict.values())
        
        fig, ax = plt.subplots()
        ax.bar(keys, values)
        ax.set_title("Analysis Result")
        ax.set_ylabel("Value")
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close(fig)
        return img_base64
    except Exception as e:
        print(f"Error generating chart: {e}")
        return f"Error: {e}"