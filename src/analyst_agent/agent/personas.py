from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from analyst_agent.agent.outputs import ANSWER_TYPES, BaseAnswer

PERSONA_DIR = Path(__file__).parent / "personas"

SHARED_RULES = """
You answer only from the dataset reachable through your tools. It covers three sectors
with roughly six companies each and is a deliberately narrow slice, not the whole market.

Rules that override anything else:

- Call describe_schema before writing SQL. Column names recalled from memory will fail.
- Resolve every company the user names with resolve_company before making any claim about
  it, however certain you are that you know the company. A not_found status means the
  dataset holds nothing on it; say so plainly, name what is covered instead, and set
  out_of_scope. Do not describe, estimate or characterise a company that is not in the data.
- Every figure you state must come from a tool result in this conversation. Select
  source_url alongside any figure you intend to quote and record it in sources.
- A NULL is not a zero. It means the inputs could not support the calculation. Report it
  as unknown rather than treating it as an absence of debt, cost or risk.
- Margins, growth rates and deltas are fractions: 0.041 means 4.1 percent. Convert before
  presenting them.
- When coverage is thin, lower your confidence and say which gap limits the answer.
"""


@dataclass(frozen=True)
class Persona:
    key: str
    display_name: str
    lens: str
    priority_metrics: tuple[str, ...]
    preferred_relations: tuple[str, ...]
    playbook: tuple[str, ...]
    emphasis: str
    answer_type: type[BaseAnswer]

    def instructions(self, sector: str, coverage_note: str | None = None) -> str:
        steps = "\n".join(f"{i}. {s}" for i, s in enumerate(self.playbook, 1))
        metrics = ", ".join(self.priority_metrics)
        relations = ", ".join(self.preferred_relations)
        scope = f"\nWhat this sector's universe excludes: {coverage_note}\n" if coverage_note else ""
        return f"""You are a {self.display_name}. The user is asking about the {sector} sector.

{self.lens.strip()}
{SHARED_RULES}{scope}
Work through these steps before answering:

{steps}

Start from these relations: {relations}.
The metrics that carry your judgement: {metrics}.

{self.emphasis.strip()}

Answer through your own lens. Another analyst looking at these identical rows would
reach a different conclusion, and that difference is the substance of your answer, not
a matter of wording.
"""


def _load(path: Path) -> Persona:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    key = raw["key"]
    if key not in ANSWER_TYPES:
        raise ValueError(f"{path.name} declares unknown persona key {key!r}")
    return Persona(
        key=key,
        display_name=raw["display_name"],
        lens=raw["lens"],
        priority_metrics=tuple(raw["priority_metrics"]),
        preferred_relations=tuple(raw["preferred_relations"]),
        playbook=tuple(raw["playbook"]),
        emphasis=raw["emphasis"],
        answer_type=ANSWER_TYPES[key],
    )


@lru_cache
def load_personas() -> dict[str, Persona]:
    personas = {p.key: p for p in (_load(f) for f in sorted(PERSONA_DIR.glob("*.yaml")))}
    missing = set(ANSWER_TYPES) - set(personas)
    if missing:
        raise RuntimeError(f"No config found for personas: {sorted(missing)}")
    return personas


def get_persona(key: str) -> Persona:
    personas = load_personas()
    if key not in personas:
        raise KeyError(f"Unknown persona {key!r}. Available: {sorted(personas)}")
    return personas[key]


PERSONA_KEYS = tuple(sorted(ANSWER_TYPES))
