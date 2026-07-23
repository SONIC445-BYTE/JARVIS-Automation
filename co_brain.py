from Automation.Automation_Brain import Auto_main_brain,clear_file
from NetHyTechSTT.listen import listen
from TextToSpeech.Fast_DF_TTS import speak
import threading
from Data.DLG_Data import online_dlg,offline_dlg
import random
from Automation.Battery import battery_Alert
from Time_Operations.brain import input_manage,input_manage_Alam
from Brain.brain import Main_Brain
from Features.create_file import create_file
from Vision.Vbrain import *
from Vision.MVbrain import *
from Weather_Check.check_weather import get_weather_by_address
from Whatsapp_automation.wa import send_msg_wa
from TextToImage.gen_image import generate_image
from Features.mike_health import mike_health
from Features.speaker_health import speaker_health_test
from Features.br_persentage import check_br_persentage
from Features.set_br import set_brightness_windows
from Features.set_get_volume import *
from Features.check_running_app import *

# Import AgentCore for ODAV-based execution. Deferred to first actual
# use (see _agent_core_available()/get_agent() below) rather than at
# module load: AgentCore.agent_brain eagerly imports pyautogui (via
# ui_perception/action_executor/checkpoint), so importing it here at
# co_brain.py's module level meant importing co_brain.py -- and
# therefore jarvis.py, which imports co_brain.py -- always paid that
# cost, even for a test that never issues a single AgentCore-routed
# command. Same pattern as AgentCore/__init__.py's and
# Automation/Automation_Brain.py's Phase 2g import-decoupling fixes.
_AGENT_CORE_AVAILABLE = None  # None = not yet determined


def _agent_core_available() -> bool:
    global _AGENT_CORE_AVAILABLE
    if _AGENT_CORE_AVAILABLE is None:
        try:
            from AgentCore.agent_brain import AgentBrain  # noqa: F401
            _AGENT_CORE_AVAILABLE = True
            print("DEBUG: AgentCore loaded successfully!")
        except ImportError as e:
            print(f"WARNING: AgentCore not available: {e}")
            _AGENT_CORE_AVAILABLE = False
    return _AGENT_CORE_AVAILABLE

numbers = ["1:","2:","3:","4:","5:","6:","7:","8:","9:"]
spl_numbers = ["11:","12:"]

ran_online_dlg = random.choice(online_dlg)
ran_offline_dlg = random.choice(offline_dlg)

# Initialize AgentBrain for non-deterministic commands
_agent_brain = None
_intent_parser = None

def get_agent():
    """Lazy initialize AgentBrain."""
    global _agent_brain, _intent_parser, _ui_context
    if _agent_core_available() and _agent_brain is None:
        from AgentCore.agent_brain import AgentBrain
        from AgentCore.intent_parser import IntentParser
        from AgentCore.ui_agent.context.ui_context import UIContext
        _agent_brain = AgentBrain()
        _ui_context = UIContext()
        # Pass UIContext to parser
        _intent_parser = IntentParser(ui_context=_ui_context)
    return _agent_brain, _intent_parser

def requires_agent_core(text: str) -> bool:
    """
    Determine if command requires AgentCore (ODAV) or legacy system.

    RULE: Route based on DETERMINISM, not complexity.
    - Deterministic command → legacy code
    - Any command requiring UI reasoning → AgentCore
    """
    if not _agent_core_available():
        return False
    
    # Non-deterministic patterns that require UI reasoning
    non_deterministic_patterns = [
        # Position-based selection
        "top-right", "top-left", "bottom-right", "bottom-left",
        "first", "second", "third", "1st", "2nd", "3rd",
        "latest", "newest", "recent",
        # Multi-app operations
        "upload", "download", "transfer", "send to",
        "from my", "to my", "from the", "to the",
        # Complex navigation
        "select the", "choose the", "click on the",
        "search results", "and then", "and click",
        # File operations with context
        "create a folder", "rename the", "move the file",
    ]
    
    text_lower = text.lower()
    for pattern in non_deterministic_patterns:
        if pattern in text_lower:
            print(f"DEBUG: Non-deterministic pattern found: '{pattern}' -> AgentCore")
            return True
    
    # Multi-step commands
    if " and " in text_lower and ("open" in text_lower or "go to" in text_lower):
        if any(action in text_lower for action in ["type", "paste", "search", "click", "select"]):
            print("DEBUG: Multi-step command detected -> AgentCore")
            return True
    
    return False

def check_inputs():
    output_text = ""
    last_processed = ""  # Track what we've already processed
    while True:
        with open("input.txt","r") as file:
            input_text = file.read().lower().strip()
        
        # Skip if no change
        if input_text == output_text:
            continue
            
        output_text = input_text
        
        # Handle appended text: only process NEW content
        if last_processed and input_text.startswith(last_processed):
            new_content = input_text[len(last_processed):].strip()
            if new_content:
                print(f"DEBUG: New appended content: '{new_content}'")
                input_text = new_content
            else:
                continue  # No new content
        
        # Skip empty
        if not input_text:
            continue
            
        print(f"DEBUG check_inputs processing: '{input_text}'")

        # --- Canonical Pipeline Hook ---
        try:
            import os
            import yaml
            import time
            pipeline_enabled = False
            flag_path = "feature_flags/pipeline_enforce.yaml"
            if os.path.exists(flag_path):
                with open(flag_path, "r") as f:
                    cfg = yaml.safe_load(f) or {}
                    pipeline_enabled = cfg.get("enabled", False)
            
            if pipeline_enabled:
                print("[Pipeline] Enforcing canonical pipeline...")
                from AgentCore.pipeline.intent_router import IntentRouter
                from AgentCore.pipeline.policy_gate import PolicyGate
                from AgentCore.pipeline.engine_router import EngineRouter
                from AgentCore.pipeline.context_builder import ContextBuilder
                from AgentCore.pipeline.pipeline_trace import PipelineTrace
                from AgentCore.pipeline.audit_logger import AuditLogger
                from TextToSpeech.Fast_DF_TTS import speak
                
                # Initialize
                trace = PipelineTrace.new_from_input(output_text, output_text)
                router = IntentRouter()
                policy = PolicyGate()
                engine_router_svc = EngineRouter()
                ctx_builder = ContextBuilder()
                audit = AuditLogger()
                
                # 1. Intent
                intent_res = router.classify(output_text)
                trace.attach_intent(intent_res)
                print(f"[Pipeline] Intent: {intent_res['intent']}")
                
                # 2. Policy Pre
                policy_pre = policy.pre_check(intent_res, {})
                trace.attach_policy_pre(policy_pre)
                
                if not policy_pre["allowed"]:
                    msg = policy_pre.get("block_reasons", ["Blocked"])[0]
                    print(f"[Pipeline] Blocked: {msg}")
                    speak(f"I cannot do that: {msg}")
                    audit.write(trace)
                    continue 
                
                # 3. Engine Select
                route = engine_router_svc.select(intent_res)
                trace.attach_engine_routing(route)
                
                # 4. Context
                ctx = ctx_builder.build(output_text, {"ts": time.time()}, intent_res)
                
                # 5. Execute
                print(f"[Pipeline] Routing to {route['engine_name']}...")
                result = route["handler"](output_text, ctx)
                trace.attach_engine_result(route["engine_name"], result)
                
                # 6. Policy Post
                policy_post = policy.post_check(result)
                trace.attach_policy_post(policy_post)
                
                # 7. Deliver
                if route["engine_name"] == "Main_Brain":
                        speak(result)
                
                trace.mark_delivered()
                audit.write(trace)
                
                # Clear input file to prevent loop
                with open("input.txt", "w") as f:
                    f.write("")
                output_text = "" 
                continue # PIPELINE SUCCESS - SKIP LEGACY
                
        except Exception as e:
            print(f"[Pipeline] Error (Fallback to Hybrid): {e}")
            # Fall through to legacy/hybrid logic below
        # -------------------------------
        
        if output_text.startswith("tell me"):
            output_text = output_text.replace(" p.m.","PM")
            output_text = output_text.replace(" a.m.","AM")
            if "11:" in output_text or "12:" in output_text:
                input_manage(output_text)
                clear_file()
            else:
                for number in numbers:
                    if number in output_text:
                        output_text = output_text.replace(number,f"0{number}")
                        input_manage(output_text)
                        clear_file()
                           
        elif output_text.startswith("set alarm"):
            output_text = output_text.replace(" p.m.","PM")
            output_text = output_text.replace(" a.m.","AM")
            if "11:" in output_text or "12:" in output_text:
                input_manage_Alam(output_text)
                clear_file()
            else:
                for number in numbers:
                    if number in output_text:
                        output_text = output_text.replace(number,f"0{number}")
                        input_manage_Alam(output_text)
                        clear_file()

        elif "send message on whatsapp" in output_text:
            print("DEBUG: WhatsApp trigger detected!")
            send_msg_wa()

        elif "jarvis" in output_text:
            # Clean common variations from the text
            cleaned_text = output_text.lower()
            # Remove common wake word patterns (speech-to-text variations)
            for phrase in ["hey jarvis", "hi jarvis", "is jarvis", "jarvis", "hey", "hi"]:
                cleaned_text = cleaned_text.replace(phrase, "").strip()
            
            print(f"DEBUG: Original text: '{output_text}'")
            print(f"DEBUG: Cleaned text: '{cleaned_text}'")
            
            # ====== DETERMINISM-BASED ROUTING ======
            # Route based on whether command requires UI reasoning
            if requires_agent_core(cleaned_text):
                # Non-deterministic: Use ODAV AgentCore
                print(f"DEBUG: Routing to AgentCore (ODAV): '{cleaned_text}'")
                agent, parser = get_agent()
                if agent:
                    # Get fresh UI context
                    from AgentCore.ui_agent.context.ui_context import UIContext
                    ctx = UIContext()
                    result = agent.execute_command(cleaned_text, context={"ui_context": ctx})
                    if result.get("status") == "success":
                        speak(result.get("message", "Task completed"))
                    else:
                        speak(f"I encountered an issue: {result.get('message', 'Unknown error')}")
                else:
                    print("DEBUG: AgentCore not available, falling back to legacy")
                    Auto_main_brain(cleaned_text)
            
            # Check for automation commands using 'in' for more flexibility
            elif "open" in cleaned_text or \
               "close" in cleaned_text or \
               "play" in cleaned_text or \
               "search" in cleaned_text or \
               "check battery" in cleaned_text or \
               "check running application" in cleaned_text:
                
                # Deterministic: Use legacy system
                print(f"DEBUG: Routing to Legacy (deterministic): '{cleaned_text}'")
                Auto_main_brain(cleaned_text)
            
            else:
                f = open('log.txt','a')
                f.write('\n'+'You : '+ output_text)
                response = Main_Brain(output_text)
                f.write('\n'+'jarvis : '+ response)
                speak(response)
            
            # Track processed content
            last_processed = output_text

        elif output_text.startswith("create"):
            if "file" in output_text:
                create_file(output_text)

        elif "what is this" in output_text or "what can you see" in output_text:
            image_path = "captured_image.png"
            if capture_image_and_save(image_path):
                encoded_image = encode_image_to_base64(image_path)
                answer = vision_brain(encoded_image)
                speak(answer)

        elif "what is in front of mobile camera" in output_text or "what can you see use mobile camera" in output_text:
            image_path = "captured_image.png"
            if capture_image_and_save(image_path):
                encoded_image = encode_image_to_base64(image_path)
                answer = mobile_vision_brain(encoded_image)
                speak(answer)

        elif "check weather" in output_text:
            text = output_text.replace("check weather in","")
            ans = get_weather_by_address(text)
            speak(ans)

        elif "generate image" in output_text:
            text = output_text.replace("generate image","")
            text = text.strip()
            generate_image(text)
            speak("image generated successfully")

        elif "check mike" in output_text or "check mike health" in output_text or "check microphone" in output_text:
            mike_health()

        elif "check speaker health" in output_text or "check speaker" in output_text:
            speaker_health_test()

        elif "check brightness percentage" in output_text:
            check_br_persentage()

        elif "set brightness percentage" in output_text:
            set = output_text.replace("set brightness percentage","")
            set_brightness_windows(int(set))

        elif "check volume level" in output_text:
            get_volume_windows()
             
        elif "set volume level" in output_text:
            set = output_text.replace("set volume level","")
            set = set.replace("%","")
            set_volume_windows(int(set))

        elif "check running application" in output_text:
            check_running_app()
            
        # --- Code Engine Hook ---
        elif any(k in output_text for k in ["write code", "write a code", "generate code", "architect", "create a script", "code for", "function for", "calculate", "program", "algorithm"]):
            # Lazy load CodeEngine if not already available
            try:
                import os
                from AgentCore.code_engine.engine import CodeEngine
                code_engine = CodeEngine()
                print(f"DEBUG: Routing to CodeEngine: '{output_text}'")
                # Force execute (dry_run=False) so files are written
                result = code_engine.handle_command(output_text, context={"user": "owner", "cwd": os.getcwd()}, dry_run=False)
                
                if result.get("dry_run", False):
                    summary = result.get('patch_summary','(see diff)')
                    print(f"[CODE_ENGINE] Dry-run: patch prepared at {summary}")
                    speak(f"I have prepared a dry run for your code request.")
                else:
                    path = result.get('file_path')
                    print(f"[CODE_ENGINE] File written: {path}")
                    speak(f"I have written the code to {path}")
            except Exception as e:
                print(f"DEBUG: CodeEngine failed: {e}")
                speak("I tried to generate code but encountered an error.")
        # ------------------------

        else:
            # Heuristic: Check if this looks like an automation command
            # If it contains common automation keywords, send to Auto_main_brain
            # Otherwise, treat as conversation and send to Main_Brain
            automation_keywords = [
                "open", "close", "play", "search", "check", "set", 
                "scroll", "click", "press", "type", "send", 
                "mute", "unmute", "volume", "brightness", "battery"
            ]
            
            is_automation = any(k in output_text.lower() for k in automation_keywords)
            
            if is_automation:
                Auto_main_brain(output_text)
            else:
                # Conversational Fallback
                try:
                    f = open('log.txt','a')
                    f.write('\n'+'You : '+ output_text)
                    response = Main_Brain(output_text)
                    f.write('\n'+'jarvis : '+ response)
                    speak(response)
                except Exception as e:
                    print(f"Error in Main_Brain: {e}")
                    Auto_main_brain(output_text) # Ultimate fallback
                
                

def Jarvis():
    clear_file()
    t1 = threading.Thread(target=listen)
    t2 = threading.Thread(target=check_inputs)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

