"""Expert Multimodal Quality Evaluator — the operator's assessment rubric, encoded
as data for ratingkit. Source of truth (prose): ../../assessment/rubric-multimodal-quality-evaluator.md

Two independent dimensions: Content (words/meaning) and Prosody (acoustic delivery).
NOTE the standing feasibility gap: Prosody requires hearing the audio. A text model
cannot. The audio adapter supplies extracted features only; it does not close that
gap. See ../../AGENTS.md and the audio adapter docstring.
"""

RUBRIC = {
    "key": "multimodal_quality_evaluator",
    "name": "Expert Multimodal Quality Evaluator",
    "system_role": ("You evaluate conversations between a user and an AI agent by "
                    "analyzing the agent's AUDIO responses."),
    "directives": [
        "Audio is the ground truth. The transcript is only a visual aid and may "
        "contain errors — do not penalize transcript errors.",
        "Absolute separation of concerns: Content and Prosody are rated completely "
        "independently (a hallucination spoken beautifully => low Content, high Prosody; "
        "a perfect answer spoken with glitches => high Content, low Prosody).",
        "Only evaluate segments labelled 'Agent response'. User turns are context only.",
        "Do not spend more than 5 minutes fact-checking a Content rating.",
    ],
    "target_roles": ["agent", "Agent response"],
    "dimensions": [
        {
            "key": "content",
            "name": "Content",
            "low": 1, "high": 5,
            "anchors": {
                1: "Very dissatisfied — fails outright: irrelevant, wrong, dismissive, "
                   "ignores the core request/constraints, rude/NSFW, or refuses a reasonable request.",
                2: "Somewhat dissatisfied — largely fails: mostly unhelpful/off-topic, material "
                   "omission or error, ignores a correction, contradicts itself, or agrees without helping.",
                3: "Neutral — partially satisfies: a clear but non-disqualifying gap (missed minor "
                   "component, minor inaccuracy, clumsy handling of context).",
                4: "Somewhat satisfied — helpful and on target with one minor shortcoming "
                   "(small omission, slightly unsuitable length/detail).",
                5: "Very satisfied — fully addresses the request accurately and relevantly at the "
                   "right depth and tone; honors constraints; uses context; no meaningful complaint.",
            },
            "justification_rules": ("Name the exact issue and reference a specific quote. For "
                                    "ratings 1-3, explicitly state what was lacking or wrong."),
            "discuss_only": "words and meaning",
        },
        {
            "key": "prosody",
            "name": "Prosody",
            "low": 1, "high": 5,
            "anchors": {
                1: "Very dissatisfied — severe failures: jarring artifacts, voice-identity changes "
                   "(different speakers), or delivery so unnatural it distracts.",
                2: "Somewhat dissatisfied — multiple compounding issues: robotic/flat throughout, "
                   "unnatural pacing, misplaced pauses, or noticeable distortion that stays intelligible.",
                3: "Neutral — clear issues alongside acceptable moments: robotic in parts, unnatural "
                   "pauses, or shifts between natural speech and a reading style.",
                4: "Somewhat satisfied — mostly natural with minor imperfections: slightly overdone "
                   "energy, an occasional unnatural pause, or a brief scripted quality.",
                5: "Very satisfied — fully natural, expressive, appropriate; convincingly a real "
                   "person speaking in a real conversation.",
            },
            "justification_rules": ("Identify the exact delivery issue (pitch, pacing, pauses, "
                                    "volume, monotone, artifacts) and where it occurs."),
            "discuss_only": "delivery only; do not mention helpfulness or meaning",
        },
    ],
    "edge_cases": [
        "Backchannels ('mm-hmm', 'yeah') are valid agent responses: rate Content on whether the "
        "acknowledgement fits context; rate Prosody on naturalness and timing.",
        "Split responses (one response segmented across turns): rate each separately; do not "
        "penalize a natural continuation.",
        "Minor artifacts/glitches: do not discard — fold the defect into the Prosody rating and "
        "name it in the justification.",
        "Item-level discard only if the whole file is unusable (pervasive segmentation problems, "
        "broken audio, violent content). Turn-level discard only if one dimension is entirely unrateable.",
    ],
    "output_fields": ["Content Score", "Content Justification", "Prosody Score", "Prosody Justification"],
}
