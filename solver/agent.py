import httpx
import os
import time
from urllib.parse import urljoin  # <-- This is the fix for relative URLs
from .planner import get_plan_from_llm, get_answer_from_llm
from .tools import (
    scrape_page_content, 
    download_file, 
    get_text_from_csv, 
    get_text_from_pdf, 
    generate_visualization
)

# Load secrets for the agent to use
MY_EMAIL = os.environ.get("MY_EMAIL")
MY_SECRET = os.environ.get("MY_SECRET")

async def run_quiz_solver_background(email: str, secret: str, initial_url: str):
    """
    The main, recursive-style function that solves the quiz.
    """
    
    current_url = initial_url
    start_time = time.time()
    
    # The quiz loop
    while current_url:
        # Check for 3-minute timeout
        if (time.time() - start_time) > 170: # 170 seconds, just under 3 mins
            print("Nearing 3-minute timeout. Stopping task.")
            break
            
        print(f"\n--- New Task ---")
        print(f"Processing URL: {current_url}")
        
        try:
            # 1. Scrape the page
            page_context = await scrape_page_content(current_url)
            if page_context.startswith("Error:"):
                print(f"Failed to scrape: {page_context}")
                break
            
            # 2. Get a plan from the LLM
            plan = await get_plan_from_llm(page_context)
            if "error" in plan:
                print(f"Failed to get plan: {plan['error']}")
                break
            
            print(f"Plan received: {plan.get('question')}")
            
            question = plan.get("question")
            data_url = plan.get("data_url")
            submit_url = plan.get("submit_url")

            # --- FIX #1: This joins the base URL (current_url) with any relative paths ---
            if data_url:
                data_url = urljoin(current_url, data_url)
            if submit_url:
                submit_url = urljoin(current_url, submit_url)
            
            # --- FIX #2: This passes the page text to the Answerer ---
            # By default, the context IS the page we just scraped.
            data_context = page_context 
            
            # 3. Execute the plan (Get Data)
            # If we find a file, THEN we overwrite the context.
            if data_url:
                print(f"Data URL found, downloading: {data_url}") 
                try:
                    file_path = await download_file(data_url, "temp_data")
                    
                    if file_path.endswith('.pdf'):
                        data_context = get_text_from_pdf(file_path)
                    elif file_path.endswith('.csv'):
                        data_context = get_text_from_csv(file_path)
                    else:
                        # Fallback for audio or unknown files
                        # We can't read them as text, so we'll just pass the path
                        # (We'll need a new tool for this later)
                        data_context = f"File downloaded to: {file_path}"
                            
                except Exception as e:
                    print(f"Failed to process file: {e}")
                    data_context = f"Error processing file: {e}" 
            
            # 4. Get the answer
            final_answer = await get_answer_from_llm(question, data_context)
            print(f"Final answer computed: {str(final_answer)[:50]}...")
            
            # 5. Submit the answer
            submission_payload = {
                "email": email,
                "secret": secret,
                "url": current_url, 
                "answer": final_answer
            }
            
            print(f"Submitting answer to: {submit_url}") # This will now be a FULL URL
            async with httpx.AsyncClient() as client:
                submit_response = await client.post(
                    submit_url, 
                    json=submission_payload,
                    timeout=30.0
                )
            
            submit_response.raise_for_status() 
            result_data = submit_response.json()
            
            # 6. Process the result
            if result_data.get("correct") == True:
                print("Answer was CORRECT.")
                current_url = result_data.get("url") 
                if not current_url:
                    print("Quiz complete! No new URL provided.")
            else:
                print(f"Answer was WRONG. Reason: {result_data.get('reason')}")
                current_url = result_data.get("url") 
                if not current_url:
                    print("Quiz ended on a wrong answer.")
            
        except Exception as e:
            print(f"---!! An unexpected error occurred in the agent loop !!---")
            print(f"Error: {e}")
            current_url = None 
            
    print("\n--- Quiz Run Finished ---")