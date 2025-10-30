# prompt_eval.py — produce prompt_evaluation.json using your Gemini API key
# Usage:
#   export GEMINI_API_KEY=...
#   python prompt_eval.py
import os, json, sys, re
from google import genai
from dotenv import load_dotenv

load_dotenv()

EVAL_INSTRUCTION = """
You are a Prompt Evaluation Assistant.

Evaluate the student's prompt on these criteria:

1. ✅ Explicit Reasoning Instructions
2. ✅ Structured Output Format
3. ✅ Separation of Reasoning and Tools
4. ✅ Conversation Loop Support
5. ✅ Instructional Framing
6. ✅ Internal Self-Checks
7. ✅ Reasoning Type Awareness
8. ✅ Error Handling or Fallbacks
9. ✅ Overall Clarity and Robustness

Return ONLY a valid JSON object in this exact format (no extra text, no code fences):

{
  "explicit_reasoning": <true|false>,
  "structured_output": <true|false>,
  "tool_separation": <true|false>,
  "conversation_loop": <true|false>,
  "instructional_framing": <true|false>,
  "internal_self_checks": <true|false>,
  "reasoning_type_awareness": <true|false>,
  "fallbacks": <true|false>,
  "overall_clarity": "<short sentence>"
}
"""

def coerce_json(s: str) -> dict:
    # Strip code fences if the model adds them
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.IGNORECASE|re.DOTALL).strip()
    # Find the first {...} JSON object if any surrounding noise
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if m:
        s = m.group(0)
    return json.loads(s)

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Set GEMINI_API_KEY env var"); sys.exit(1)

    if not os.path.exists("final_prompt.txt"):
        print("Missing final_prompt.txt"); sys.exit(1)

    with open("final_prompt.txt", "r", encoding="utf-8") as f:
        student_prompt = f.read()

    client = genai.Client(api_key=api_key)

    contents = f"{EVAL_INSTRUCTION}\n\nNow evaluate the following prompt:\n\n{student_prompt}"
    resp = client.models.generate_content(model="gemini-2.0-flash", contents=contents)
    raw = (resp.text or "").strip()

    try:
        data = coerce_json(raw)
    except Exception as e:
        print("Model returned non-JSON response:\n", raw[:500])
        raise

    with open("prompt_evaluation.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("Wrote prompt_evaluation.json")
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()