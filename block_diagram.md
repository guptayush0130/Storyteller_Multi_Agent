# Multi-Agent Storytelling System Architecture

This diagram illustrates the multi-agent architecture and the flow of structured data within the bedtime storytelling system.

```mermaid
flowchart TD
    %% Professional neutral styling
    classDef user fill:#f5f5f5,stroke:#555,stroke-width:1.5px,color:#111
    classDef process fill:#eef3f8,stroke:#2f5d8a,stroke-width:1.5px,color:#111
    classDef control fill:#f8f3e8,stroke:#8a6d2f,stroke-width:1.5px,color:#111
    classDef output fill:#edf7ed,stroke:#2f7a3d,stroke-width:1.5px,color:#111
    classDef note fill:#ffffff,stroke:#999,stroke-width:1px,color:#333

    User[User Request]:::user

    subgraph P1[Phase 1: Extraction and Planning]
        Extractor[Extractor Agent\nExtraction]
        Planner[Planner Agent\nStoryPlan]
        Reviewer[Reviewer Agent\nReviewResult]
    end

    subgraph P2[Phase 2: Scene Execution]
        Director[ActionDecider Agent\nActionDecision]:::control
        Storyteller[Storyteller Agent\nStorytellerOutput]:::process
        Characters[Character Agents\nDynamic Cast]:::process
        Judge[Judge Agent\nJudgment]:::control
    end

    subgraph P3[Phase 3: User Feedback Handling]
        Feedback[FeedbackClassifier Agent\nFeedbackClassification]
    end

    Output[Story Output]:::output
    RetryPlan[Plan retries handled internally\nuntil approved or retry limit]:::note
    RetryJudge[Content retries handled internally\nuntil approved or retry limit]:::note

    User -->|1. Prompt| Extractor
    Extractor -->|2. Elements| Planner
    Planner -->|3. Candidate Plan| Reviewer
    Reviewer -->|4. Approved Plan| Director
    Reviewer -.-> RetryPlan

    Director -->|5. Select Next Actor| Storyteller
    Director -->|5. Select Next Actor| Characters
    Storyteller -->|6. Narrative Block| Judge
    Characters -->|6. Character Block| Judge
    Judge -->|7. Approved Content| Output
    Judge -.-> RetryJudge

    Output -->|8. Display| User
    User -->|9. Feedback| Feedback
    Feedback -->|Scene Adjustment| Director
    Feedback -->|Plan Change| Planner
```

## Agent Roles & Data Structures

All interactions are strictly typed using **Pydantic** to guarantee structural reliability when parsed by the OpenAI Responses API.

*   **Extractor Agent:** Analyzes the user's initial prompt and extracts elements into an `Extraction` model containing a strict Enum for the theme, detailed character descriptions, and relationships.
*   **Planner Agent:** Adopts a specific author persona (e.g., Dan Brown, J.K. Rowling) based on the theme to generate a 9-scene Hero's Journey arc, returning a `StoryPlan`.
*   **Reviewer Agent:** A safety gatekeeper that evaluates the `StoryPlan` for 5-10-year-old age appropriateness (e.g., converting violent threats to safe scares). Returns a `ReviewResult`.
*   **ActionDecider (Director) Agent:** Evaluates the ongoing story context and determines which entity (the Storyteller or a specific Character) should speak next. Returns an `ActionDecision`.
*   **Storyteller Agent:** Acts as the narrator. Outputs a `StorytellerOutput` containing both the prose (`narrative_block`) and a hidden prompt instructing the next character (`prompt_for_next_actor`).
*   **Character Agents:** Independent agents initialized with the extracted personas. They generate seamless third-person prose matching their character description.
*   **Judge Agent:** A continuous quality control filter. Evaluates every piece of prose for safety, engagement, and alignment, returning a `Judgment`.
*   **FeedbackClassifier Agent:** Evaluates mid-story user input, classifying it as a localized "scene adjustment" or a major "plan change" via the `FeedbackClassification` model.
