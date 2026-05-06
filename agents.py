import os
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel
from openai import OpenAI

# --- Enums ---
class Theme(str, Enum):
    romance = "romance"
    fantasy = "fantasy"
    thriller = "thriller"
    horror = "horror"
    mystery = "mystery"
    mythology = "mythology"
    adventure = "adventure"
    other = "other"

# --- Pydantic Models for Structured Outputs ---

class Character(BaseModel):
    name: str
    description: str
    personality: str

class Extraction(BaseModel):
    characters: List[Character]
    theme: Theme
    setting: str
    relationships: str

class Scene(BaseModel):
    title: str
    description: str
    characters_involved: List[str]
    goal: str

class StoryPlan(BaseModel):
    scenes: List[Scene]

class ReviewResult(BaseModel):
    approved: bool
    feedback: str
    suggestions: List[str]

class Judgment(BaseModel):
    approved: bool
    feedback: str
    corrected_version: Optional[str] = None

class FeedbackClassification(BaseModel):
    classification: str # 'plan_change' or 'scene_adjustment'
    summary: str

class StorytellerOutput(BaseModel):
    narrative_block: str
    prompt_for_next_actor: str

class ActionDecision(BaseModel):
    next_actor: str # Name of character, 'Storyteller', or 'SceneComplete'
    reasoning: str

# --- Agent Base Class and Implementations ---

class StoryAgent:
    def __init__(self, name, system_prompt, model="gpt-4o-2024-08-06"):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def call(self, user_prompt, temperature=0.7):
        if not user_prompt:
            user_prompt = "Proceed with the next step."

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content

    def call_structured(self, user_prompt, response_format):
        if not user_prompt:
            user_prompt = "Proceed with the next step."

        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            text_format=response_format
        )
        
        for output in response.output:
            if output.type == "message":
                for item in output.content:
                    if item.type == "refusal":
                        raise Exception(f"Model refusal: {item.refusal}")
                    if item.parsed:
                        return item.parsed
        
        raise Exception("Failed to get parsed output from Responses API")

class ExtractorAgent(StoryAgent):
    def __init__(self):
        system_prompt = """
        Role: You are an expert story analyst. 
        Task: Extract the core elements of a bedtime story request for children ages 5-10 into structured data.
        Context: The user will provide a prompt. You must identify characters, setting, theme, and relationships exactly as requested by the user. Do NOT hallucinate or invent characters or locations that are not implied by the user's prompt. Choose the most appropriate theme from the given enum options.
        Example Character Description:
        - "A brave 7-year-old squirrel with a bushy tail who loves collecting acorns but is afraid of heights."
        - "A wise old owl with silver feathers who wears tiny spectacles and always speaks in riddles."
        Make sure the descriptions and personalities are highly detailed and vivid.
        
        Example Output JSON:
        {
            "characters": [
                {
                    "name": "Sparky",
                    "description": "A brave 7-year-old squirrel with a bushy tail who loves collecting acorns but is afraid of heights.",
                    "personality": "Curious, energetic, but sometimes anxious when facing new challenges."
                }
            ],
            "theme": "adventure",
            "setting": "A massive, ancient oak tree in the center of the Whispering Woods.",
            "relationships": "Sparky is best friends with the wise old owl who lives on the top branch."
        }
        """
        super().__init__("Extractor", system_prompt)

    def extract(self, user_request) -> Extraction:
        return self.call_structured(user_request, Extraction)

class PlannerAgent(StoryAgent):
    def __init__(self, theme_enum: Theme):
        theme_value = theme_enum.value if hasattr(theme_enum, 'value') else str(theme_enum)
        theme_prompts = {
            "fantasy": "You are a modern J.K. Rowling writing a magical next-generation fantasy for children ages 5-10.",
            "adventure": "You are a modern Rick Riordan writing an action-packed next-generation adventure for children ages 5-10.",
            "thriller": "You are a modern Dan Brown writing a next-generation thriller for children ages 5-10. Your framework relies on the Three C's: The Contract (you make promises and you fulfill them), The Clock (a ticking deadline), and a Crucible (the reason why the hero cannot leave).",
            "mystery": "You are a modern Agatha Christie writing an engaging puzzle-filled mystery for children ages 5-10.",
            "mythology": "You are a modern Neil Gaiman writing a legendary mythological tale adapted for children ages 5-10.",
            "horror": "You are a modern R.L. Stine writing a spooky but safe (age-appropriate) tale for children ages 5-10.",
            "romance": "You are a modern storyteller writing a sweet, fairy-tale romance focused on friendship and loyalty for children ages 5-10.",
            "other": "You are a creative children's storyteller writing a unique tale for children ages 5-10."
        }
        style = theme_prompts.get(theme_value, theme_prompts["other"])
        
        system_prompt = f"""
        Role: {style}
        Task: Create a detailed, scene-by-scene story arc.
        Context: You will receive a set of story elements. If 'current_history' is provided, it means you are RE-PLANNING a story in progress from the 'starting_scene_index'. Your new plan should seamlessly continue from where the last one left off, incorporating the user's feedback to shape the *rest* of the story. Do not regenerate the entire story from the beginning. Generate a new list of scenes for the remainder of the story. Otherwise, construct a new narrative using the Hero's Journey framework, adapted for a young audience.
        
        Hero's Journey Framework (Adapted):
        1. Call to Adventure: The hero's normal life is disrupted by a sudden challenge or invitation.
        2. Meeting the Mentor: The hero gains guidance, wisdom, or a magical item from a wiser figure.
        3. Crossing the Threshold: The hero leaves their familiar world and enters the unknown.
        4. Tests, Allies, and Enemies: The hero faces challenges, meets friends, and encounters obstacles.
        5. The Ordeal: The biggest challenge or turning point in the middle of the story.
        6. The Reward: The hero overcomes the Ordeal and gains something valuable (a lesson, item, or friend).
        7. The Road Back: The hero begins the journey home or to the final destination.
        8. Resurrection / Final Challenge: One last test where the hero uses everything they've learned.
        9. Return with the Elixir: The hero returns home, changed for the better, bringing hope or peace.
        
        Example Scene Output Goal: "The hero must retrieve the glowing acorn without waking the sleeping bear, learning the value of silence and patience."
        
        Example Output JSON:
        {{
            "scenes": [
                {{
                    "title": "1. The Missing Acorn",
                    "description": "Sparky wakes up to find his magical golden acorn missing from his nest.",
                    "characters_involved": ["Sparky"],
                    "goal": "Call to Adventure: Establish the mystery and Sparky's motivation to leave his nest."
                }},
                {{
                    "title": "2. A Wise Word",
                    "description": "Sparky visits the wise old owl to ask for advice and receives a special glowing leaf.",
                    "characters_involved": ["Sparky", "Owl"],
                    "goal": "Meeting the Mentor: Sparky receives guidance and a helpful item."
                }},
                {{
                    "title": "3. Leaving the Tree",
                    "description": "Sparky climbs down to the forest floor, a place he has never been before.",
                    "characters_involved": ["Sparky"],
                    "goal": "Crossing the Threshold: Sparky enters the unknown world."
                }},
                {{
                    "title": "4. The River Crossing",
                    "description": "Sparky meets a friendly turtle who helps him cross a fast-moving river, but they have to avoid a grumpy frog.",
                    "characters_involved": ["Sparky", "Turtle", "Frog"],
                    "goal": "Tests, Allies, and Enemies: Sparky makes a friend and faces a minor obstacle."
                }},
                {{
                    "title": "5. The Dark Cave",
                    "description": "Sparky must enter a dark cave to find the shadow-creature who took the acorn, facing his fear of the dark.",
                    "characters_involved": ["Sparky", "Shadow Creature"],
                    "goal": "The Ordeal: Sparky faces his biggest fear to achieve his goal."
                }},
                {{
                    "title": "6. The Golden Acorn",
                    "description": "Sparky realizes the shadow-creature was just lonely and trades the glowing leaf for his golden acorn.",
                    "characters_involved": ["Sparky", "Shadow Creature"],
                    "goal": "The Reward: Sparky retrieves the acorn by showing kindness."
                }},
                {{
                    "title": "7. The Climb Back",
                    "description": "Sparky hurries back up the massive oak tree as a sudden rainstorm begins.",
                    "characters_involved": ["Sparky"],
                    "goal": "The Road Back: The journey home begins with a new sense of urgency."
                }},
                {{
                    "title": "8. The Slippery Branch",
                    "description": "Just before his nest, Sparky slips, but he uses his new bravery to pull himself up.",
                    "characters_involved": ["Sparky"],
                    "goal": "Resurrection / Final Challenge: Sparky proves he is braver than before."
                }},
                {{
                    "title": "9. Home Sweet Home",
                    "description": "Sparky places the acorn back in his nest, realizing he doesn't need to be afraid of the forest anymore.",
                    "characters_involved": ["Sparky"],
                    "goal": "Return with the Elixir: Sparky returns home changed, bringing newfound courage."
                }}
            ]
        }}
        """
        super().__init__("Planner", system_prompt)

    def plan(self, story_elements_str) -> StoryPlan:
        prompt = f"Create a plan for a story with these elements: {story_elements_str}"
        return self.call_structured(prompt, StoryPlan)

class ReviewerAgent(StoryAgent):
    def __init__(self):
        system_prompt = """
        Role: You are a child development expert and editor.
        Task: Review the provided story plan for children ages 5-10.
        Context: The plan must be highly engaging but MUST strictly adhere to the following safety boundaries for 5-10 year olds:
        1. Explicit Material: ABSOLUTELY NO sexual content, profanity, vulgarity, or substance abuse.
        2. Violence: NO graphic realism, blood, or gore. Violence should be "cartoonish" or slapstick. NO realistic weapons (e.g., firearms); use fantasy tools like magic wands.
        3. Fear/Scare: Use "safe scares" (e.g., fantasy monsters, ghosts) rather than real-world threats (e.g., kidnappings, home intrusions). Every scary moment MUST resolve with a return to safety.
        4. Threats & Victims: Threats must be external (dragons, spells), never internal or mature (mental illness, abuse). Children must never be shown in extreme peril or harmed by trusted figures (parents, teachers).
        5. Resolution: Order must be restored by the end.
        
        Example Output JSON:
        {
            "approved": false,
            "feedback": "The ordeal features a realistic kidnapping which violates the 'safe scare' rule for 5-year-olds.",
            "suggestions": ["Change the kidnapping to a magical maze the hero gets lost in, and have a friendly firefly guide them out."]
        }
        """
        super().__init__("Reviewer", system_prompt)

    def review(self, plan_str) -> ReviewResult:
        return self.call_structured(f"Review this plan: {plan_str}", ReviewResult)

class StorytellerAgent(StoryAgent):
    def __init__(self):
        system_prompt = """
        Role: You are the main Storyteller and director.
        Task: Narrate the story vividly and direct the characters based on the scene plan.
        Context: You set the scene, describe the environment, and prompt characters. Do NOT speak for the characters. Only include the specific characters designated for this scene; do not introduce random bystanders. Separate your response into the 'narrative_block' (the actual story text) and 'prompt_for_next_actor' (the internal instruction for the next character). IMPORTANT: Keep your narrative blocks very short and fast-paced (MAX 2-3 sentences). Move the story forward quickly.
        
        Example Output JSON:
        {
            "narrative_block": "The forest grew dark as the sun set. The wind whispered through the leaves, casting long, dancing shadows on the ground.",
            "prompt_for_next_actor": "'Sparky the Squirrel', what do you do next when you hear a strange rustling sound?"
        }
        """
        super().__init__("Storyteller", system_prompt)
        
    def tell(self, prompt) -> StorytellerOutput:
        return self.call_structured(prompt, StorytellerOutput)

class CharacterAgent(StoryAgent):
    def __init__(self, char_data: Character):
        system_prompt = f"""
        Role: You are {char_data.name}.
        Task: Respond with your dialogue and actions when prompted by the Storyteller.
        Context: You must stay in character. Keep language simple and engaging for kids 5-10. Write your response in the THIRD PERSON as if it is a paragraph in a storybook. DO NOT use first-person narration (e.g., say "Sparky jumped" instead of "I jump") and do not include internal thoughts. DO NOT start your response with your name (e.g., do not write "{char_data.name}:"). The output must read seamlessly like a continuous story. IMPORTANT: Keep your responses very short (MAX 1-2 sentences) to keep the conversation snappy.
        Description: {char_data.description}
        Personality: {char_data.personality}
        Example: "Sparky nervously twitched his bushy tail. 'I... I don't think I can jump that far!' he squeaked, looking down at the ground."
        """
        super().__init__(char_data.name, system_prompt)

class JudgeAgent(StoryAgent):
    def __init__(self):
        system_prompt = """
        Role: You are the Quality Judge.
        Task: Review the latest narrative or dialogue block for quality and safety.
        Context: You must ensure the text aligns with the scene's plan, is engaging, and strictly follows safety rules for 5-10 year olds:
        1. Explicit Material: ABSOLUTELY NO sexual content, profanity, vulgarity, or substance abuse.
        2. Violence: Must be cartoonish/slapstick without blood or realistic pain. No real-world weapons.
        3. Fear: Use "safe scares" (fantasy creatures). No real-world dangers (kidnapping, burglars).
        4. Themes: No mature themes (abuse, severe illness). No trusted figures harming children.
        5. Tone: If tension is high, ensure humor or a quick resolution brings it back to a safe baseline.
        
        Example Output JSON:
        {
            "approved": false,
            "feedback": "The dialogue includes a graphic description of a sword cutting someone, violating the 'no blood/graphic realism' rule.",
            "corrected_version": "The magical sword clanged loudly against the shield, sending a burst of colorful sparks into the air!"
        }
        """
        super().__init__("Judge", system_prompt)

    def judge(self, content, scene_context) -> Judgment:
        prompt = f"Scene Context: {scene_context}\nContent to Judge: {content}"
        return self.call_structured(prompt, Judgment)

class FeedbackClassifierAgent(StoryAgent):
    def __init__(self):
        system_prompt = """
        Role: You are a feedback analyst.
        Task: Classify live user feedback into a category.
        Context: 'plan_change' means a major shift in the story. 'scene_adjustment' means a minor tweak right now.
        
        Example Output JSON:
        {
            "classification": "scene_adjustment",
            "summary": "Make the hero pick up the shiny rock."
        }
        """
        super().__init__("FeedbackClassifier", system_prompt)

    def classify(self, user_feedback, current_context) -> FeedbackClassification:
        prompt = f"Context: {current_context}\nFeedback: {user_feedback}"
        return self.call_structured(prompt, FeedbackClassification)

class ActionDeciderAgent(StoryAgent):
    def __init__(self):
        system_prompt = """
        Role: You are the story's director.
        Task: Decide which character should act next to move the story forward.
        Context: Based on the scene's goal and the story history, choose the most logical next actor. The actor MUST be 'Storyteller', 'SceneComplete', or one of the 'Available Actors' listed in the prompt. Do NOT invent characters. Do NOT force characters into roles they do not hold (e.g., do not make a main character act as a random bystander). IMPORTANT: Once the scene's goal has been reasonably addressed, you MUST immediately choose 'SceneComplete' to avoid endless looping. Do not drag out scenes.
        
        Example Output JSON:
        {
            "next_actor": "Sparky",
            "reasoning": "Sparky was just asked a question, so he should respond."
        }
        """
        super().__init__("ActionDecider", system_prompt)

    def decide(self, scene_goal, story_history, character_names) -> ActionDecision:
        prompt = f"""
        Scene Goal: {scene_goal}
        Story History:
        ---
        {story_history}
        ---
        Available Actors: {character_names + ['Storyteller']}
        
        Who should act next to best advance the scene toward its goal?
        """
        return self.call_structured(prompt, ActionDecision)
