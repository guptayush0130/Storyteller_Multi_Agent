# Hippocratic AI Demo: Multi-Agent Bedtime Storytelling System

This project is an interactive bedtime story generation system for ages 5-10, implemented with a multi-agent orchestration pattern:
- A **Planner** builds a structured story arc (scenes + goals).
- A **Storyteller** narrates and cues character turns.
- **Character agents** contribute in-role actions/dialogue.
- A **Judge** gatekeeps quality/safety and retries low-quality outputs.
- A **Director (ActionDecider)** chooses who speaks next.
- A **FeedbackClassifier** routes user feedback into either small adjustments or full replanning.

The project supports two interfaces:
- **Streamlit application** (`app.py`) for web-based interaction.
- **CLI application** (`main.py`) for terminal-based interaction.

## How to run

### Install

```bash
pip install -r requirements.txt
```

### Configure environment

```bash
export OPENAI_API_KEY='your-api-key-here'
```

Optional safety limits (prevents infinite looping if a scene does not terminate naturally):

```bash
export MAX_MESSAGES_PER_SCENE=30
export MAX_MESSAGES_TOTAL=300
```

### Run Streamlit UI

```bash
streamlit run app.py
```

### Run CLI

```bash
python main.py
```


## Detailed architecture

### High-level phases

- **Phase 1 - Extraction**
  - Input: user story request
  - Output: structured story elements (theme + character specifications)

- **Phase 2 - Planning and review**
  - The Planner generates a multi-scene story arc (scene titles, descriptions, involved characters, and explicit goals).
  - A Reviewer acts as a gatekeeper: if the plan isn’t acceptable, the Planner retries (up to a fixed retry count).

- **Phase 3 - Execution (per-scene loop)**
  - The story runs scene-by-scene.
  - Within each scene, the Director repeatedly selects which agent acts next:
    - **Storyteller** narrates and can provide an internal cue for the next actor.
    - **Character agent** responds in-character.
  - Every generated block is sent through the **Judge**, which can approve, correct, or reject and request retries.
  - The loop ends when the Director chooses `SceneComplete` (or when the safety limit forces an end).

- **Phase 4 - Live feedback**
  - User feedback is classified:
    - **Scene adjustment**: appended into history as an instruction to influence future turns.
    - **Plan change**: triggers replanning from the current scene onward while preserving history/context.

### Component responsibilities (agents)

- **ExtractorAgent**
  - Parses the initial user request into structured story elements (theme + characters).

- **PlannerAgent**
  - Generates an ordered list of scenes with clear goals (a story arc).

- **ReviewerAgent**
  - Validates the proposed plan for appropriateness and coherence; rejects plans that need revision.

- **StorytellerAgent**
  - Produces the main narration (`narrative_block`) and, optionally, a private cue for the next actor.

- **CharacterAgent(s)**
  - One agent per extracted character; generates in-character contributions consistent with the scene and recent history.

- **JudgeAgent**
  - Evaluates every narrative block against the current **scene goal**; can approve, provide corrections, or reject and force retries.

- **ActionDeciderAgent (Director)**
  - Chooses the next actor given:
    - the scene goal
    - recent story history
    - available characters
  - May choose `SceneComplete` to advance to the next scene.

- **FeedbackClassifierAgent**
  - Classifies user input as either a small adjustment or a plan change.

### Data flow / block diagram

See `block_diagram.md` for the Mermaid diagram showing prompt/data flow across agents.