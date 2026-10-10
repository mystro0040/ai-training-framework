"""Template rubric. Copy to <your_rubric>.py and edit. Pure data only.

Keys the engine reads:
  key, name                 identifiers
  system_role               the judge's role (free text)
  directives                list of core rules
  target_roles              which turn roles/labels to evaluate (matched
                            case-insensitively against turn.role AND turn.label)
  dimensions[]              each: key, name, low, high, anchors{score:desc},
                            justification_rules, discuss_only
  edge_cases                list of operational rules (free text)
  output_fields             ordered field names the judge must emit per dimension
"""

RUBRIC = {
    "key": "example",
    "name": "Example Rubric",
    "system_role": "You are an evaluator.",
    "directives": ["Rate only the target turns.", "Keep each dimension independent."],
    "target_roles": ["agent", "Agent response"],
    "dimensions": [
        {
            "key": "quality",
            "name": "Quality",
            "low": 1, "high": 5,
            "anchors": {1: "Very poor", 3: "Neutral", 5: "Excellent"},
            "justification_rules": "Name the exact issue and quote it.",
            "discuss_only": "",
        },
    ],
    "edge_cases": ["Discard a turn only if it is entirely unrateable."],
    "output_fields": ["Score", "Justification"],
}
