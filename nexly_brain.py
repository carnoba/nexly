import google.generativeai as genai
import os
from nexly_utils import log_activity

class NexlyBrain:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None

    def analyze_website(self, business_name, website_text):
        """Generates a personalized intro based on website content."""
        if not self.model:
            return "I was browsing your website and loved what you're doing."

        prompt = f"""
        Analyze this business website text for "{business_name}".
        Text: {website_text[:2000]}
        
        Task: Create a personalized, high-conversion opening sentence for a cold email.
        The sentence should mention a specific detail from their site to prove I'm not a bot.
        Keep it under 20 words.
        Format: Just the sentence, nothing else.
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            log_activity("Brain", "AIError", str(e), "Warning")
            return f"I noticed {business_name} online and was impressed by your services."
