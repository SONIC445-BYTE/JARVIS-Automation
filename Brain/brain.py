# from webscout import PhindSearch as brain


# ai = brain(
#     is_conversation=True,
#     max_tokens=800,
#     timeout=30,
#     intro='J.A.R.V.I.S',
#     filepath=r"C:\Users\chatu\Desktop\J.A.R.V.I.S\chat_hystory.txt",
#     update_file=True,
#     proxies={},
#     history_offset=10250,
#     act=None,
# )

# def Main_Brain(text):
#     r = ai.chat(text)
#     return r 

from AgentCore.llm_engine import LLMEngine
from os import getcwd

def Main_Brain(text):
    try:
        # Try using local LLM first
        llm = LLMEngine()
        if llm.is_available():
            # Simple context management: just send the text for now
            # TODO: Load chat_history.txt for context if needed
            response = llm.generate(text, system="You are JARVIS, a helpful AI assistant. Answer concisely.")
            return response.text
        else:
            # Fallback to legacy TurboSeek if LLM unavailable
            from webscout import TurboSeek
            filepath = f"{getcwd()}\\chat_hystory.txt"
            ai = TurboSeek(filepath=filepath, is_conversation=True)
            res = ai.chat(text)
            return res
    except Exception as e:
        print(f"Error in Main_Brain: {e}")
        return "I apologize, but I am unable to process that request at the moment."
