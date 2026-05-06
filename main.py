import sys
import os
import json
from dotenv import load_dotenv
from agents import (
    ExtractorAgent, PlannerAgent, ReviewerAgent, 
    StorytellerAgent, CharacterAgent, JudgeAgent, 
    FeedbackClassifierAgent, ActionDeciderAgent
)

"""
Before submitting the assignment, describe here in a few sentences what you would have built next if you spent 2 more hours on this project:

1) Right now the story changes scenes after 10 messages max because sometimes it starts to loop - I would have built an Agent to prevent the looping and find more appropriate end of scenes.
2) And I would have built tool calls for Agents to be able to add characters (like the director Agent can't add characters, but it could if it had the tool to do so), 
and maybe tools to make changes in the environment which would have consequences in the story.
3) I would have also enabled web search in the Agents to be able to get more factual information which they would need to use in their responses.
4) Finally, I would have built a better user interface. 

"""
MAX_JUDGE_RETRY = 3
MAX_MESSAGES_PER_SCENE = int(os.environ.get("MAX_MESSAGES_PER_SCENE", "10"))
MAX_MESSAGES_TOTAL = int(os.environ.get("MAX_MESSAGES_TOTAL", "300"))

class StoryState:
    def __init__(self):
        self.elements = None
        self.plan = None
        self.current_scene_index = 0
        self.story_history = [] # For LLM context (includes internal notes)
        self.printable_story = [] # For final output
        self.characters = {}
        self.active_adjustments = []

    def get_full_story(self):
        return "\n\n".join(self.story_history)

    def get_recent_history(self, n=5):
        return "\n\n".join(self.story_history[-n:])

def get_judged_output(agent, prompt, scene_goal, judge):
    """Gets output from an agent and has it judged, retrying on failure."""
    for i in range(MAX_JUDGE_RETRY):
        output = agent.call(prompt)
        judgment = judge.judge(output, scene_goal)
        if judgment.approved:
            return judgment.corrected_version or output
        else:
            print(f"[Debug - Judge Feedback for {agent.name}] Rejected: {judgment.feedback}. Retrying...")
            prompt += f"\n\n[Judge Feedback]: {judgment.feedback}. Please revise your output."
    
    print(f"[Debug - System] Agent {agent.name} failed to get approval after {MAX_JUDGE_RETRY} attempts. Skipping.")
    return None

def get_judged_storyteller_output(agent, prompt, scene_goal, judge):
    """Gets structured output from storyteller and has it judged."""
    for i in range(MAX_JUDGE_RETRY):
        output_obj = agent.tell(prompt)
        judgment = judge.judge(output_obj.narrative_block, scene_goal)
        if judgment.approved:
            narrative = judgment.corrected_version or output_obj.narrative_block
            return narrative, output_obj.prompt_for_next_actor
        else:
            print(f"[Debug - Judge Feedback for Storyteller] Rejected: {judgment.feedback}. Retrying...")
            prompt += f"\n\n[Judge Feedback]: {judgment.feedback}. Please revise your narrative block."
            
    print(f"[Debug - System] Storyteller failed to get approval after {MAX_JUDGE_RETRY} attempts. Skipping.")
    return None, None

def main():
    load_dotenv()
    
    print("--- Welcome to the Multi-Agent Bedtime Storyteller! ---")
    user_request = input("What kind of story should we tell today? ")
    
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    state = StoryState()
    total_messages_used = 0
    
    # 1. Extraction
    print("\n[Extractor] Analyzing your request...")
    extractor = ExtractorAgent()
    state.elements = extractor.extract(user_request)
    print(f"Extracted Theme: {state.elements.theme.value}")
    print(f"Characters: {', '.join([c.name for c in state.elements.characters])}")

    # 2. Planning & Review
    print("\n[Planner] Creating a story arc...")
    planner = PlannerAgent(state.elements.theme)
    reviewer = ReviewerAgent()
    
    for _ in range(MAX_JUDGE_RETRY):
        plan = planner.plan(state.elements.model_dump_json())
        review_result = reviewer.review(plan.model_dump_json())
        if review_result.approved:
            state.plan = plan
            print("Plan approved!\n")
            print("--- Story Plan ---")
            for i, s in enumerate(state.plan.scenes):
                print(f"Scene {i+1}: {s.title}")
                print(f"  Description: {s.description}")
                print(f"  Characters: {', '.join(s.characters_involved)}")
                print(f"  Goal: {s.goal}\n")
            break
        else:
            print(f"Plan rejected: {review_result.feedback}")
    
    if not state.plan:
        print("Failed to generate an approved plan. Exiting.")
        sys.exit(1)

    # 3. Initialize Agents
    storyteller = StorytellerAgent()
    judge = JudgeAgent()
    feedback_classifier = FeedbackClassifierAgent()
    action_decider = ActionDeciderAgent()
    
    for char_data in state.elements.characters:
        state.characters[char_data.name] = CharacterAgent(char_data)

    # 4. Execution Loop
    print("\n--- Starting the Story ---\n")
    
    while state.current_scene_index < len(state.plan.scenes):
        scene = state.plan.scenes[state.current_scene_index]
        print(f"--- Scene {state.current_scene_index + 1}: {scene.title} ---")
        
        next_actor_name = "Storyteller" # Start each scene with the storyteller
        next_actor_reasoning = "Introduce the scene."
        scene_messages_used = 0

        while next_actor_name != "SceneComplete":
            # Safety guard: if the director never decides to end the scene,
            # stop after a fixed number of turns to avoid infinite loops.
            if scene_messages_used >= MAX_MESSAGES_PER_SCENE or total_messages_used >= MAX_MESSAGES_TOTAL:
                safety_msg = (
                    "[System: Safety limit reached (max turns). Ending scene to prevent an infinite loop.]"
                )
                print(f"\n{safety_msg}")
                state.story_history.append(safety_msg)
                next_actor_name = "SceneComplete"
                break

            scene_messages_used += 1
            total_messages_used += 1

            # Check for User Feedback
            user_input = input(f"\n(Press Enter to continue, or type feedback/actions): ").strip()
            if user_input:
                classification = feedback_classifier.classify(user_input, scene.description)
                if classification.classification == 'plan_change':
                    print("\n[System] Re-planning story based on your feedback...")
                    state.plan.scenes[state.current_scene_index:] = planner.plan(json.dumps({
                        "elements": state.elements.model_dump(), 
                        "current_history": state.get_full_story(), 
                        "feedback": user_input,
                        "starting_scene_index": state.current_scene_index
                    })).scenes
                    print(f"New plan integrated. Continuing with the story.")
                    scene = state.plan.scenes[state.current_scene_index]
                    # After a major re-plan, the storyteller should set the new scene
                    next_actor_name = "Storyteller"
                    next_actor_reasoning = "Set up the new scene."
                else:
                    print(f"\n[System] Adding adjustment: {classification.summary}")
                    # This adjustment will be picked up by the next agent's prompt
                    state.story_history.append(f"[User Adjustment]: {classification.summary}")

            # Decide who acts next
            if next_actor_name == "Storyteller":
                actor = storyteller
                prompt = f"Scene Description: {scene.description}\nScene Goal: {scene.goal}\nCharacters Present: {', '.join(scene.characters_involved)}\nDirector's Cue: {next_actor_reasoning}\nRecent History: {state.get_recent_history()}"
                
                content, next_actor_prompt = get_judged_storyteller_output(actor, prompt, scene.goal, judge)
                if content:
                    print(f"\n{content}")
                    state.story_history.append(content)
                    state.printable_story.append(content)
                    if next_actor_prompt:
                        state.story_history.append(f"[Storyteller Prompt to Actor]: {next_actor_prompt}")
            else:
                actor = state.characters.get(next_actor_name)
                prompt = f"Scene Description: {scene.description}\nScene Goal: {scene.goal}\nCharacters Present: {', '.join(scene.characters_involved)}\nDirector's Cue: {next_actor_reasoning}\nRecent History: {state.get_recent_history()}"

                content = get_judged_output(actor, prompt, scene.goal, judge)
                if content:
                    print(f"\n{content}")
                    state.story_history.append(content)
                    state.printable_story.append(content)

            # Decide next actor
            decision = action_decider.decide(
                scene_goal=scene.goal,
                story_history=state.get_recent_history(),
                character_names=scene.characters_involved
            )
            next_actor_name = decision.next_actor
            next_actor_reasoning = decision.reasoning
            print(f"\n[Debug - Director] Next up: {next_actor_name}. Reason: {decision.reasoning}")

        state.current_scene_index += 1

    print("\n--- The End ---")
    print("\nFull Story Summary:")
    print("\n\n".join(state.printable_story))

if __name__ == "__main__":
    main()
