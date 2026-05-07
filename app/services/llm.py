import google.generativeai as genai
import time
import re
import json

def extract_json(prompt: str, criteria_list: list = None):
    """
    EXTRACT_JSON now accepts 'criteria_list' to prevent the 
    '1 positional argument but 2 given' error.
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    for attempt in range(5):
        try:
            response = model.generate_content(prompt)
            if response and response.text:
                return parse_json_safely(response.text)
        except Exception as e:
            if "429" in str(e):
                # Logic: Wait 25s, 45s, etc. to clear the 1-minute quota window
                wait_time = (attempt + 1) * 20 + 5
                print(f"!!! Quota Hit. Waiting {wait_time}s for real data...")
                time.sleep(wait_time)
            else:
                print(f"LLM Error: {str(e)}")
                time.sleep(5)
    
    # Final error if retries fail
    raise Exception("AI is overloaded. Please wait 1 minute and click Upload again.")

def parse_json_safely(text):
    try:
        clean = re.sub(r'```json|```', '', text).strip()
        match = re.search(r'\[.*\]|\{.*\}', clean, re.DOTALL)
        return json.loads(match.group()) if match else []
    except:
        return []