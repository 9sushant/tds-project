import httpx
import os
import json
import re # Import regular expressions for number parsing

# Load environment variables.
AIPIPE_TOKEN = os.environ.get("AIPIPE_TOKEN")
AIPIPE_URL = "https://aipipe.org/openrouter/v1/chat/completions"

async def get_plan_from_llm(page_context: str) -> dict:
    """
    First LLM call: Takes page HTML and creates a JSON plan.
    """
    print("Calling LLM to create a plan...")
    headers = {"Authorization": f"Bearer {AIPIPE_TOKEN}"}
    
    # --- PROMPT 14: THE "HTML PARSER" ---
    # This prompt is built to read HTML, not just text.
    system_prompt = """
    You are an automated HTML parser. Your *only* job is to find three
    specific pieces of info from a webpage's HTML and return them as a JSON object.

    You MUST follow these rules:
    1.  **"question"**: Find the *literal task instruction*.
        -   First, look for text starting with "Q." (e.g., "Q. Get the secret code...").
        -   If no "Q." is found, find the main instruction by looking for keywords
            like "CSV file" and "Cutoff:".
        -   You MUST extract the *entire* instruction (e.g., "CSV file\nCutoff: 29172").
    2.  **"data_url"**: Find the URL to a *data file*.
        -   This *must* be a *literal* link from an `<a>` tag.
        -   The link *must* end in .csv, .pdf, .mp3, or .wav.
        -   (e.g., find `<a href="demo-audio-data.csv">CSV file</a>` -> "demo-audio-data.csv")
        -   If no such link is found, you MUST return `null`.
    3.  **"submit_url"**: Find the URL or path to *submit* the answer.
        This is often in the instructions (e.g., "POST your answer to /submit").
        This *must* be extracted.

    You *must* return only the JSON object. Do not add commentary.

    The JSON schema MUST be:
    {
      "question": "The literal task instruction extracted from the text.",
      "data_url": "The full URL or path extracted from the HTML (or null).",
      "analysis_plan": "A one-sentence copy of the question.",
      "submit_url": "The literal submission URL or path (e.g., /submit)."
    }
    """

    payload = {
        "model": "openai/gpt-4o", # Smartest model
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Parse this HTML and return the JSON:\n\n---\n\n{page_context}"}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(AIPIPE_URL, headers=headers, json=payload, timeout=60.0)
        
        response.raise_for_status() 
        llm_response_str = response.json()['choices'][0]['message']['content']
        plan_dict = json.loads(llm_response_str)
        
        if not plan_dict.get("submit_url"):
            raise ValueError(f"LLM failed to find a submit_url. Plan: {plan_dict}")
            
        return plan_dict

    except Exception as e:
        print(f"Error in LLM Planner: {e}")
        return {"error": str(e)}


async def get_answer_from_llm(question: str, data_context: str) -> str | int | bool | dict:
    """
    Second LLM call: Takes a question and data, returns the specific answer.
    """
    print(f"Calling LLM to get a specific answer for question: {question[:30]}...")
    headers = {"Authorization": f"Bearer {AIPIPE_TOKEN}"}

    # --- PROMPT 14: THE "SPECIALIST" (Based on screenshots) ---
    # This prompt is built from all your screenshots.
    system_prompt = f"""
    You are a specialist bot. You have two jobs.
    You must follow the rule that matches the user's question.
    Return *only* the raw answer. Do not add commentary or explanations.

    ---
    **RULE 1: SECRET CODE EXTRACTION**
    -   **If the question is:** "Q. Get the secret code from this page."
    -   **Your Job:** The data context will be HTML. Find the secret code.
        (e.g., The HTML will contain "Secret code is 29172 and not 29887.")
    -   **Your Answer:** You must find the correct code and return *only* the number.
        (e.g., 29172)
    -   Look for the code. It is there. Do not return "ANSWER_NOT_FOUND".

    ---
    **RULE 2: CSV MATH (Based on screenshots)**
    -   **If the question involves:** "CSV file" and "Cutoff"
    -   **Your Job:** The data context will be the text from a CSV file (a single column of numbers).
        The *question* will contain the cutoff (e.g., "CSV file\nCutoff: 29172").
        You must:
        1.  Parse the "question" to find the "Cutoff" number (e.g., "Cutoff: 29172" -> 29172).
        2.  Parse the `data_context` to get the list of numbers from the CSV.
        3.  Filter this list, keeping *only* the numbers *greater than* the cutoff.
        4.  Calculate the *sum* of those filtered numbers.
    -   **Your Answer:** Return *only* the final sum as a single number (e.g., 450123).

    ---
    -   If neither rule matches, or if the data is an error, return "ANSWER_NOT_FOUND".

    Question: {question}
    """
    
    payload = {
        "model": "openai/gpt-4o", # Use the smart model for math/extraction
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Data Context:\n{data_context}"}
        ]
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(AIPIPE_URL, headers=headers, json=payload, timeout=60.0)
        
        response.raise_for_status()
        
        answer = response.json()['choices'][0]['message']['content'].strip()
        
        if not answer or answer == "ANSWER_NOT_FOUND":
            return "ANSWER_NOT_FOUND"
        
        # Try to clean and convert to number if it's a number
        cleaned_answer = re.sub(r"[^0-9.]", "", answer)
        if cleaned_answer:
            try:
                return int(float(cleaned_answer))
            except ValueError:
                pass 
            
        return answer 

    except Exception as e:
        print(f"Error in LLM Answerer: {e}")
        return f"Error: {e}"