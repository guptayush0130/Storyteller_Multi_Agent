# Multi-Agent Storytelling System Architecture

This diagram illustrates the multi-agent architecture and the flow of structured data within the bedtime storytelling system.

```mermaid
flowchart TD
    %% Styling Definitions
    classDef user node    fill:#f9f,stroke:#333,stroke-width:2px,color:#000
    classDef agent node   fill:#e1f5fe,stroke:#1565c0,stroke-width:2px,color:#000
    classDef engine node  fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#000
    classDef safety node  fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#000
    classDef output node  fill:#f3e5f5,stroke:#388e3c,stroke-width:2px,color:#000

    %% User Input
    User(["👤 User"]):::user

    %% Phase 1: Planning & Setup
    subgraph Planning["Phase 1: Planning & Setup"]
        Extractor["🔍 Extractor Agent<br/><small>Pydantic: Extraction</small>"]:::agent
        Planner["🗺️ Planner Agent<br/><small>Pydantic: StoryPlan</small>"]:::agent
        PlanReviewer["🛡️ Reviewer Agent<br/><small>Pydantic: ReviewResult</small>"]:::safety
    end

    %% Phase 2: Execution & Interactive Loop
    subgraph Execution["Phase 2: Execution & Generation (Interactive Loop)"]
        Director["🎬 ActionDecider Agent<br/><small>Pydantic: ActionDecision</small>"]:::engine
        Storyteller["📖 Storyteller Agent<br/><small>Pydantic: StorytellerOutput</small>"]:::agent
        CharacterAgents["🎭 Character Agents<br/><small>(Dynamic Generation)</small>"]:::agent
        Judge["⚖️ Judge Agent<br/><small>Pydantic: Judgment</small>"]:::safety
    end

    %% Phase 3: Feedback
    subgraph Feedback["Phase 3: Live Feedback"]
        FeedbackClassifier["🧠 FeedbackClassifier Agent<br/><small>Pydantic: FeedbackClassification</small>"]:::agent
    end

    FinalStory(["📚 Final Story UI"]):::output

    %% Edges - Initial Flow
    User -->|1. Initial Story Prompt| Extractor
    Extractor -->|2. Theme & Characters| Planner
    Planner -->|3. Hero's Journey Arc| PlanReviewer
    
    %% Edges - Review Loop
    PlanReviewer -.->|Rejected Plan<br/>(Retry)| Planner
    PlanReviewer -->|4. Approved Plan| Director

    %% Edges - Execution Loop
    Director -->|5. Chooses Next Actor| Storyteller
    Director -->|5. Chooses Next Actor| CharacterAgents
    
    Storyteller -->|6. Narrative Block| Judge
    CharacterAgents -->|6. Dialogue/Action| Judge

    %% Edges - Judge Loop
    Judge -.->|Rejected Content<br/>(Retry)| Storyteller
    Judge -.->|Rejected Content<br/>(Retry)| CharacterAgents
    
    %% Edges - Output & Feedback
    Judge -->|7. Approved Content| FinalStory
    FinalStory --> User
    
    User -.->|8. Live Feedback| FeedbackClassifier
    FeedbackClassifier -.->|Scene Adjustment| Director
    FeedbackClassifier -.->|Plan Change| Planner
```

## Agent Roles & Data Structures

All interactions are strictly typed using **Pydantic** to guarantee structural reliability when parsed by the OpenAI Responses API.

*   **🔍 Extractor Agent:** Analyzes the user's initial prompt and extracts elements into an `Extraction` model containing a strict Enum for the theme, detailed character descriptions, and relationships.
*   **🗺️ Planner Agent:** Adopts a specific author persona (e.g., Dan Brown, J.K. Rowling) based on the theme to generate a 9-scene Hero's Journey arc, returning a `StoryPlan`.
*   **🛡️ Reviewer Agent:** A safety gatekeeper that evaluates the `StoryPlan` for 5-10-year-old age appropriateness (e.g., converting violent threats to safe scares). Returns a `ReviewResult`.
*   **🎬 ActionDecider (Director) Agent:** Evaluates the ongoing story context and determines which entity (the Storyteller or a specific Character) should speak next. Returns an `ActionDecision`.
*   **📖 Storyteller Agent:** Acts as the narrator. Outputs a `StorytellerOutput` containing both the prose (`narrative_block`) and a hidden prompt instructing the next character (`prompt_for_next_actor`).
*   **🎭 Character Agents:** Independent agents initialized with the extracted personas. They generate seamless third-person prose matching their character description.
*   **⚖️ Judge Agent:** A continuous quality control filter. Evaluates every piece of prose for safety, engagement, and alignment, returning a `Judgment`.
*   **🧠 FeedbackClassifier Agent:** Evaluates mid-story user input, classifying it as a localized "scene adjustment" or a major "plan change" via the `FeedbackClassification` model.
