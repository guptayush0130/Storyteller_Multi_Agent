import os
import time
import json
import streamlit as st
from dotenv import load_dotenv
from agents import (
    ExtractorAgent, PlannerAgent, ReviewerAgent, 
    StorytellerAgent, CharacterAgent, JudgeAgent, 
    ActionDeciderAgent, FeedbackClassifierAgent
)

load_dotenv()

MAX_JUDGE_RETRY = 3
MAX_MESSAGES_PER_SCENE = int(os.environ.get("MAX_MESSAGES_PER_SCENE", "10"))
MAX_MESSAGES_TOTAL = int(os.environ.get("MAX_MESSAGES_TOTAL", "300"))

st.set_page_config(page_title="Bedtime Storyteller", page_icon="book", layout="wide")

class StoryState:
    def __init__(self):
        self.elements = None
        self.plan = None
        self.current_scene_index = 0
        self.story_history = []
        self.printable_story = []
        self.characters = {}
        self.active_adjustments = []
        # Safety counters to prevent infinite director loops.
        self.scene_messages_used = 0
        self.total_messages_used = 0

    def get_full_story(self):
        return "\n\n".join(self.story_history)

    def get_recent_history(self, n=5):
        return "\n\n".join(self.story_history[-n:])

def get_judged_output(agent, prompt, scene_goal, judge):
    for i in range(MAX_JUDGE_RETRY):
        output = agent.call(prompt)
        judgment = judge.judge(output, scene_goal)
        if judgment.approved:
            return judgment.corrected_version or output
        else:
            prompt += f"\n\n[Judge Feedback]: {judgment.feedback}. Please revise your output."
    return None

def get_judged_storyteller_output(agent, prompt, scene_goal, judge):
    for i in range(MAX_JUDGE_RETRY):
        output_obj = agent.tell(prompt)
        judgment = judge.judge(output_obj.narrative_block, scene_goal)
        if judgment.approved:
            narrative = judgment.corrected_version or output_obj.narrative_block
            return narrative, output_obj.prompt_for_next_actor
        else:
            prompt += f"\n\n[Judge Feedback]: {judgment.feedback}. Please revise your narrative block."
    return None, None

def initialize_story(user_request):
    st.session_state.story_state = StoryState()
    state = st.session_state.story_state
    
    with st.spinner("Analyzing request and extracting characters..."):
        extractor = ExtractorAgent()
        state.elements = extractor.extract(user_request)
        
    with st.spinner(f"Creating a {state.elements.theme.value} story arc..."):
        planner = PlannerAgent(state.elements.theme)
        reviewer = ReviewerAgent()
        
        plan = None
        for _ in range(MAX_JUDGE_RETRY):
            temp_plan = planner.plan(state.elements.model_dump_json())
            review_result = reviewer.review(temp_plan.model_dump_json())
            if review_result.approved:
                plan = temp_plan
                break
                
        if not plan:
            st.error("Failed to generate a safe and approved story plan.")
            return False
            
        state.plan = plan

    st.session_state.planner = planner
    st.session_state.storyteller = StorytellerAgent()
    st.session_state.judge = JudgeAgent()
    st.session_state.action_decider = ActionDeciderAgent()
    st.session_state.feedback_classifier = FeedbackClassifierAgent()
    
    for c in state.elements.characters:
        state.characters[c.name] = CharacterAgent(c)

    st.session_state.next_actor_name = "Storyteller"
    st.session_state.next_actor_reasoning = "Introduce the scene."
    st.session_state.phase = "executing"
    st.session_state.ui_messages.append({"role": "system", "content": "Story plan approved! Let's begin."})
    return True

def play_next_turn():
    state = st.session_state.story_state
    if state.current_scene_index >= len(state.plan.scenes):
        st.session_state.phase = "finished"
        return

    scene = state.plan.scenes[state.current_scene_index]
    
    # Check if we need to move to next scene
    if st.session_state.next_actor_name == "SceneComplete":
        state.current_scene_index += 1
        state.scene_messages_used = 0
        if state.current_scene_index < len(state.plan.scenes):
            scene = state.plan.scenes[state.current_scene_index]
            st.session_state.next_actor_name = "Storyteller"
            st.session_state.next_actor_reasoning = "Introduce the new scene."
            st.session_state.ui_messages.append({"role": "system", "content": f"**Moving to Scene {state.current_scene_index + 1}: {scene.title}**"})
            return # Wait for user to click continue again for the new scene
        else:
            st.session_state.phase = "finished"
            return

    actor_name = st.session_state.next_actor_name
    reasoning = st.session_state.next_actor_reasoning
    
    # Safety guard to avoid infinite loops when the director never ends the scene.
    if state.scene_messages_used >= MAX_MESSAGES_PER_SCENE or state.total_messages_used >= MAX_MESSAGES_TOTAL:
        safety_msg = "[System: Safety limit reached (max turns). Ending scene to prevent an infinite loop.]"
        st.session_state.ui_messages.append({"role": "system", "content": safety_msg})
        state.story_history.append(safety_msg)
        st.session_state.next_actor_name = "SceneComplete"
        st.session_state.next_actor_reasoning = "Reached safety limit."
        return

    recent_history = state.get_recent_history()
    
    with st.spinner(f"{actor_name} is thinking..."):
        if actor_name == "Storyteller":
            actor = st.session_state.storyteller
            prompt = f"Scene Description: {scene.description}\nScene Goal: {scene.goal}\nCharacters Present: {', '.join(scene.characters_involved)}\nDirector's Cue: {reasoning}\nRecent History: {recent_history}"
            content, next_actor_prompt = get_judged_storyteller_output(actor, prompt, scene.goal, st.session_state.judge)
            if content:
                state.story_history.append(content)
                state.printable_story.append(content)
                st.session_state.ui_messages.append({"role": "assistant", "content": content})
                if next_actor_prompt:
                    state.story_history.append(f"[Storyteller Prompt to Actor]: {next_actor_prompt}")
            else:
                state.story_history.append("[System: Storyteller failed to act. Moving on.]")
        else:
            actor = state.characters.get(actor_name)
            if actor:
                prompt = f"Scene Description: {scene.description}\nScene Goal: {scene.goal}\nCharacters Present: {', '.join(scene.characters_involved)}\nDirector's Cue: {reasoning}\nRecent History: {recent_history}"
                content = get_judged_output(actor, prompt, scene.goal, st.session_state.judge)
                if content:
                    state.story_history.append(content)
                    state.printable_story.append(content)
                    st.session_state.ui_messages.append({"role": "assistant", "content": content})
                else:
                    state.story_history.append(f"[System: {actor_name} failed to act. Storyteller should take over.]")
            else:
                state.story_history.append(f"[System: Actor '{actor_name}' is not an available character. Storyteller should take over.]")

        # Count this turn toward the safety limit regardless of whether the actor succeeded.
        state.scene_messages_used += 1
        state.total_messages_used += 1

        # Decide next actor
        decision = st.session_state.action_decider.decide(
            scene_goal=scene.goal,
            story_history=state.get_recent_history(),
            character_names=scene.characters_involved
        )
        st.session_state.next_actor_name = decision.next_actor
        st.session_state.next_actor_reasoning = decision.reasoning

def handle_feedback(user_feedback):
    state = st.session_state.story_state
    scene = state.plan.scenes[state.current_scene_index]
    
    with st.spinner("Processing feedback..."):
        classification = st.session_state.feedback_classifier.classify(user_feedback, scene.description)
        if classification.classification == 'plan_change':
            st.session_state.ui_messages.append({"role": "system", "content": "Re-planning story based on your feedback..."})
            state.plan.scenes[state.current_scene_index:] = st.session_state.planner.plan(json.dumps({
                "elements": state.elements.model_dump(), 
                "current_history": state.get_full_story(), 
                "feedback": user_feedback,
                "starting_scene_index": state.current_scene_index
            })).scenes
            st.session_state.next_actor_name = "Storyteller"
            st.session_state.next_actor_reasoning = "Set up the new scene after the plan change."
            st.session_state.ui_messages.append({"role": "system", "content": f"**New plan integrated. Continuing with Scene {state.current_scene_index + 1}: {state.plan.scenes[state.current_scene_index].title}**"})
        else:
            st.session_state.ui_messages.append({"role": "system", "content": f"Adding adjustment: {classification.summary}"})
            state.story_history.append(f"[User Adjustment]: {classification.summary}")

# --- Streamlit UI ---

st.title("Interactive Bedtime Storyteller")

if "phase" not in st.session_state:
    st.session_state.phase = "init"
    st.session_state.ui_messages = []

if st.session_state.phase == "init":
    st.markdown("Enter a prompt to begin the story. You will be able to provide feedback or just continue reading as it goes!")
    user_request = st.text_area("What kind of story should we tell today?", placeholder="A brave squirrel who loses his favorite nut...")
    if st.button("Start Story", type="primary"):
        if not os.environ.get("OPENAI_API_KEY"):
            st.error("Please set your OPENAI_API_KEY environment variable before running.")
            st.stop()
        if initialize_story(user_request):
            st.rerun()

elif st.session_state.phase in ["executing", "finished"]:
    # Display Story Plan in sidebar
    with st.sidebar:
        st.header("Story Plan")
        state = st.session_state.story_state
        for i, s in enumerate(state.plan.scenes):
            if i == state.current_scene_index:
                st.markdown(f"**Scene {i+1} (Current): {s.title}**")
            else:
                st.markdown(f"**Scene {i+1}: {s.title}**")
            st.caption(s.description)
            
    # Display Chat History
    for msg in st.session_state.ui_messages:
        if msg["role"] == "system":
            # Keep scene/status updates, but hide internal safety-limit errors.
            if "Safety limit reached (max turns)" not in msg["content"]:
                st.info(msg["content"])
        elif msg["role"] == "assistant":
            st.write(msg["content"])
        elif msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])

    if st.session_state.phase == "executing":
        feedback = st.chat_input("Type feedback or suggestions here to change the story...")
        if feedback:
            st.session_state.ui_messages.append({"role": "user", "content": feedback})
            handle_feedback(feedback)
            play_next_turn()
            st.rerun()
        else:
            # Auto-continue the story
            play_next_turn()
            time.sleep(1) # Add a small delay for readability
            st.rerun()
            
    if st.session_state.phase == "finished":
        st.success("The End! Hope you enjoyed the story.")
        if st.button("Start a New Story"):
            st.session_state.phase = "init"
            st.session_state.ui_messages = []
            st.rerun()
